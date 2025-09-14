# ITL.K8s - Kubernetes Infrastructure Documentation

> 🚀 **Comprehensive Kubernetes infrastructure documentation and configuration management for ITlusions**

Welcome to the ITlusions Kubernetes (ITL.K8s) documentation repository. This repository serves as the central hub for all Kubernetes-related documentation, best practices, configurations, and operational guides.

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Documentation Structure](#-documentation-structure)
- [Storage Classes](#-storage-classes)
- [Authentication](#-authentication)
- [Getting Started](#-getting-started)
- [Contributing](#-contributing)
- [Support](#-support)

## 🚀 Quick Start

### New to ITL Kubernetes?

1. **📖 Read the [Documentation Index](docs/index.md)** - Start here for a complete overview
2. **🔐 Set up [GitHub Authentication](docs/authentication/GITHUB_AUTHENTICATION.md)** - Configure cluster access
3. **💾 Understand [Storage Classes](docs/storageClasses/README.md)** - Choose the right storage for your workloads
4. **🛠️ Follow our [Best Practices](#best-practices)** - Ensure production-ready deployments

### Quick Access Links

| Resource | Description | Status |
|----------|-------------|--------|
| 📚 [Full Documentation](docs/index.md) | Complete documentation index | ✅ Available |
| 🔐 [Authentication Guide](docs/authentication/GITHUB_AUTHENTICATION.md) | GitHub OAuth setup for K8s access | ✅ Available |
| 💾 [Storage Classes](docs/storageClasses/README.md) | Storage configuration and selection guide | ✅ Available |
| 🏗️ Architecture Diagrams | Infrastructure overview and patterns | 🚧 Coming Soon |
| 📊 Monitoring Dashboards | Grafana dashboards and alerts | 🚧 Coming Soon |

## 📁 Documentation Structure

```
ITL.K8s/
├── README.md                          # This file - main entry point
├── docs/
│   ├── index.md                       # Complete documentation index
│   ├── authentication/
│   │   └── GITHUB_AUTHENTICATION.md  # GitHub OAuth for Kubernetes
│   └── storageClasses/
│       ├── README.md                  # Storage classes overview
│       ├── ha-dbs-lh.yaml            # High availability database storage
│       ├── longhorn.yaml             # Default distributed storage
│       ├── longhorn-static.yaml      # Simplified Longhorn storage
│       ├── minio-data.yaml           # MinIO object storage
│       ├── nfs-csi.yaml              # Network file system storage
│       ├── openebs-hostpath.yaml     # Local high-performance storage
│       └── local-storage.yaml        # Manual provisioned storage
└── [Additional directories as needed]
```

## 💾 Storage Classes

Our Kubernetes cluster provides multiple storage classes optimized for different workloads:

### 🏆 **Recommended Storage Classes**

| Storage Class | Use Case | Performance | Availability | Documentation |
|---------------|----------|-------------|--------------|---------------|
| **`ha-dbs-lh`** | 🗄️ Production databases | High | Very High | [Details](docs/storageClasses/ha-dbs-lh.yaml) |
| **`longhorn`** | 📱 General applications | High | High | [Details](docs/storageClasses/longhorn.yaml) |
| **`openebs-hostpath`** | ⚡ High-performance apps | Very High | Medium | [Details](docs/storageClasses/openebs-hostpath.yaml) |
| **`nfs-csi`** | 🤝 Shared volumes | Medium | High | [Details](docs/storageClasses/nfs-csi.yaml) |

**👉 [Complete Storage Classes Guide](docs/storageClasses/README.md)**

### Quick Storage Selection

```bash
# For databases (PostgreSQL, MySQL, MongoDB)
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: database-storage
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: ha-dbs-lh
  resources:
    requests:
      storage: 10Gi
EOF

# For applications
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-storage
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: longhorn
  resources:
    requests:
      storage: 5Gi
EOF
```

## 🔐 Authentication

### GitHub OAuth Integration

We use **GitHub OAuth** for Kubernetes cluster authentication through Keycloak:

- ✅ **Single Sign-On**: Use your GitHub credentials
- ✅ **Team-based Access**: GitHub teams → Kubernetes RBAC
- ✅ **Centralized Management**: All access through Keycloak
- ✅ **Audit Trail**: Complete authentication logging

**👉 [Setup GitHub Authentication](docs/authentication/GITHUB_AUTHENTICATION.md)**

### Quick Auth Setup

```bash
# Check your current authentication
kubectl auth whoami

# Login with GitHub (via Keycloak)
kubectl oidc-login

# Verify your permissions
kubectl auth can-i get pods --namespace=default
```

## 🛠️ Getting Started

### For Developers

1. **Setup Access**: Follow the [GitHub Authentication Guide](docs/authentication/GITHUB_AUTHENTICATION.md)
2. **Choose Storage**: Use the [Storage Classes Guide](docs/storageClasses/README.md)
3. **Deploy Applications**: Follow our deployment best practices
4. **Monitor**: Use our monitoring dashboards

### For Platform Engineers

1. **Read Full Documentation**: Start with [docs/index.md](docs/index.md)
2. **Understand Architecture**: Review infrastructure patterns
3. **Configure Security**: Implement RBAC and network policies
4. **Setup Monitoring**: Deploy observability stack

### For DevOps Teams

1. **CI/CD Integration**: Setup GitHub Actions with OIDC
2. **GitOps Workflows**: Configure ArgoCD deployments
3. **Security Policies**: Implement Pod Security Standards
4. **Disaster Recovery**: Setup backup and recovery procedures

## 🏗️ Best Practices

### 🔒 Security
- Use `ha-dbs-lh` storage class for production databases
- Implement network policies for pod-to-pod communication
- Regular security audits and compliance checks
- Principle of least privilege for RBAC

### 📈 Performance
- Choose appropriate storage classes for workload requirements
- Monitor resource usage and set appropriate limits
- Use horizontal pod autoscaling where applicable
- Optimize container images for faster startup

### 💰 Cost Optimization
- Right-size storage volumes and compute resources
- Use spot instances where appropriate
- Regular cleanup of unused resources
- Monitor and optimize cluster utilization

### 🔧 Operations
- Follow GitOps practices for all deployments
- Implement comprehensive monitoring and alerting
- Document all customizations and configurations
- Regular backup and disaster recovery testing

### 🆘 Getting Help

| Issue Type | Contact Method | Response Time |
|------------|----------------|---------------|
| **Emergency** | Matrix: `#platform-emergency` | Immediate |
| **General Questions** | Matrix: `#kubernetes-help` | Same day |
| **Documentation** | GitHub Issues | 1-2 days |
| **Feature Requests** | GitHub Issues | Weekly review |

### 👥 Team Contacts

- **Platform Team**: Overall cluster management and infrastructure
- **Security Team**: Security policies and compliance  
- **DevOps Team**: CI/CD and deployment automation

### 🔗 Useful Links

- **Cluster Dashboard**: [https://dashboard.dev.itlusions.com](https://dashboard.dev.itlusions.com)
- **Grafana Monitoring**: [https://grafana.dev.itlusions.com](https://grafana.dev.itlusions.com)
- **ArgoCD GitOps**: [https://argocd.dev.itlusions.com](https://argocd.dev.itlusions.com)
- **Keycloak Auth**: [https://sts.itlusions.com](https://sts.itlusions.com)

## 📊 Repository Statistics

![GitHub last commit](https://img.shields.io/github/last-commit/ITlusions/ITL.K8s)
![GitHub issues](https://img.shields.io/github/issues/ITlusions/ITL.K8s)
![GitHub pull requests](https://img.shields.io/github/issues-pr/ITlusions/ITL.K8s)
![GitHub stars](https://img.shields.io/github/stars/ITlusions/ITL.K8s)

---

## 📜 License

This documentation is maintained by the **ITlusions Platform Team**.

**Last Updated**: September 14, 2025 | **Version**: 1.0 | **Status**: 🟢 Active

---

> 💡 **Tip**: Bookmark this README and the [Documentation Index](docs/index.md) for quick access to all Kubernetes resources!

*Happy Kubernetes-ing! 🚢*