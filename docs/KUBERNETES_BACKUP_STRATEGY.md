# Kubernetes Backup Strategy for Upgrade Protection

## 🎯 Overview

This guide provides comprehensive backup strategies to protect your Kubernetes cluster from failed upgrades, ensuring you can quickly recover to a working state.

## 📋 Pre-Upgrade Backup Checklist

### 1. **etcd Backup (Critical - Most Important)**
```bash
# Create etcd snapshot
ETCDCTL_API=3 etcdctl snapshot save backup.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt \
  --key=/etc/kubernetes/pki/etcd/healthcheck-client.key

# Verify snapshot
ETCDCTL_API=3 etcdctl --write-out=table snapshot status backup.db
```

### 2. **Cluster Configuration Backup**
```bash
# Backup all cluster resources (Linux/MacOS)
kubectl get all --all-namespaces -o yaml > cluster-backup-$(date +%Y%m%d-%H%M%S).yaml

# PowerShell equivalent (Windows)
kubectl get all --all-namespaces -o yaml > "cluster-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').yaml"

# Backup specific critical resources
kubectl get nodes -o yaml > nodes-backup.yaml
kubectl get pv -o yaml > pv-backup.yaml
kubectl get pvc --all-namespaces -o yaml > pvc-backup.yaml
kubectl get configmaps --all-namespaces -o yaml > configmaps-backup.yaml
kubectl get secrets --all-namespaces -o yaml > secrets-backup.yaml
kubectl get ingress --all-namespaces -o yaml > ingress-backup.yaml

# Backup CRDs
kubectl get crd -o yaml > crds-backup.yaml
```

### 3. **Kubernetes Configuration Files Backup**
```bash
# Backup kubeconfig
cp ~/.kube/config ~/.kube/config-backup-$(date +%Y%m%d)

# Backup cluster certificates (on control plane nodes)
sudo cp -r /etc/kubernetes/pki /root/kubernetes-pki-backup-$(date +%Y%m%d)

# Backup kubelet config
sudo cp /var/lib/kubelet/config.yaml /root/kubelet-config-backup-$(date +%Y%m%d).yaml
```

## 🔧 Automated Backup Scripts

### Complete Pre-Upgrade Backup Script
```bash
#!/bin/bash
# backup-kubernetes.sh

set -e

BACKUP_DIR="/backup/k8s-$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR

echo "Starting Kubernetes backup to $BACKUP_DIR"

# 1. etcd backup (most critical)
echo "Backing up etcd..."
ETCDCTL_API=3 etcdctl snapshot save $BACKUP_DIR/etcd-backup.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt \
  --key=/etc/kubernetes/pki/etcd/healthcheck-client.key

# 2. Cluster resources
echo "Backing up cluster resources..."
kubectl get all --all-namespaces -o yaml > $BACKUP_DIR/all-resources.yaml
kubectl get nodes -o yaml > $BACKUP_DIR/nodes.yaml
kubectl get pv -o yaml > $BACKUP_DIR/persistent-volumes.yaml
kubectl get pvc --all-namespaces -o yaml > $BACKUP_DIR/persistent-volume-claims.yaml
kubectl get crd -o yaml > $BACKUP_DIR/custom-resources.yaml
kubectl get configmaps --all-namespaces -o yaml > $BACKUP_DIR/configmaps.yaml
kubectl get secrets --all-namespaces -o yaml > $BACKUP_DIR/secrets.yaml

# 3. Configuration files
echo "Backing up configuration files..."
cp ~/.kube/config $BACKUP_DIR/kubeconfig
sudo cp -r /etc/kubernetes/pki $BACKUP_DIR/kubernetes-pki
sudo cp /var/lib/kubelet/config.yaml $BACKUP_DIR/kubelet-config.yaml

# 4. Application-specific backups
echo "Backing up application configs..."
kubectl get -n istio-system all -o yaml > $BACKUP_DIR/istio-config.yaml
kubectl get -n argocd all -o yaml > $BACKUP_DIR/argocd-config.yaml
kubectl get -n longhorn-system all -o yaml > $BACKUP_DIR/longhorn-config.yaml

# 5. Create backup manifest
cat > $BACKUP_DIR/backup-info.txt << EOF
Kubernetes Backup Information
=============================
Date: $(date)
Kubernetes Version: $(kubectl version --short | grep Server)
Node Count: $(kubectl get nodes --no-headers | wc -l)
Namespace Count: $(kubectl get namespaces --no-headers | wc -l)
Pod Count: $(kubectl get pods --all-namespaces --no-headers | wc -l)

Backup Contents:
- etcd snapshot: etcd-backup.db
- All resources: all-resources.yaml
- Nodes: nodes.yaml
- Persistent Volumes: persistent-volumes.yaml
- PVCs: persistent-volume-claims.yaml
- Custom Resources: custom-resources.yaml
- ConfigMaps: configmaps.yaml
- Secrets: secrets.yaml
- Kubeconfig: kubeconfig
- PKI certificates: kubernetes-pki/
- Kubelet config: kubelet-config.yaml
- Istio config: istio-config.yaml
- ArgoCD config: argocd-config.yaml
- Longhorn config: longhorn-config.yaml
EOF

echo "Backup completed successfully at $BACKUP_DIR"
echo "etcd snapshot verification:"
ETCDCTL_API=3 etcdctl --write-out=table snapshot status $BACKUP_DIR/etcd-backup.db
```

## 🔄 Recovery Procedures

### 1. **etcd Recovery (Complete Cluster Restore)**
```bash
# Stop etcd
sudo systemctl stop etcd

# Restore from snapshot
ETCDCTL_API=3 etcdctl snapshot restore backup.db \
  --name m1 \
  --initial-cluster m1=https://10.240.0.17:2380 \
  --initial-cluster-token etcd-cluster-1 \
  --initial-advertise-peer-urls https://10.240.0.17:2380 \
  --data-dir /var/lib/etcd

# Restart etcd
sudo systemctl start etcd

# Verify cluster
kubectl get nodes
```

