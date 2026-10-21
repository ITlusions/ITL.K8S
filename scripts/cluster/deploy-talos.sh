#!/usr/bin/env bash
# Unattended deployment of the ITL Talos cluster:
#   Talos (generated config, applied to every node, etcd bootstrapped)
#   -> Cilium (CNI) -> MetalLB with BGP (VLAN 99 pool)
#
# Prerequisites: talosctl, kubectl, helm, envsubst. Every node must already be
# booted into Talos maintenance mode (see docs/cluster/deployment.md, step 1).
#
# Usage: scripts/cluster/deploy-talos.sh [path/to/deploy.env]
# Re-running is safe: existing secrets are reused, and applies are idempotent.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${1:-$HERE/deploy.env}"

log()  { printf '%s %s\n' "$(date '+%F %T')" "$*"; }
die()  { log "ERROR: $*"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing tool: $1"; }

[ -f "$ENV_FILE" ] || die "env file not found: $ENV_FILE (copy deploy.env.example)"
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

for t in talosctl kubectl helm envsubst; do need "$t"; done
case "$TALOS_INSTALLER_IMAGE" in *"<"*|*">"*) die "set TALOS_INSTALLER_IMAGE to your factory image URL (placeholder still present)";; esac
for v in CLUSTER_NAME CLUSTER_VIP CLUSTER_ENDPOINT NODES NODE_INTERFACE INSTALL_DISK NODE_GATEWAY TALOS_INSTALLER_IMAGE \
         CILIUM_VERSION METALLB_VERSION LB_POOL BGP_NODE_ASN BGP_ROUTER_ASN BGP_ROUTER_ADDRESS; do
  [ -n "${!v:-}" ] || die "$v is not set in $ENV_FILE"
done

GEN="$REPO/scripts/cluster/generated"   # git-ignored: holds secrets and kubeconfig
mkdir -p "$GEN"; chmod 700 "$GEN"
export TALOSCONFIG="$GEN/talosconfig"

# --- 1. Talos secrets and machine configs ----------------------------------
if [ ! -f "$GEN/secrets.yaml" ]; then
  log "generating Talos secrets"
  talosctl gen secrets -o "$GEN/secrets.yaml"
  chmod 600 "$GEN/secrets.yaml"
fi

PATCH_DIR="$GEN/patches"; mkdir -p "$PATCH_DIR"
# Cluster-wide: no built-in CNI (Cilium is installed later), VIP on control-plane nodes
cat > "$PATCH_DIR/cluster.yaml" <<EOF
cluster:
  network:
    cni:
      name: none
machine:
  install:
    disk: ${INSTALL_DISK}
    image: ${TALOS_INSTALLER_IMAGE}
EOF

cat > "$PATCH_DIR/controlplane-vip.yaml" <<EOF
machine:
  network:
    interfaces:
      - interface: ${NODE_INTERFACE}
        dhcp: false
        vip:
          ip: ${CLUSTER_VIP}
EOF

if [ ! -f "$GEN/controlplane.yaml" ]; then
  log "generating machine configs"
  talosctl gen config "$CLUSTER_NAME" "$CLUSTER_ENDPOINT" \
    --with-secrets "$GEN/secrets.yaml" \
    --kubernetes-version "$KUBERNETES_VERSION" \
    --config-patch "@$PATCH_DIR/cluster.yaml" \
    --config-patch-control-plane "@$PATCH_DIR/controlplane-vip.yaml" \
    --output-dir "$GEN" --force
fi

