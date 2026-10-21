# ITL.K8s documentation index

Documents are grouped into numbered folders. Each file is named `x.y-title.md`, where `x` is the folder number. Start with **1. Cluster**.

## 1. Cluster

The current design: Talos, Cilium, MetalLB with BGP, Traefik, cert-manager, external-dns, Keycloak, and the ITL website.

- [1.1 Architecture](1-cluster/1.1-architecture.md): the node roles, the network, the component versions, and the main diagram.
- [1.2 Deployment](1-cluster/1.2-deployment.md): build the cluster from scratch, with the checklist, the unattended script, and phase two.
- [1.4 Ingress](1-cluster/1.4-ingress.md): the public and internal Traefik instances, the names they serve, and the request flow.
- [1.5 Load balancing and BGP](1-cluster/1.5-loadbalancing-bgp.md): MetalLB pools, BGP sessions, the planned peers, and failure cases.
- [1.6 DNS hierarchy](1-cluster/1.6-dns.md): the external and internal zones, who writes which records, and the certificates.

## 2. Network

- [2.2 VPN MTU optimization](2-network/2.2-vpn-mtu-optimization.md): MTU and MSS tuning for the ISP VPN.

## 3. Authentication

- [3.1 GitHub authentication](3-authentication/3.1-github-authentication.md): GitHub login through Keycloak.
- [3.2 Emergency access](3-authentication/3.2-emergency-access.md): break-glass procedures.

## 4. Storage

- [4.1 Storage classes](4-storage/4.1-storage-classes.md): the storage classes and how to choose one. The manifests are in [manifests/storageclasses](../manifests/storageclasses/).

## 5. GPU

- [5.1 GPU overview](5-gpu/5.1-gpu-overview.md): what the GPU setup covers.
- [5.2 AMD installation](5-gpu/5.2-amd-installation.md): installing the ROCm drivers and the device plugin.
- [5.3 AMD troubleshooting](5-gpu/5.3-amd-troubleshooting.md): the common issues, numbered 1 to 6.
- [5.4 GPU detection quick fix](5-gpu/5.4-gpu-detection-quick-fix.md): a short fix when GPUs aren't detected.

## 6. Operations

- [6.1 Backup strategy](6-operations/6.1-backup-strategy.md): what to back up, and the etcd snapshot procedure.
- [6.2 Keycloak restore plan](6-operations/6.2-keycloak-restore.md): the database dump and realm exports, what they restore, and the steps.

## 0. Historical

Records of the pre-rebuild Ubuntu cluster. They're kept for reference and aren't current.

- [0.1 Cluster capabilities (Ubuntu)](0-historical/0.1-cluster-capabilities-ubuntu.md)
- [0.2 MetalLB analysis (Ubuntu)](0-historical/0.2-metallb-analysis-ubuntu.md)

## Manifests and scripts

These aren't documents, but the docs refer to them.

- `manifests/metallb/`: the VLAN 99 IP pool, the BGP peer, and the advertisement.
- `manifests/external-dns/values-internal.yaml`: external-dns for the internal zone.
- `manifests/storageclasses/`: the storage class manifests.
- `scripts/cluster/deploy-talos.sh`: the unattended Talos deployment, with `deploy.env.example` as its settings.
- `scripts/pxe/`: the iPXE boot menu and the node config helper.

Git-ignored: `backups/` (exports and database dumps), `scripts/cluster/generated/` (cluster secrets and the kubeconfig), and `scripts/cluster/deploy.env`.