### 2. **Selective Resource Recovery**
```bash
# Restore specific resources
kubectl apply -f nodes-backup.yaml
kubectl apply -f pv-backup.yaml
kubectl apply -f pvc-backup.yaml
kubectl apply -f configmaps-backup.yaml
kubectl apply -f secrets-backup.yaml
kubectl apply -f crds-backup.yaml

# Restore namespaced resources
kubectl apply -f ingress-backup.yaml
```

### 3. **Certificate Recovery**
```bash
# Restore PKI certificates (on control plane)
sudo systemctl stop kubelet
sudo rm -rf /etc/kubernetes/pki
sudo cp -r /root/kubernetes-pki-backup-* /etc/kubernetes/pki
sudo systemctl start kubelet
```

## 📊 Storage-Specific Backups

### Longhorn Backup (Your Storage System)
```bash
# Create Longhorn snapshots before upgrade
kubectl create -f - <<EOF
apiVersion: longhorn.io/v1beta1
kind: RecurringJob
metadata:
  name: pre-upgrade-backup
  namespace: longhorn-system
spec:
  cron: "0 2 * * *"
  task: "backup"
  groups:
  - default
  retain: 3
  concurrency: 2
EOF

# Manual snapshot creation
for pv in $(kubectl get pv -o jsonpath='{.items[*].metadata.name}'); do
  kubectl create -f - <<EOF
apiVersion: longhorn.io/v1beta2
kind: Backup
metadata:
  name: pre-upgrade-$pv-$(date +%s)
  namespace: longhorn-system
spec:
  snapshotName: pre-upgrade-snapshot
  volume: $pv
EOF
done
```

### Database Backups (If applicable)
```bash
# PostgreSQL backup (for ArgoCD, etc.)
kubectl exec -n argocd argocd-postgres-0 -- pg_dump -U postgres argocd > argocd-db-backup.sql

# Backup Keycloak database
kubectl exec -n keycloak keycloak-postgres-0 -- pg_dump -U postgres keycloak > keycloak-db-backup.sql
```

## 🛡️ Application-Specific Backup Strategies

### ArgoCD Backup
```bash
# Export ArgoCD applications
argocd app list -o yaml > argocd-applications-backup.yaml

# Export ArgoCD repositories
argocd repo list -o yaml > argocd-repositories-backup.yaml

# Export ArgoCD projects
argocd proj list -o yaml > argocd-projects-backup.yaml
```

### Istio Configuration Backup
```bash
# Export Istio configurations
kubectl get -n istio-system gateway,virtualservice,destinationrule,serviceentry,sidecar,authorizationpolicy,peerauthentication -o yaml > istio-networking-backup.yaml

# Export Istio operators
kubectl get istiooperator -A -o yaml > istio-operators-backup.yaml
```

## ⚡ Quick Recovery Commands

### Emergency Rollback Commands
```bash
# Quick etcd restore (single command)
sudo systemctl stop etcd && \
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-backup.db \
  --data-dir /var/lib/etcd-restore && \
sudo mv /var/lib/etcd /var/lib/etcd-old && \
sudo mv /var/lib/etcd-restore /var/lib/etcd && \
sudo systemctl start etcd

# Quick kubeconfig restore
cp ~/.kube/config-backup-* ~/.kube/config

# Quick certificate restore
sudo cp -r /root/kubernetes-pki-backup-*/* /etc/kubernetes/pki/ && \
sudo systemctl restart kubelet
```

## 📈 Backup Verification Checklist

Before proceeding with upgrade:

- [ ] ✅ etcd snapshot created and verified
- [ ] ✅ All cluster resources exported
- [ ] ✅ PKI certificates backed up
- [ ] ✅ Kubeconfig backed up
- [ ] ✅ Application configurations exported
- [ ] ✅ Database backups completed
- [ ] ✅ Storage snapshots created
- [ ] ✅ Backup files stored in safe location
- [ ] ✅ Recovery procedures tested on staging

## 🔧 Automated Backup with Cron

```bash
# Add to crontab for daily backups
0 2 * * * /usr/local/bin/backup-kubernetes.sh

# Weekly full backup with retention
0 1 * * 0 /usr/local/bin/backup-kubernetes.sh && find /backup -name "k8s-*" -mtime +30 -delete
```

## 🚨 Emergency Recovery Contacts

```
Primary: Kubernetes Admin Team
Secondary: Infrastructure Team  
Escalation: Platform Engineering
```

## 📝 Post-Recovery Verification

After any recovery procedure:

1. **Cluster Health Check**
   ```bash
   kubectl get nodes
   kubectl get pods --all-namespaces
   kubectl get pv,pvc
   ```

2. **Application Health Check**
   ```bash
   kubectl get -n istio-system pods
   kubectl get -n argocd pods
   kubectl get -n longhorn-system pods
   ```

3. **Network Connectivity**
   ```bash
   kubectl exec -it <test-pod> -- nslookup kubernetes.default
   kubectl exec -it <test-pod> -- curl -k https://kubernetes.default/api/v1
   ```

## 🎯 Best Practices

1. **Test Recovery Procedures** regularly on staging clusters
2. **Store Backups** in multiple locations (local + remote)
3. **Document Recovery Times** for SLA planning
4. **Automate Verification** of backup integrity
5. **Keep Backup Scripts** version controlled
6. **Practice Emergency Scenarios** with team

---

> **⚠️ Remember**: etcd backup is the most critical component. Everything else can be recreated, but etcd contains the entire cluster state.