# --- 2. Apply configs to every node -----------------------------------------
CP_IPS=(); FIRST_CP=""
for entry in $NODES; do
  IFS=: read -r name ip role <<<"$entry"
  if [ "$role" = "controlplane" ]; then
    [ -z "$FIRST_CP" ] && FIRST_CP="$ip"
    CP_IPS+=("$ip")
    cfg="$GEN/controlplane.yaml"
  else
    cfg="$GEN/worker.yaml"
  fi

  hostpatch="$PATCH_DIR/host-$name.yaml"
  printf 'machine:\n  network:\n    hostname: %s\n    nameservers: [10.99.2.10]\n    interfaces:\n      - interface: %s\n        addresses: [%s/24]\n        routes:\n          - network: 0.0.0.0/0\n            gateway: %s\n' \
    "$name" "$NODE_INTERFACE" "$ip" "$NODE_GATEWAY" > "$hostpatch"

  log "applying config to $name ($ip, $role)"
  # --insecure is needed only while the node is still in maintenance mode.
  # Once a node has a config, talosctl uses the talosconfig instead.
  if talosctl --nodes "$ip" get machineconfig >/dev/null 2>&1; then
    talosctl apply-config --nodes "$ip" --file "$cfg" --config-patch "@$hostpatch" --mode auto
  else
    talosctl apply-config --insecure --nodes "$ip" --file "$cfg" --config-patch "@$hostpatch"
  fi
done

# --- 3. Bootstrap etcd and fetch kubeconfig --------------------------------
log "waiting for $FIRST_CP to accept the API"
for _ in $(seq 1 60); do
  talosctl --nodes "$FIRST_CP" --endpoints "$FIRST_CP" version >/dev/null 2>&1 && break
  sleep 10
done

if talosctl --nodes "$FIRST_CP" --endpoints "$FIRST_CP" etcd members >/dev/null 2>&1; then
  log "etcd already bootstrapped, skipping bootstrap"
else
  log "bootstrapping etcd on $FIRST_CP"
  talosctl bootstrap --nodes "$FIRST_CP" --endpoints "$FIRST_CP"
fi

log "fetching kubeconfig"
talosctl kubeconfig "$GEN/kubeconfig" --nodes "$FIRST_CP" --endpoints "$CLUSTER_VIP" --force
export KUBECONFIG="$GEN/kubeconfig"

for _ in $(seq 1 60); do
  kubectl get --raw=/readyz >/dev/null 2>&1 && break
  sleep 10
done
kubectl get --raw=/readyz >/dev/null || die "API server not ready"

# --- 4. Cilium (CNI) --------------------------------------------------------
log "installing Cilium $CILIUM_VERSION"
helm repo add cilium https://helm.cilium.io >/dev/null 2>&1 || true
helm repo update cilium >/dev/null
helm upgrade --install cilium cilium/cilium --version "$CILIUM_VERSION" \
  --namespace kube-system \
  --set ipam.mode=kubernetes \
  --set k8sServiceHost="$CLUSTER_VIP" \
  --set k8sServicePort=6443 \
  --set kubeProxyReplacement=false \
  --set operator.replicas=2 \
  --wait --timeout 10m

# --- 5. MetalLB with BGP ----------------------------------------------------
log "installing MetalLB $METALLB_VERSION"
helm repo add metallb https://metallb.github.io/metallb >/dev/null 2>&1 || true
helm repo update metallb >/dev/null
helm upgrade --install metallb metallb/metallb --version "$METALLB_VERSION" \
  --namespace metallb-system --create-namespace --wait --timeout 10m

export LB_POOL BGP_NODE_ASN BGP_ROUTER_ASN BGP_ROUTER_ADDRESS
envsubst < "$REPO/manifests/metallb/ipaddresspool.yaml"  | kubectl apply -f -
envsubst < "$REPO/manifests/metallb/bgppeer.yaml"        | kubectl apply -f -
envsubst < "$REPO/manifests/metallb/bgpadvertisement.yaml" | kubectl apply -f -

# --- 6. Verify --------------------------------------------------------------
log "waiting for all nodes to be Ready"
kubectl wait --for=condition=Ready node --all --timeout=15m
kubectl get nodes -o wide
log "done. Kubeconfig: $GEN/kubeconfig"
