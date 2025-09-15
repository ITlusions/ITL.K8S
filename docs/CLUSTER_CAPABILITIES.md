# Kubernetes Cluster Capability Matrix

## Overview

Complete hardware and capability analysis of the ITL Kubernetes cluster (v1.30.13) conducted on September 15, 2025.

## Node Hardware Profile

| Node | Type | CPU Model | Cores | Memory | Role | GPU | Architecture |
|------|------|-----------|-------|--------|------|-----|--------------|
| **itl01** | Compute | AMD Ryzen 5 7430U | 12 (6c/12t) | 15 GiB | Worker | AMD Radeon (gfx90c) | x86_64 |
| **itl02** | Compute | AMD Ryzen 5 7430U | 12 (6c/12t) | 15 GiB | Worker | AMD Radeon (gfx90c) | x86_64 |
| **nwa01** | Control | Intel i5-6500T @ 2.50GHz | 4 (4c/4t) | 7.6 GiB | Control Plane | None | x86_64 |
| **nwa02** | Worker | Intel i5-6500T @ 2.50GHz | 4 (4c/4t) | 7.6 GiB | Worker | None | x86_64 |
| **nwa03** | Worker | Intel i5-6500T @ 2.50GHz | 4 (4c/4t) | 7.6 GiB | Worker | None | x86_64 |

## Detailed Node Specifications

### ITL01 & ITL02 (High Performance Compute Nodes)
- **CPU**: AMD Ryzen 5 7430U with Radeon Graphics (Zen 3+ architecture)
- **Specs**: 6 cores, 12 threads, 2.50-4.38 GHz (dynamic scaling)
- **Cache**: L1d=192 KiB, L1i=192 KiB, L2=3 MiB, L3=16 MiB
- **Memory**: 15 GiB system RAM
- **GPU**: AMD Radeon RX Vega 7 (gfx90c architecture)
- **Features**: AMD-V virtualization, advanced instruction sets (AVX2, AES, etc.)
- **Role**: GPU-enabled workloads, ML inference, high-performance computing

### NWA01 (Control Plane)
- **CPU**: Intel Core i5-6500T @ 2.50GHz (Skylake architecture, 6th gen)
- **Specs**: 4 cores, 4 threads, 0.8-3.1 GHz (dynamic scaling)
- **Cache**: L1d=128 KiB, L1i=128 KiB, L2=1 MiB, L3=6 MiB
- **Memory**: 7.6 GiB system RAM
- **GPU**: None (integrated graphics)
- **Features**: Intel VT-x virtualization, hardware security features
- **Role**: Kubernetes control plane (etcd, API server, scheduler, controller manager)

### NWA02 & NWA03 (Standard Worker Nodes)
- **CPU**: Intel Core i5-6500T @ 2.50GHz (Skylake architecture, 6th gen)
- **Specs**: 4 cores, 4 threads, 0.8-3.1 GHz (dynamic scaling)
- **Cache**: L1d=128 KiB, L1i=128 KiB, L2=1 MiB, L3=6 MiB
- **Memory**: 7.6 GiB system RAM
- **GPU**: None (integrated graphics)
- **Features**: Intel VT-x virtualization, hardware security features
- **Role**: Standard workloads, CPU-intensive tasks, general purpose computing

## Resource Distribution

### Total Cluster Resources
- **CPU Cores**: 36 total (24 on AMD, 12 on Intel)
- **Memory**: 61.2 GiB total
- **GPU Units**: 2x AMD Radeon (14 compute units total)
- **Architecture**: Mixed AMD Zen3+ and Intel Skylake

### Node Resource Allocation
- **High-Performance (ITL01/02)**: 67% of CPU cores, 49% of memory, 100% of GPU
- **Standard Compute (NWA02/03)**: 22% of CPU cores, 25% of memory
- **Control Plane (NWA01)**: 11% of CPU cores, 12% of memory

## GPU Capabilities

### AMD GPU Configuration
- **Model**: AMD Radeon RX Vega 7 (Mobile)
- **Architecture**: gfx90c (Vega 10 derivative)
- **Compute Units**: 7 per GPU (14 total cluster-wide)
- **ROCm Status**: ⚠️ Limited compatibility (requires ROCm 5.x for full support)
- **Modern ROCm**: ❌ Not supported in ROCm 6.4.2+ (focuses on MI-series and RDNA2/3)
- **Detection**: ✅ Successfully detected by ROCm runtime
- **Device Access**: ⚠️ Permissions required for `/dev/kfd` (requires privileged containers)

### GPU Workload Support
- **AI/ML Frameworks**: Limited (requires legacy ROCm stack)
- **ONNX Runtime**: ❌ Not compatible with modern versions
- **PyTorch**: ⚠️ Requires ROCm 5.x builds
- **TensorFlow**: ⚠️ Limited support with older ROCm versions
- **OpenCL**: ✅ Supported
- **General Compute**: ⚠️ Basic compute tasks supported

