# AMD GPU Support Documentation

## 🎯 Overview

This section provides comprehensive documentation for setting up, configuring, and troubleshooting AMD GPU support in Kubernetes environments using the ROCm stack.

## 📚 Documentation Index

| Document | Description | When to Use |
|----------|-------------|-------------|
| **[AMD GPU Installation Guide](AMD_GPU_INSTALLATION.md)** | Complete installation and configuration guide for AMD GPUs | Setting up GPU support from scratch |
| **[AMD GPU Troubleshooting](AMD_GPU_TROUBLESHOOTING.md)** | Common issues, debugging, and recovery procedures | When GPU workloads fail or behave unexpectedly |

## 🚀 Quick Start

New to AMD GPU on Kubernetes? Follow this sequence:

1. **[Install ROCm drivers](AMD_GPU_INSTALLATION.md#step-1-install-amd-rocm-drivers-on-nodes)** on your GPU nodes
2. **[Configure permissions](AMD_GPU_INSTALLATION.md#step-2-configure-user-groups-and-permissions)** for GPU access
3. **[Deploy device plugin](AMD_GPU_INSTALLATION.md#step-3-install-amd-gpu-device-plugin-for-kubernetes)** to expose GPUs to Kubernetes
4. **[Verify installation](AMD_GPU_INSTALLATION.md#verification-and-testing)** with test workloads
5. **[Monitor and troubleshoot](AMD_GPU_TROUBLESHOOTING.md)** as needed

## ⚠️ Common Issue Alert

**Are you seeing "Could not find cuda drivers" with AMD GPUs?** This means you're using a CUDA-based TensorFlow image instead of ROCm. See the [Container Image Issues section](AMD_GPU_TROUBLESHOOTING.md#container-image-issues) for the solution.

## 🔧 Configuration Summary

### Supported Hardware
- **AMD RX Series**: RX 5000, 6000, 7000 series
- **AMD MI Series**: MI25, MI50, MI60, MI100, MI200 series  
- **AMD APUs**: With integrated graphics

### Software Stack
- **ROCm 6.0+** (recommended 6.3+)
- **Kubernetes 1.26+** (tested with 1.30.x)
- **containerd** or **Docker** runtime
- **Ubuntu 20.04/22.04** or **RHEL/CentOS 8/9**

### Resource Requirements
```yaml
resources:
  limits:
    amd.com/gpu: 1    # Request 1 AMD GPU
  requests:
    amd.com/gpu: 1
```

## 📊 Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GPU Pod       │    │  Device Plugin   │    │   GPU Node      │
│                 │    │                  │    │                 │
│  ┌───────────┐  │    │  ┌────────────┐  │    │  ┌───────────┐  │
│  │    App    │  │◄──►│  │   AMD GPU  │  │◄──►│  │   ROCm    │  │
│  │           │  │    │  │   Plugin   │  │    │  │  Drivers  │  │
│  └───────────┘  │    │  └────────────┘  │    │  └───────────┘  │
│                 │    │                  │    │                 │
│  amd.com/gpu: 1 │    │   Kubernetes     │    │  /dev/kfd       │
└─────────────────┘    │   API Server     │    │  /dev/dri/      │
                       └──────────────────┘    └─────────────────┘
```

## 🔍 Verification Commands

```bash
# Check GPU nodes
kubectl get nodes -l amd.com/gpu

# View GPU resources  
kubectl describe nodes | grep -A 5 -B 5 amd.com/gpu

# Test GPU access
kubectl run gpu-test --image=rocm/tensorflow:latest --limits=amd.com/gpu=1 --rm -it -- rocm-smi
```

## 🚨 Common Issues Quick Reference

| Issue | Quick Check | Solution Link |
|-------|-------------|---------------|
| GPUs not detected | `rocminfo` | [Driver Installation](AMD_GPU_INSTALLATION.md#step-1-install-amd-rocm-drivers-on-nodes) |
| Permission denied | `groups $USER` | [User Groups](AMD_GPU_INSTALLATION.md#step-2-configure-user-groups-and-permissions) |
| Device plugin failing | `kubectl logs -n kube-system -l name=amdgpu-device-plugin-ds` | [Device Plugin Debug](AMD_GPU_TROUBLESHOOTING.md#issue-3-device-plugin-not-detecting-gpus) |
| Pod pending | `kubectl describe pod <name>` | [Scheduling Issues](AMD_GPU_TROUBLESHOOTING.md#issue-5-pod-stuck-in-pending-state) |
| Container GPU access | `kubectl exec <pod> -- rocm-smi` | [Container Access](AMD_GPU_TROUBLESHOOTING.md#issue-4-container-cannot-access-gpu) |

## 💡 Best Practices

### Resource Management
- Always set both requests and limits for GPU resources
- Use ResourceQuotas to prevent GPU resource exhaustion  
- Monitor GPU utilization with `rocm-smi`

### Security
- Run containers with minimal privileges
- Use specific ROCm image versions (avoid `:latest`)
- Regularly update ROCm drivers

### Performance
- Pin GPU workloads to specific nodes with nodeSelector
- Use appropriate batch sizes for GPU memory
- Monitor GPU temperature and throttling

## 🔗 External Resources

- **ROCm Documentation**: [rocm.docs.amd.com](https://rocm.docs.amd.com)
- **AMD GPU Device Plugin**: [github.com/RadeonOpenCompute/k8s-device-plugin](https://github.com/RadeonOpenCompute/k8s-device-plugin)
- **ROCm Container Hub**: [hub.docker.com/u/rocm](https://hub.docker.com/u/rocm)
- **Kubernetes GPU Scheduling**: [kubernetes.io GPU docs](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)

## 🆘 Getting Help

1. **Check troubleshooting guide**: [AMD_GPU_TROUBLESHOOTING.md](AMD_GPU_TROUBLESHOOTING.md)
2. **Run verification scripts** provided in the troubleshooting guide
3. **Collect diagnostic information**:
   ```bash
   # System info
   rocminfo > rocm-info.txt
   rocm-smi > rocm-smi.txt
   
   # Kubernetes info
   kubectl describe nodes > nodes.txt
   kubectl get pods --all-namespaces -o wide > pods.txt
   ```
4. **Open issue** with collected information

---

> **🎯 Success Tip**: Start with a single GPU node and basic workload before scaling to multi-GPU or production deployments.