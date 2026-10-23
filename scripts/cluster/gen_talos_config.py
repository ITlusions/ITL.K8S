#!/usr/bin/env python3
"""Generate Talos secrets and machine configs for a manual deployment.

Run once per cluster. Safe to re-run: skips any step whose output already
exists in generated/. Needs talosctl on PATH.

Usage: python3 scripts/cluster/gen_talos_config.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE / "generated"
PATCH_DIR = GEN / "patches"

CLUSTER_NAME = "itl"
# NOTE: temporarily the first control-plane node's own IP, not the VIP, per
# https://docs.siderolabs.com/talos/v1.14/getting-started/getting-started
# (the VIP can't be up before etcd/control-plane is bootstrapped). Switch
# back to the VIP (10.99.100.10) once itl-cp01 is healthy and itl-cp02 joins.
CLUSTER_ENDPOINT = "https://10.99.100.11:6443"
KUBERNETES_VERSION = "1.37.1"


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


INSTALL_DISK = "/dev/sda"
INSTALL_IMAGE = ("factory.talos.dev/installer/"
                  "8479232c408ba2e411fefcf18c0e83ac657875c4d4d2b09b55a31a38b9c013a1:v1.14.4")


def main() -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    os.chmod(GEN, 0o700)

    secrets = GEN / "secrets.yaml"
    if secrets.exists():
        print(f"secrets already exist: {secrets}, skipping gen secrets")
    else:
        print("generating Talos secrets")
        subprocess.run(["talosctl", "gen", "secrets", "-o", str(secrets)], check=True)
        os.chmod(secrets, 0o600)

    controlplane_cfg = GEN / "controlplane.yaml"
    if controlplane_cfg.exists():
        print(f"machine configs already exist: {controlplane_cfg}, skipping gen config")
        return

    print("generating machine configs (controlplane.yaml, worker.yaml)")
    subprocess.run([
        "talosctl", "gen", "config", CLUSTER_NAME, CLUSTER_ENDPOINT,
        "--with-secrets", str(secrets),
        "--kubernetes-version", KUBERNETES_VERSION,
        "--install-disk", INSTALL_DISK,
        "--install-image", INSTALL_IMAGE,
        "--output-dir", str(GEN), "--force",
    ], check=True)
    print(f"done. See {GEN}")


if __name__ == "__main__":
    main()
