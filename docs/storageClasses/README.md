# Kubernetes Storage Classes Documentation

This directory contains documentation for all storage classes available in the ITL Kubernetes cluster.

## Overview

Storage classes define different types of storage that can be dynamically provisioned for applications. Each storage class has specific characteristics, performance profiles, and use cases.

## Available Storage Classes

### Production Storage Classes

#### 1. **ha-dbs-lh** - High Availability Database Storage
- **File**: `ha-dbs-lh.yaml`
- **Purpose**: Production database storage with high availability
- **Provisioner**: Longhorn (driver.longhorn.io)
- **Replicas**: 3 (across different nodes)
- **Reclaim Policy**: Retain (data preserved even if PVC deleted)
- **Volume Expansion**: ✅ Supported
- **Use Cases**: 
  - PostgreSQL databases (like CNPG clusters)
  - MySQL/MariaDB production instances
  - MongoDB replica sets
  - Any critical database requiring data persistence

#### 2. **longhorn** - Default Distributed Storage
- **File**: `longhorn.yaml`
- **Purpose**: General-purpose distributed storage (cluster default)
- **Provisioner**: Longhorn (driver.longhorn.io)
- **Replicas**: 3 (across different nodes)
- **Reclaim Policy**: Delete
- **Volume Expansion**: ✅ Supported
- **Use Cases**:
  - Application data volumes
  - Non-critical databases
  - General persistent storage needs
  - Default choice for most workloads

### Specialized Storage Classes

#### 3. **minio-data** - Object Storage
- **File**: `minio-data.yaml`
- **Purpose**: Optimized for MinIO object storage
- **Provisioner**: OpenEBS Local (openebs.io/local)
- **Path**: `/mnt/data-lv-01/minio`
- **Reclaim Policy**: Delete
- **Volume Expansion**: ❌ Not supported
- **Use Cases**:
  - MinIO tenant data storage
  - Object storage workloads
  - Large file storage

#### 4. **nfs-csi** - Network File System
- **File**: `nfs-csi.yaml`
- **Purpose**: Shared network storage
- **Provisioner**: NFS CSI (nfs.csi.k8s.io)
- **Server**: 10.99.100.3
- **Share**: `/mnt/data-lv-01`
- **Protocol**: NFSv4.1
- **Volume Expansion**: ❌ Not supported
- **Use Cases**:
  - Shared configuration files
  - Multi-pod read/write access
  - Legacy applications requiring NFS

### Local Storage Classes

#### 5. **openebs-hostpath** - Local Node Storage (Default)
- **File**: `openebs-hostpath.yaml`
- **Purpose**: Fast local storage on each node
- **Provisioner**: OpenEBS Local (openebs.io/local)
- **Path**: `/var/openebs/local`
- **Binding**: WaitForFirstConsumer
- **Volume Expansion**: ❌ Not supported
- **Use Cases**:
  - High-performance applications
  - Temporary storage
  - Single-node applications
  - Cache volumes

#### 6. **longhorn-static** - Simplified Longhorn
- **File**: `longhorn-static.yaml`
- **Purpose**: Basic Longhorn storage with minimal config
- **Provisioner**: Longhorn (driver.longhorn.io)
- **Reclaim Policy**: Delete
- **Volume Expansion**: ✅ Supported
- **Use Cases**:
  - Simple distributed storage needs
  - Pre-provisioned volumes
  - Basic application storage

#### 7. **local-storage** - Manual Provisioning
- **File**: `local-storage.yaml`
- **Purpose**: Manually managed local volumes
- **Provisioner**: None (kubernetes.io/no-provisioner)
- **Binding**: WaitForFirstConsumer
- **Volume Expansion**: ❌ Not supported
- **Use Cases**:
  - Pre-allocated hardware storage
  - Specific node storage requirements
  - Manual storage management

## Storage Class Selection Guide

### For Databases 🗄️
- **Production**: Use `ha-dbs-lh` for critical databases
- **Development**: Use `longhorn` for non-critical databases
- **High Performance**: Use `openebs-hostpath` for single-node DBs

### For Applications 📱
- **General Use**: Use `longhorn` (default)
- **High Performance**: Use `openebs-hostpath` 
- **Shared Data**: Use `nfs-csi`

### For Object Storage 🗂️
- **MinIO**: Use `minio-data`
- **General Objects**: Use `longhorn`

### For Temporary Storage ⏱️
- **Fast Temporary**: Use `openebs-hostpath`
- **Distributed Temporary**: Use `longhorn`

## Performance Characteristics

| Storage Class | Latency | Throughput | Availability | Durability |
|---------------|---------|------------|--------------|------------|
| ha-dbs-lh | Medium | High | Very High | Very High |
| longhorn | Medium | High | High | High |
| longhorn-static | Medium | High | High | High |
| minio-data | Low | Very High | Medium | Medium |
| nfs-csi | High | Medium | High | High |
| openebs-hostpath | Very Low | Very High | Low | Low |
| local-storage | Very Low | Very High | Low | Low |

## Volume Binding Modes

- **Immediate**: Volume is created immediately when PVC is created
- **WaitForFirstConsumer**: Volume creation waits until pod is scheduled

## Reclaim Policies

- **Delete**: PersistentVolume is deleted when PVC is deleted
- **Retain**: PersistentVolume is preserved even after PVC deletion (manual cleanup required)

## Best Practices

### For Production Workloads
1. Use `ha-dbs-lh` for critical databases
2. Use `longhorn` for general application storage
3. Always specify resource limits and requests
4. Monitor storage usage and performance

### For Development
1. Use `longhorn` or `openebs-hostpath` for most cases
2. Consider cleanup policies for temporary environments
3. Use appropriate storage sizes to avoid waste

### For Backup and Disaster Recovery
1. `ha-dbs-lh` with Retain policy for critical data
2. Regular backups regardless of storage class
3. Test restore procedures periodically

## Troubleshooting

### Common Issues
1. **PVC Pending**: Check storage class availability and node resources
2. **Volume Mount Failures**: Verify node labels and storage class parameters
3. **Performance Issues**: Consider storage class characteristics and node resources

### Monitoring
- Monitor PV/PVC status: `kubectl get pv,pvc -A`
- Check storage class details: `kubectl describe storageclass <name>`
- View storage usage: `kubectl top nodes`

## Examples

### Database PVC Example
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: ha-dbs-lh
  resources:
    requests:
      storage: 10Gi
```

### Application PVC Example
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 5Gi
```

---

**Last Updated**: September 14, 2025
**Cluster**: ITL Kubernetes Infrastructure
**Documentation Version**: 1.0