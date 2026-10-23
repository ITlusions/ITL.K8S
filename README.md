# ITL.K8s

Documentation for the ITlusions Kubernetes cluster: how it's built, how it's deployed, and how to operate it.

## Main stack

| Layer | Component | Notes |
|---|---|---|
| OS | **Talos** | Immutable Kubernetes OS, managed with `talosctl` |
| CNI | **Cilium** | eBPF networking, the target CNI |
| Load balancing | **MetalLB with BGP** | LoadBalancer IPs from VLAN 99 (`10.99.99.20–100`), announced to the gateway |
| Ingress | **Traefik** | Public instance on `10.99.99.27`, internal instance (Gateway API) on `10.99.99.26` |
| Certificates | **cert-manager** | Public names: Let's Encrypt **HTTP-01** through the public Traefik (`letsencrypt-issuer`). Internal `int` names: Let's Encrypt **DNS-01** through the TransIP webhook (LAN-only addresses can't pass HTTP-01) |
| DNS records | **external-dns** | Writes `k8s.int.itlusions.nl` records into the internal zone from Services, Ingresses, and Gateway routes |
| Identity | **Keycloak** | `sts.itlusions.com`, realm `itlusions` |
| Website | **ITL website** | Public, behind the public Traefik instance |

Not yet decided: Longhorn (storage), Argo CD (GitOps), and Prefect. See [the deployment doc](docs/1-cluster/1.2-deployment.md#step-5-phase-2-not-automated-yet).

## Cluster layout

Five servers, two of them control-plane nodes.

| Node | Address | Role |
|---|---|---|
| itl-cp01 | 10.99.100.11 | control plane |
| talos-cp02 | 10.99.100.12 | control plane |
| talos-w01 | 10.99.100.21 | worker |
| talos-w02 | 10.99.100.22 | worker |
| talos-w03 | 10.99.100.23 | worker |
| control-plane VIP | 10.99.100.10 | Kubernetes API |

The full diagram is in [docs/1-cluster/1.1-architecture.md](docs/1-cluster/1.1-architecture.md).

## Deploying from scratch

1. Read the checklist and the steps in [docs/1-cluster/1.2-deployment.md](docs/1-cluster/1.2-deployment.md).
2. Boot the five nodes into Talos (manual step).
3. Copy `scripts/cluster/deploy.env.example` to `scripts/cluster/deploy.env` and fill it in.
4. Run `python3 scripts/cluster/deploy_talos.py`. It installs Talos, Cilium, and MetalLB with BGP.
5. Take an etcd snapshot right after bootstrap.

Generated secrets, the kubeconfig, and `deploy.env` are git-ignored. Keep them out of the repo.

## Repository layout

```
ITL.K8s/
├── README.md
├── docs/
│   ├── index.md                              # full documentation index
│   ├── 1-cluster/
│   │   ├── 1.1-architecture.md               # architecture diagram and node roles
│   │   ├── 1.2-deployment.md                 # build the cluster from scratch
│   │   ├── 1.4-ingress.md                    # public and internal Traefik
│   │   ├── 1.5-loadbalancing-bgp.md          # MetalLB pools and BGP
│   │   ├── 1.6-dns.md                        # k8s.itlusions.nl DNS hierarchy
│   ├── 2-network/
│   │   └── 2.2-vpn-mtu-optimization.md
│   ├── 3-authentication/
│   │   ├── 3.1-github-authentication.md      # GitHub login through Keycloak
│   │   └── 3.2-emergency-access.md           # break-glass procedures
│   ├── 4-storage/
│   │   └── 4.1-storage-classes.md
│   ├── 5-gpu/
│   │   └── 5.1-…5.4                          # AMD GPU overview, install, troubleshooting
│   ├── 6-operations/
│   │   └── 6.1-backup-strategy.md
│   └── 0-historical/                          # records of the pre-rebuild Ubuntu cluster
│       ├── 0.1-cluster-capabilities-ubuntu.md
│       └── 0.2-metallb-analysis-ubuntu.md
├── manifests/
│   ├── metallb/                              # IP pool, BGP peer, advertisement
│   └── storageclasses/                       # storage class manifests
└── scripts/
    ├── cluster/                              # unattended Talos deployment
    └── pxe/                                  # iPXE boot menu and config helpers
```

## Authentication

Cluster access uses **GitHub OAuth through Keycloak** (`sts.itlusions.com`):

- Single sign-on with GitHub credentials.
- GitHub teams map to Kubernetes RBAC.
- All access goes through Keycloak, with audit logging.

Setup: [GitHub authentication](docs/3-authentication/3.1-github-authentication.md).

Break-glass access: [emergency access](docs/3-authentication/3.2-emergency-access.md).

## Storage

Storage classes and their use cases are in [docs/4-storage/4.1-storage-classes.md](docs/4-storage/4.1-storage-classes.md). For databases, use `ha-dbs-lh` (replicated, retained). Longhorn is not in the main stack yet, so confirm before depending on it.

## Backups

The backup that matters is the **etcd snapshot**. Take one after bootstrap and regularly after that, and store it off the cluster. Procedures and what else to back up: [KUBERNETES_BACKUP_STRATEGY.md](docs/6-operations/6.1-backup-strategy.md).

## Contacts

- **Platform team:** cluster management and infrastructure.
- **Security team:** policies and compliance.
- **Emergencies:** Matrix `#platform-emergency`. Other questions: `#kubernetes-help`.

---

**Last updated:** October 21, 2026
