# ITL.K8s documentation index

Documents are grouped into numbered folders. Each file is named `x.y-title.md`, where `x` is the folder number.

## 1. Cluster

- [1.1 Architecture](1-cluster/1.1-architecture.md): the Talos cluster, node roles, and network.
- [1.2 Deployment](1-cluster/1.2-deployment.md): build the cluster from scratch.
- [1.4 Ingress](1-cluster/1.4-ingress.md): public and internal Traefik, names, and request flow.
- [1.5 Load balancing and BGP](1-cluster/1.5-loadbalancing-bgp.md): MetalLB pools, BGP sessions, and failure cases.
- [1.6 DNS hierarchy](1-cluster/1.6-dns.md): `k8s.itlusions.nl` split-horizon zone, records, and certificates.

## 2. Network

- [2.2 VPN MTU optimization](2-network/2.2-vpn-mtu-optimization.md): MTU and MSS tuning for the ISP VPN.

## 3. Authentication

- [3.1 GitHub authentication](3-authentication/3.1-github-authentication.md): GitHub login through Keycloak.
- [3.2 Emergency access](3-authentication/3.2-emergency-access.md): break-glass procedures.

## 4. Storage

- [4.1 Storage classes](4-storage/4.1-storage-classes.md): storage classes and how to pick one. The manifests are in [manifests/storageclasses](../manifests/storageclasses/).

## 5. GPU

- [5.1 GPU overview](5-gpu/5.1-gpu-overview.md)
- [5.2 AMD installation](5-gpu/5.2-amd-installation.md)
- [5.3 AMD troubleshooting](5-gpu/5.3-amd-troubleshooting.md)
- [5.4 GPU detection quick fix](5-gpu/5.4-gpu-detection-quick-fix.md)

## 6. Operations

- [6.1 Backup strategy](6-operations/6.1-backup-strategy.md): what to back up, and the etcd snapshot procedure.
- [6.2 Keycloak restore plan](6-operations/6.2-keycloak-restore.md): what the exports restore, what they don't, and the steps.

## 0. Historical

Records of the existing Ubuntu cluster, kept for reference. They're not current.

- [0.1 Cluster capabilities (Ubuntu)](0-historical/0.1-cluster-capabilities-ubuntu.md)
- [0.2 MetalLB analysis (Ubuntu)](0-historical/0.2-metallb-analysis-ubuntu.md)
