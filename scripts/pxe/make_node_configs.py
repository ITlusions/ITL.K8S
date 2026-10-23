#!/usr/bin/env python3
"""Create one machine config per node, with its hostname and address patched in,
for the PXE config server to serve.

Run after scripts/cluster/deploy_talos.py has generated the base configs
(scripts/cluster/generated/controlplane.yaml and worker.yaml).

Output: scripts/cluster/generated/pxe/<node>.yaml

Usage: python3 scripts/pxe/make_node_configs.py
Override defaults with environment variables: NODE_INTERFACE, NODE_GATEWAY, NODES.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent / "cluster" / "generated"
OUT = GEN / "pxe"

NODE_INTERFACE = os.environ.get("NODE_INTERFACE", "eth0")
NODE_GATEWAY = os.environ.get("NODE_GATEWAY", "10.99.100.1")
NODES = os.environ.get(
    "NODES",
    "talos-cp01:10.99.100.11:controlplane talos-cp02:10.99.100.12:controlplane "
    "talos-w01:10.99.100.21:worker talos-w02:10.99.100.22:worker talos-w03:10.99.100.23:worker",
)


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if shutil.which("talosctl") is None:
        die("talosctl not found")
    for base in ("controlplane.yaml", "worker.yaml"):
        if not (GEN / base).is_file():
            die(f"base config missing: {GEN / base}; run deploy_talos.py first")

    OUT.mkdir(parents=True, exist_ok=True)
    os.chmod(OUT, 0o700)
    for entry in NODES.split():
        name, ip, role = entry.split(":")
        base = GEN / f"{role}.yaml"
        patch = OUT / f"{name}.patch.yaml"
        patch.write_text(
            f"machine:\n  network:\n    hostname: {name}\n    interfaces:\n"
            f"      - interface: {NODE_INTERFACE}\n        addresses: [{ip}/24]\n"
            f"        routes:\n          - network: 0.0.0.0/0\n            gateway: {NODE_GATEWAY}\n",
            encoding="utf-8")
        target = OUT / f"{name}.yaml"
        subprocess.run(["talosctl", "machineconfig", "patch", str(base),
                        "--patch", f"@{patch}", "-o", str(target)], check=True)
        patch.unlink()
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
