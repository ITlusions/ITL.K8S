#!/usr/bin/env bash
# Create one machine config per node, with its hostname and address patched in,
# for the PXE config server to serve. Run after scripts/cluster/deploy-talos.sh
# has generated the base configs (scripts/cluster/generated/).
#
# Output: scripts/cluster/generated/pxe/<node>.yaml
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
GEN="$HERE/../cluster/generated"
OUT="$GEN/pxe"
NODE_INTERFACE=${NODE_INTERFACE:-eth0}
NODE_GATEWAY=${NODE_GATEWAY:-10.99.100.1}
NODES=${NODES:-"talos-cp01:10.99.100.11:controlplane talos-cp02:10.99.100.12:controlplane talos-w01:10.99.100.21:worker talos-w02:10.99.100.22:worker talos-w03:10.99.100.23:worker"}

command -v talosctl >/dev/null || { echo "talosctl not found" >&2; exit 1; }
[ -f "$GEN/controlplane.yaml" ] && [ -f "$GEN/worker.yaml" ] || { echo "base configs missing in $GEN; run deploy-talos.sh first" >&2; exit 1; }

mkdir -p "$OUT"; chmod 700 "$OUT"
for entry in $NODES; do
  IFS=: read -r name ip role <<<"$entry"
  base="$GEN/$role.yaml"
  patch="$OUT/$name.patch.yaml"
  cat > "$patch" <<EOF
machine:
  network:
    hostname: ${name}
    interfaces:
      - interface: ${NODE_INTERFACE}
        addresses: [${ip}/24]
        routes:
          - network: 0.0.0.0/0
            gateway: ${NODE_GATEWAY}
EOF
  talosctl machineconfig patch "$base" --patch "@$patch" -o "$OUT/$name.yaml"
  rm -f "$patch"
  echo "wrote $OUT/$name.yaml"
done
