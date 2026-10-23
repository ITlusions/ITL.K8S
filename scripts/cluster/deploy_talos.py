#!/usr/bin/env python3
"""Unattended deployment of the ITL Talos cluster.

    Talos (generated config, applied to every node, etcd bootstrapped)
    -> Cilium (CNI) -> MetalLB with BGP (VLAN 99 pool)

Prerequisites: talosctl, kubectl, helm on PATH. Every node must already be booted
into Talos maintenance mode (see docs/1-cluster/1.2-deployment.md, step 1).

Usage:
    python3 scripts/cluster/deploy_talos.py [path/to/deploy.env]

Re-running is safe: existing secrets are reused, bootstrap is skipped if etcd
exists, and applies are idempotent.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GEN = REPO / "scripts" / "cluster" / "generated"   # git-ignored: secrets and kubeconfig
PATCH_DIR = GEN / "patches"

REQUIRED = [
    "CLUSTER_NAME", "CLUSTER_VIP", "CLUSTER_ENDPOINT", "KUBERNETES_VERSION", "NODES",
    "NODE_INTERFACE", "INSTALL_DISK", "NODE_GATEWAY", "TALOS_INSTALLER_IMAGE",
    "METALLB_VERSION", "LB_POOL", "BGP_NODE_ASN", "BGP_ROUTER_ASN",
    "BGP_ROUTER_ADDRESS",
]


def log(msg: str) -> None:
    """Print a timestamped progress message to stdout.

    Args:
        msg: The message to print.
    """
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def die(msg: str) -> None:
    """Log an error message and exit the script with status 1.

    Args:
        msg: The error message to print before exiting.
    """
    log(f"ERROR: {msg}")
    sys.exit(1)


def load_env(path: Path) -> dict[str, str]:
    """Read a KEY=VALUE environment file, such as deploy.env.

    Blank lines and lines starting with ``#`` are skipped. Values may be wrapped
    in single or double quotes, and a trailing ``# comment`` after an unquoted
    value is removed.

    Args:
        path: Path to the environment file.

    Returns:
        A dictionary mapping each key to its value, as strings.
    """
    """Parse KEY=VALUE lines. Supports quotes and trailing # comments."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value[:1] in ("'", '"'):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            value = re.sub(r"\s+#.*$", "", value)
        values[key.strip()] = value
    return values