## Network and Storage

### Networking
- **CNI**: Flannel (pod-to-pod communication)
- **Pod CIDR**: 10.244.0.0/16
- **Service CIDR**: Standard Kubernetes networking
- **External Access**: Ingress controllers available

### Storage Classes Available
- **Longhorn**: Distributed block storage
- **Local Storage**: Node-local storage classes
- **NFS CSI**: Network file system support
- **OpenEBS**: Cloud native storage
- **Minio**: Object storage for specific use cases

## Workload Recommendations

### High-Performance Workloads (ITL01/02)
- ✅ CPU-intensive applications (12 cores per node)
- ✅ Memory-intensive workloads (15 GiB per node)
- ⚠️ GPU workloads (legacy compatibility required)
- ✅ Parallel processing and batch jobs
- ✅ Development environments with high resource requirements

### Standard Workloads (NWA02/03)
- ✅ Web applications and microservices
- ✅ Database workloads (with storage classes)
- ✅ CI/CD pipelines
- ✅ Monitoring and logging stacks
- ✅ General purpose applications

### Control Plane Considerations (NWA01)
- ✅ Dedicated control plane (no user workloads scheduled)
- ✅ High availability control plane components
- ✅ Sufficient resources for cluster management
- ⚠️ Monitor resource usage under high cluster load

## Node Selectors and Labels

### Correct Labels for Scheduling
```yaml
# GPU Nodes
nodeSelector:
  kubernetes.io/hostname: itl01  # or itl02
  amd.com/gpu.cu-count: "7"      # Correct GPU label

# High CPU Nodes (AMD)
nodeSelector:
  kubernetes.io/arch: amd64
  # Use hostname selector for specific high-performance nodes

# Standard Nodes (Intel)
nodeSelector:
  kubernetes.io/hostname: nwa02  # or nwa03
```

### Ignored/Incorrect Labels
- ❌ `amd.com/gpu.family: vega` (incorrect, ignore this label)
- ❌ Any Vega-specific labels (hardware detection inconsistency)

## Performance Characteristics

### CPU Performance
- **AMD Nodes**: Modern Zen3+ architecture, higher core count, better single/multi-thread performance
- **Intel Nodes**: Older Skylake architecture, solid performance for standard workloads
- **Boost Clocks**: AMD up to 4.38 GHz, Intel up to 3.1 GHz

### Memory Performance
- **AMD Nodes**: Larger memory pools (15 GiB), better for memory-intensive tasks
- **Intel Nodes**: Adequate memory (7.6 GiB) for standard workloads
- **No Swap**: All nodes run without swap (good for Kubernetes)

### Cache Hierarchy
- **AMD**: Larger L3 cache (16 MiB) better for data-intensive workloads
- **Intel**: Standard cache hierarchy, optimized for general purpose computing

## Operational Status

### Current Cluster Health
- ✅ All 5 nodes operational and ready
- ✅ Mixed architecture cluster functioning properly
- ✅ Pod scheduling working across all node types
- ✅ Network connectivity between all nodes
- ✅ Storage classes available and functional

### Resource Utilization (at analysis time)
- **ITL01**: 6.0 GiB / 15 GiB memory used (40%)
- **ITL02**: ~6.0 GiB / 15 GiB memory used (similar load)
- **NWA01**: 5.6 GiB / 7.6 GiB memory used (74% - control plane)
- **NWA02**: 4.8 GiB / 7.6 GiB memory used (63%)
- **NWA03**: 5.0 GiB / 7.6 GiB memory used (66%)

## Deployment Strategies

### For GPU Workloads
1. Use legacy ROCm-compatible images (ROCm 5.x)
2. Ensure privileged container access for GPU device files
3. Target nodes specifically: `itl01` or `itl02`
4. Consider CPU-only alternatives for modern ML frameworks

### For High-Performance CPU Workloads
1. Target AMD nodes for maximum performance: `itl01` or `itl02`
2. Utilize higher core count and memory availability
3. Consider NUMA topology for memory-intensive applications

### For Standard Workloads
1. Use Intel nodes for general applications: `nwa02`, `nwa03`
2. Implement resource requests/limits appropriate for 4-core nodes
3. Consider spreading replicas across both Intel nodes

### For System Services
1. Use standard worker nodes to preserve high-performance nodes
2. Control plane node should remain dedicated (tainted)
3. Consider node affinity for monitoring and logging workloads

## Summary

The ITL Kubernetes cluster provides a **heterogeneous computing environment** with distinct performance tiers:

- **Tier 1**: AMD Ryzen nodes (ITL01/02) - High-performance compute with legacy GPU capability
- **Tier 2**: Intel nodes (NWA02/03) - Standard compute for general workloads  
- **Control**: Intel node (NWA01) - Dedicated control plane

The cluster excels at **CPU-intensive workloads** and provides **adequate GPU support for legacy applications**. Modern AI/ML workloads should consider CPU-only implementations or legacy ROCm compatibility requirements.