def run(cmd: list[str], *, check: bool = True, input_text: str | None = None,
        capture: bool = False, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run an external command and wait for it to finish.

    Args:
        cmd: The command and its arguments, as a list.
        check: Raise ``CalledProcessError`` if the command exits non-zero.
        input_text: Text to send to the command's standard input, or None.
        capture: Capture stdout and stderr instead of printing them.
        env: Environment for the command. Defaults to the current environment.

    Returns:
        The completed process, including its return code and any captured output.
    """
    return subprocess.run(
        cmd, check=check, input=input_text, text=True, env=env or os.environ.copy(),
        stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None,
    )


def succeeds(cmd: list[str], env: dict[str, str]) -> bool:
    """Check whether a command exits with status 0, without raising on failure.

    Output is captured and discarded. Use this for readiness and existence checks.

    Args:
        cmd: The command and its arguments, as a list.
        env: Environment for the command.

    Returns:
        True if the command exits with status 0, otherwise False.
    """
    return run(cmd, check=False, capture=True, env=env).returncode == 0


def envsubst(template: Path, values: dict[str, str]) -> str:
    """Fill ``${NAME}`` placeholders in a template file, like the envsubst tool.

    Names that aren't in ``values`` are left unchanged, so a missing value is
    visible in the output rather than silently blank.

    Args:
        template: Path to the template file.
        values: Mapping of placeholder names to their replacement values.

    Returns:
        The template text with the placeholders filled in.
    """
    """Replace ${NAME} with values[NAME]. Unknown names are left unchanged."""
    text = template.read_text(encoding="utf-8")
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
                  lambda m: values.get(m.group(1), m.group(0)), text)


def wait_for(check, attempts: int = 60, delay: int = 10) -> bool:
    """Call ``check`` repeatedly until it returns True, or give up.

    Used for slow steps such as the first API server coming up after bootstrap.

    Args:
        check: A callable with no arguments that returns True when the wait is over.
        attempts: The maximum number of tries.
        delay: Seconds to sleep between tries.

    Returns:
        True if ``check`` returned True within the attempts, otherwise False.
    """
    for _ in range(attempts):
        if check():
            return True
        time.sleep(delay)
    return False


def parse_nodes(spec: str) -> list[tuple[str, str, str]]:
    """Parse the NODES setting into (name, address, role) tuples.

    The format is space-separated ``name:ip:role`` entries, where role is
    ``controlplane`` or ``worker``.

    Args:
        spec: The NODES value from the environment file.

    Returns:
        One ``(name, ip, role)`` tuple per node, in the order given.

    Raises:
        SystemExit: If a role is not ``controlplane`` or ``worker``.
    """
    nodes = []
    for entry in spec.split():
        name, ip, role = entry.split(":")
        if role not in ("controlplane", "worker"):
            die(f"bad role for {name}: {role}")
        nodes.append((name, ip, role))
    return nodes


def main() -> None:
    """Deploy the ITL Talos cluster from start to finish.

    The stack is Talos Linux (OS), Cilium (CNI), and MetalLB in BGP mode for
    LoadBalancer IPs on VLAN 99. Each step below depends on the one before it.

    Prerequisites:
        * ``talosctl``, ``kubectl``, and ``helm`` on PATH.
        * Every node booted into Talos maintenance mode, reachable on its address.
        * An environment file (see ``deploy.env.example``) with every required
          setting filled in. ``TALOS_INSTALLER_IMAGE`` must be a real factory
          image, not the placeholder.

    Steps, in order:
        1. Load and check the environment file and the required tools.
        2. Generate the Talos secrets (once) and the machine configs.
           The cluster patch turns off the built-in CNI so Cilium can be
           installed, and the control-plane patch adds the shared VIP.
        3. Apply each node's config, with its hostname and static address.
           Nodes still in maintenance mode get ``--insecure``. Nodes that already
           have a config are updated with ``--mode auto``.
        4. Bootstrap etcd on the first control-plane node (only if it isn't
           already bootstrapped), then write the kubeconfig to ``generated/``.
        5. Install Cilium as the CNI, with the API server set to the VIP.
           kube-proxy is kept for now.
        6. Install MetalLB, then apply the VLAN 99 IP pool, the BGP peer, and the
           BGP advertisement from ``manifests/metallb/``.
        7. Wait for every node to be Ready, and print the node list.

    Inputs:
        * ``argv[1]`` (optional): path to the environment file. Defaults to
          ``deploy.env`` next to this script.

    Outputs (all under ``scripts/cluster/generated/``, which is git-ignored):
        * ``secrets.yaml``: the Talos cluster secrets. Keep this safe.
        * ``controlplane.yaml`` and ``worker.yaml``: the machine configs.
        * ``talosconfig`` and ``kubeconfig``: credentials for the new cluster.
        * ``patches/``: the small patch files used when applying the configs.

    Re-running is safe. Existing secrets and configs are reused, bootstrap is
    skipped if etcd exists, and the applies are idempotent. If a step fails,
    fix the cause and run the script again from the start.

    Exits with status 1 on the first error, with a message that names the setting
    or tool at fault.
    """
    env_file = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "deploy.env"
    if not env_file.is_file():
        die(f"env file not found: {env_file} (copy deploy.env.example)")
    cfg = load_env(env_file)
    for name in REQUIRED:
        if not cfg.get(name):
            die(f"{name} is not set in {env_file}")
    if "<" in cfg["TALOS_INSTALLER_IMAGE"] or ">" in cfg["TALOS_INSTALLER_IMAGE"]:
        die("set TALOS_INSTALLER_IMAGE to your factory image URL (placeholder still present)")
    for tool in ("talosctl", "kubectl", "helm"):
        if shutil.which(tool) is None:
            die(f"missing tool: {tool}")

    GEN.mkdir(parents=True, exist_ok=True)
    os.chmod(GEN, 0o700)
    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TALOSCONFIG"] = str(GEN / "talosconfig")
    nodes = parse_nodes(cfg["NODES"])
    first_cp = next(ip for _, ip, role in nodes if role == "controlplane")

    # 1. Talos secrets and machine configs
    secrets = GEN / "secrets.yaml"
    if not secrets.exists():
        log("generating Talos secrets")
        run(["talosctl", "gen", "secrets", "-o", str(secrets)])
        os.chmod(secrets, 0o600)

    # Cluster-wide patch: no built-in CNI (Cilium is installed in step 5), and the install disk and image.
    cluster_patch = PATCH_DIR / "cluster.yaml"
    cluster_patch.write_text(
        "cluster:\n  network:\n    cni:\n      name: none\n"
        "machine:\n  install:\n"
        f"    disk: {cfg['INSTALL_DISK']}\n    image: {cfg['TALOS_INSTALLER_IMAGE']}\n",
        encoding="utf-8")
    # Control-plane patch: the shared VIP is announced on the control-plane interface, and DHCP is off.
    vip_patch = PATCH_DIR / "controlplane-vip.yaml"
    vip_patch.write_text(
        "machine:\n  network:\n    interfaces:\n"
        f"      - interface: {cfg['NODE_INTERFACE']}\n        dhcp: false\n"
        f"        vip:\n          ip: {cfg['CLUSTER_VIP']}\n",
        encoding="utf-8")

    if not (GEN / "controlplane.yaml").exists():
        log("generating machine configs")
        run(["talosctl", "gen", "config", cfg["CLUSTER_NAME"], cfg["CLUSTER_ENDPOINT"],
             "--with-secrets", str(secrets),
             "--kubernetes-version", cfg["KUBERNETES_VERSION"],
             "--config-patch", f"@{cluster_patch}",
             "--config-patch-control-plane", f"@{vip_patch}",
             "--output-dir", str(GEN), "--force"], env=env)

    # 2. Apply configs to every node
    for name, ip, role in nodes:
        cfg_file = GEN / ("controlplane.yaml" if role == "controlplane" else "worker.yaml")
        # Per-node patch: hostname, static address, default gateway, and the internal DNS server.
        host_patch = PATCH_DIR / f"host-{name}.yaml"
        host_patch.write_text(
            f"machine:\n  network:\n    hostname: {name}\n    nameservers: [10.99.2.10]\n"
            f"    interfaces:\n      - interface: {cfg['NODE_INTERFACE']}\n"
            f"        addresses: [{ip}/24]\n        routes:\n"
            f"          - network: 0.0.0.0/0\n            gateway: {cfg['NODE_GATEWAY']}\n",
            encoding="utf-8")
        log(f"applying config to {name} ({ip}, {role})")
        # --insecure only while the node is in maintenance mode; afterwards use talosconfig.
        if succeeds(["talosctl", "--nodes", ip, "get", "machineconfig"], env):
            run(["talosctl", "apply-config", "--nodes", ip, "--file", str(cfg_file),
                 "--config-patch", f"@{host_patch}", "--mode", "auto"], env=env)
        else:
            run(["talosctl", "apply-config", "--insecure", "--nodes", ip, "--file", str(cfg_file),
                 "--config-patch", f"@{host_patch}"], env=env)

    # 3. Bootstrap etcd and fetch kubeconfig
    log(f"waiting for {first_cp} to accept the API")
    # The first API server may take a few minutes to come up after the config is applied.
    wait_for(lambda: succeeds(["talosctl", "--nodes", first_cp, "--endpoints", first_cp, "version"], env))

    if succeeds(["talosctl", "--nodes", first_cp, "--endpoints", first_cp, "etcd", "members"], env):
        log("etcd already bootstrapped, skipping bootstrap")
    else:
        log(f"bootstrapping etcd on {first_cp}")
        run(["talosctl", "bootstrap", "--nodes", first_cp, "--endpoints", first_cp], env=env)

    log("fetching kubeconfig")
    kubeconfig = GEN / "kubeconfig"
    run(["talosctl", "kubeconfig", str(kubeconfig), "--nodes", first_cp,
         "--endpoints", cfg["CLUSTER_VIP"], "--force"], env=env)
    # From here on, kubectl and helm use the new cluster's kubeconfig.
    env["KUBECONFIG"] = str(kubeconfig)

    wait_for(lambda: succeeds(["kubectl", "get", "--raw=/readyz"], env))
    if not succeeds(["kubectl", "get", "--raw=/readyz"], env):
        die("API server not ready")

    # 4. Cilium (CNI), from the ITL.Cilium wrapper chart - cloned as a sibling
    # of this repo (ITlusions/ITL.Cilium). Talos-specific overrides and Hubble
    # live in that chart's own values.yaml now, not here; only the
    # cluster-specific bits (VIP, operator replica count) are set per deploy.
    cilium_repo = REPO.parent / "ITL.Cilium"
    cilium_chart = cilium_repo / "itl.cilium"
    log(f"fetching ITL.Cilium ({cilium_repo})")
    if cilium_repo.exists():
        run(["git", "-C", str(cilium_repo), "pull", "--ff-only"], env=env)
    else:
        run(["git", "clone", "https://github.com/ITlusions/ITL.Cilium.git", str(cilium_repo)], env=env)

    # The actual Cilium version is now pinned in ITL.Cilium's Chart.yaml
    # dependency, not CILIUM_VERSION here - bump it there, not in deploy.env.
    log(f"installing Cilium (version pinned in {cilium_chart}/Chart.yaml)")
    run(["helm", "dependency", "update", str(cilium_chart)], env=env)
    run(["helm", "upgrade", "--install", "cilium", str(cilium_chart),
         "--namespace", "kube-system",
         "--set", f"cilium.k8sServiceHost={cfg['CLUSTER_VIP']}",
         "--set", "cilium.operator.replicas=2",
         "--wait", "--timeout", "10m"], env=env)

    # 5. MetalLB with BGP
    log(f"installing MetalLB {cfg['METALLB_VERSION']}")
    # The namespace needs the "privileged" Pod Security Admission label before the
    # speaker DaemonSet is created, or it's rejected: the speaker needs hostNetwork,
    # hostPort, and NET_ADMIN/NET_RAW/SYS_ADMIN for BGP/ARP, which the cluster's
    # default "baseline" PSA level blocks. See manifests/metallb/namespace.yaml.
    run(["kubectl", "apply", "-f", str(REPO / "manifests" / "metallb" / "namespace.yaml")], env=env)
    run(["helm", "repo", "add", "metallb", "https://metallb.github.io/metallb"], check=False, capture=True, env=env)
    run(["helm", "repo", "update", "metallb"], capture=True, env=env)
    run(["helm", "upgrade", "--install", "metallb", "metallb/metallb",
         "--version", cfg["METALLB_VERSION"], "--namespace", "metallb-system",
         "--wait", "--timeout", "10m"], env=env)

    # Only these values are substituted into the MetalLB manifests.
    values = {k: cfg[k] for k in ("LB_POOL", "BGP_NODE_ASN", "BGP_ROUTER_ASN", "BGP_ROUTER_ADDRESS")}
    for manifest in ("ipaddresspool.yaml", "bgppeer.yaml", "bgpadvertisement.yaml"):
        rendered = envsubst(REPO / "manifests" / "metallb" / manifest, values)
        run(["kubectl", "apply", "-f", "-"], input_text=rendered, env=env)

    # 6. Verify
    log("waiting for all nodes to be Ready")
    run(["kubectl", "wait", "--for=condition=Ready", "node", "--all", "--timeout=15m"], env=env)
    run(["kubectl", "get", "nodes", "-o", "wide"], env=env)
    log(f"done. Kubeconfig: {kubeconfig}")


if __name__ == "__main__":
    main()
