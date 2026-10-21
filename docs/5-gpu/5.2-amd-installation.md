# AMD GPU Support on Kubernetes

## 🎯 Overview

This guide provides comprehensive instructions for installing and configuring AMD GPU support on Kubernetes clusters using the ROCm stack. This enables GPU workloads for machine learning, AI, and compute-intensive applications.

## 📋 Prerequisites

### Hardware Requirements
- **AMD GPU**: Supported GPUs (RX 5000/6000/7000 series, MI series, etc.)
- **PCIe 3.0/4.0**: Adequate PCIe bandwidth for GPU communication
- **Memory**: Minimum 8GB system RAM per GPU
- **Power**: Sufficient PSU capacity for GPU(s)

### Software Requirements
- **Ubuntu 24.04.2 LTS** (Noble Numbat)
- **Kernel**: 6.8+ (included with Ubuntu 24.04.2)
- **Kubernetes 1.26+** (tested with 1.30.x)
- **Container Runtime**: containerd (recommended) or Docker
- **Root Access**: Required for driver installation
## 🔧 Installation Steps

### Step 1: Install AMD ROCm Drivers on Ubuntu 24.04.2 LTS

#### System Preparation
```bash
# Update system packages to latest
sudo apt update && sudo apt upgrade -y

# Install prerequisite packages
sudo apt install -y wget gnupg2 software-properties-common

# Verify kernel version (should be 6.8+)
uname -r
```

#### ROCm 6.3 Installation for Ubuntu 24.04.2
```bash
# Download and add ROCm GPG key (modern method, replaces deprecated apt-key)
wget -qO - https://repo.radeon.com/rocm/rocm.gpg.key | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/rocm.gpg > /dev/null

# Add ROCm repository for Ubuntu 24.04 (noble)
echo 'deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/rocm.gpg] https://repo.radeon.com/rocm/apt/6.3/ noble main' | sudo tee /etc/apt/sources.list.d/rocm.list

# Update package index
sudo apt update

# Install ROCm kernel drivers and development tools
sudo apt install -y \
    rocm-dkms \
    rocm-dev \
    rocm-libs \
    rocm-utils \
    rocminfo \
    rocm-smi \
    hip-dev \
    hip-runtime-amd

# Install additional development packages (optional but recommended)
sudo apt install -y \
    rocblas \
    rocfft \
    rocsparse \
    rocrand \
    rocthrust
```

#### Post-Installation Configuration
```bash
# Add ROCm paths to system environment
echo 'export PATH=$PATH:/opt/rocm/bin' | sudo tee -a /etc/environment
echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/rocm/lib' | sudo tee -a /etc/environment

# Create ROCm module load configuration
echo 'amdgpu' | sudo tee /etc/modules-load.d/amdgpu.conf

# Configure AMDGPU driver parameters for optimal performance
echo 'options amdgpu noretry=0' | sudo tee /etc/modprobe.d/amdgpu.conf
echo 'options amdgpu lockup_timeout=1000' | sudo tee -a /etc/modprobe.d/amdgpu.conf

# Update initramfs to include new modules
sudo update-initramfs -u
```

### Step 2: Configure User Groups and Permissions

```bash
# Add current user to required GPU access groups
sudo usermod -aG render,video $USER

# Add kubernetes/container runtime user (if different)
sudo usermod -aG render,video kubernetes

# Verify group memberships
groups $USER

# Set proper permissions for GPU device files (Ubuntu 24.04.2 specific)
sudo udevadm control --reload-rules
sudo udevadm trigger

# Reboot system to ensure all changes take effect
sudo reboot
```

#### Post-Reboot Verification
```bash
# After reboot, verify ROCm installation
rocminfo

# Check GPU status and availability
rocm-smi

# Verify AMDGPU driver is loaded
lsmod | grep amdgpu

# Check GPU device files exist with proper permissions
ls -la /dev/kfd /dev/dri/render*
```

### Step 3: Install AMD GPU Device Plugin for Kubernetes (Ubuntu 24.04.2)

#### Prerequisites Check for Ubuntu 24.04.2
```bash
# Verify Kubernetes version compatibility (requires 1.19+)
kubectl version --client --short

# Check Ubuntu version
lsb_release -a

# Verify ROCm installation
rocminfo | head -5
```

#### Option A: Using Official AMD Device Plugin (Recommended for Ubuntu 24.04.2)
```bash
# Apply the latest AMD GPU device plugin compatible with recent kernels
kubectl apply -f https://raw.githubusercontent.com/RadeonOpenCompute/k8s-device-plugin/master/k8s-ds-amdgpu-dp.yaml

# Wait for device plugin to be ready
kubectl wait --for=condition=Ready pod -l name=amdgpu-device-plugin -n kube-system --timeout=300s

# Verify device plugin deployment
kubectl get pods -n kube-system -l name=amdgpu-device-plugin -o wide
```

#### Option B: Manual Installation with Ubuntu 24.04.2 Optimizations
```bash
# Deploy AMD GPU device plugin with Ubuntu 24.04.2 specific settings
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: amdgpu-device-plugin-daemonset
  namespace: kube-system
  labels:
    app: amdgpu-device-plugin
spec:
  selector:
    matchLabels:
      name: amdgpu-device-plugin-ds
  template:
    metadata:
      labels:
        name: amdgpu-device-plugin-ds
        app: amdgpu-device-plugin
    spec:
      tolerations:
      - key: CriticalAddonsOnly
        operator: Exists
      - effect: NoSchedule
        key: amd.com/gpu
        operator: Exists
      - effect: NoSchedule
        key: node-role.kubernetes.io/control-plane
        operator: Exists
      priorityClassName: system-node-critical
      containers:
      - image: rocm/k8s-device-plugin:latest
        name: amdgpu-device-plugin-ctr
        env:
        # Ubuntu 24.04.2 specific environment variables
        - name: LD_LIBRARY_PATH
          value: "/opt/rocm/lib:/opt/rocm/lib64"
        - name: PATH
          value: "/opt/rocm/bin:/opt/rocm/opencl/bin:$PATH"
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
          runAsNonRoot: false
          runAsUser: 0
        resources:
          requests:
            cpu: 50m
            memory: 10Mi
          limits:
            cpu: 100m
            memory: 50Mi
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
        - name: dev
          mountPath: /dev
        - name: sys
          mountPath: /sys
        - name: proc-modules
          mountPath: /proc/modules
          readOnly: true
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
      - name: dev
        hostPath:
          path: /dev
      - name: sys
        hostPath:
          path: /sys
      - name: proc-modules
        hostPath:
          path: /proc/modules
      nodeSelector:
        kubernetes.io/arch: amd64
        # Only deploy on nodes with AMD GPUs
        feature.node.kubernetes.io/pci-10de.present: "false"
      hostNetwork: true
      hostPID: true
EOF
```

### Step 4: Install Node Feature Discovery (NFD) for Ubuntu 24.04.2

```bash
# Install the latest NFD compatible with Kubernetes 1.28+ and Ubuntu 24.04.2
kubectl apply -k https://github.com/kubernetes-sigs/node-feature-discovery/deployment/overlays/default?ref=v0.15.0

# Create NFD configuration for AMD GPU detection on Ubuntu 24.04.2
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: nfd-worker-config
  namespace: node-feature-discovery
data:
  nfd-worker.conf: |
    core:
      labelWhiteList: "amd.com"
      featureSources: ["pci", "kernel", "system"]
    sources:
      pci:
        deviceClassWhitelist: ["0300", "0302"]
        deviceLabelFields: ["vendor", "device", "subsystem_vendor", "subsystem_device"]
      kernel:
        kconfigFile: "/proc/config.gz"
        configOpts: ["CONFIG_DRM_AMDGPU"]
      system:
        osRelease: [VERSION_ID, ID]
EOF

# Restart NFD to pick up new configuration
kubectl rollout restart daemonset nfd-worker -n node-feature-discovery

# Wait for NFD to be ready
kubectl wait --for=condition=Ready pod -l app=nfd-worker -n node-feature-discovery --timeout=120s

# Verify NFD is running and detecting features
kubectl get pods -n node-feature-discovery -o wide
kubectl logs -n node-feature-discovery -l app=nfd-worker --tail=50
```

### Step 5: Configure Container Runtime for GPU Support (Ubuntu 24.04.2)

#### For containerd (Recommended for Ubuntu 24.04.2)
```bash
# Backup existing containerd configuration
sudo cp /etc/containerd/config.toml /etc/containerd/config.toml.backup

# Generate default configuration for containerd 1.7+ (included with Ubuntu 24.04.2)
containerd config default | sudo tee /etc/containerd/config.toml

# Configure containerd for systemd cgroup driver (required for Kubernetes)
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

# Ensure proper sandbox image for Ubuntu 24.04.2
sudo sed -i 's|registry.k8s.io/pause:3.6|registry.k8s.io/pause:3.9|' /etc/containerd/config.toml

# Add GPU device access configuration
sudo tee -a /etc/containerd/config.toml <<EOF

# AMD GPU specific configuration
[plugins."io.containerd.grpc.v1.cri".containerd]
  default_runtime_name = "runc"

[plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runc.options]
  BinaryName = "/usr/bin/runc"
  SystemdCgroup = true

# Allow privileged containers for GPU access
[plugins."io.containerd.grpc.v1.cri"]
  enable_selinux = false
  sandbox_image = "registry.k8s.io/pause:3.9"
EOF

# Restart and enable containerd
sudo systemctl restart containerd
sudo systemctl enable containerd
```

#### Container Runtime Verification
```bash
# Check containerd status
sudo systemctl status containerd

# Test container runtime with ROCm
sudo ctr run --rm -t --device /dev/kfd --device /dev/dri/renderD128 docker.io/rocm/rocm-terminal:latest rocm-test rocminfo
```

## 🔍 Verification and Testing (Ubuntu 24.04.2)

### Step 6: Verify GPU Detection and Node Labels
```bash
# Check if nodes have GPU labels after NFD processing
kubectl get nodes -o json | jq '.items[] | select(.metadata.labels | has("feature.node.kubernetes.io/pci-1002.present")) | .metadata.name'

# View all AMD-related labels on GPU nodes
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, labels: (.metadata.labels | to_entries | map(select(.key | contains("amd") or contains("gpu"))) | from_entries)}'

# Expected labels for Ubuntu 24.04.2 with ROCm 6.3:
# "amd.com/gpu": "1" or higher
# "feature.node.kubernetes.io/pci-1002.present": "true"
# "feature.node.kubernetes.io/system-os_release.VERSION_ID": "24.04"
```

### Step 7: Check GPU Resources and Allocation
```bash
# View detailed GPU resources on nodes
kubectl describe nodes | grep -A 10 -B 5 "amd.com/gpu"

# Check GPU resource allocation across cluster
kubectl get nodes -o custom-columns="NODE:.metadata.name,GPU-CAPACITY:.status.capacity.amd\.com/gpu,GPU-ALLOCATABLE:.status.allocatable.amd\.com/gpu"

# Verify GPU device plugin is exposing resources
kubectl top node --show-capacity
```

### Step 8: Deploy Comprehensive Test Pod for Ubuntu 24.04.2
```bash
# Create advanced GPU test pod with Ubuntu 24.04.2 optimizations
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: amd-gpu-test-ubuntu2404
  labels:
    purpose: gpu-test
    os: ubuntu-24-04
spec:
  nodeSelector:
    kubernetes.io/arch: amd64
    feature.node.kubernetes.io/pci-1002.present: "true"
  containers:
  - name: rocm-test
    image: rocm/tensorflow:rocm6.3-tf2.16-dev
    command: ["/bin/bash", "-c"]
    args:
    - |
      echo "=== Ubuntu 24.04.2 AMD GPU Test Started ==="
      echo "Container OS Info:"
      cat /etc/os-release | grep -E "(ID|VERSION)"
      
      echo "=== ROCm Installation Verification ==="
      rocminfo | head -20
      
      echo "=== GPU Hardware Detection ==="
      rocm-smi --showid --showproductname --showvoltage --showpower
      
      echo "=== HIP Runtime Test ==="
      /opt/rocm/bin/hipconfig --full
      
      echo "=== Device Accessibility ==="
      ls -la /dev/dri/
      ls -la /dev/kfd
      
      echo "=== ROCm Library Paths ==="
      find /opt/rocm -name "*.so" | head -10
      
      echo "=== TensorFlow GPU Test ==="
      python3 -c "
      import tensorflow as tf
      print('TensorFlow version:', tf.__version__)
      print('GPU devices:', tf.config.list_physical_devices('GPU'))
      if tf.config.list_physical_devices('GPU'):
          print('GPU is available and accessible!')
          with tf.device('/GPU:0'):
              a = tf.constant([[1.0, 2.0], [3.0, 4.0]])
              b = tf.constant([[1.0, 1.0], [0.0, 1.0]])
              c = tf.matmul(a, b)
              print('Matrix multiplication result:', c.numpy())
      else:
          print('No GPU devices found!')
      "
      
      echo "=== Test Complete - Container staying alive ==="
      sleep infinity
    env:
    - name: HIP_VISIBLE_DEVICES
      value: "0"
    - name: ROCR_VISIBLE_DEVICES
      value: "0"
    - name: HSA_OVERRIDE_GFX_VERSION
      value: "10.3.0"  # Adjust based on your GPU
    - name: LD_LIBRARY_PATH
      value: "/opt/rocm/lib:/opt/rocm/lib64"
    resources:
      limits:
        amd.com/gpu: 1
        memory: 8Gi
        cpu: 2
      requests:
        amd.com/gpu: 1
        memory: 4Gi
        cpu: 1
    securityContext:
      privileged: true
    volumeMounts:
    - name: dev-dri
      mountPath: /dev/dri
    - name: dev-kfd
      mountPath: /dev/kfd
    - name: sys-class-drm
      mountPath: /sys/class/drm
      readOnly: true
  volumes:
  - name: dev-dri
    hostPath:
      path: /dev/dri
  - name: dev-kfd
    hostPath:
      path: /dev/kfd
  - name: sys-class-drm
    hostPath:
      path: /sys/class/drm
  restartPolicy: Never
EOF

# Monitor pod startup (may take several minutes to download ROCm image)
kubectl get pod amd-gpu-test-ubuntu2404 -w

# Check pod logs once running
kubectl logs amd-gpu-test-ubuntu2404 -f

# Interactive testing (once pod is running)
kubectl exec -it amd-gpu-test-ubuntu2404 -- /bin/bash

# Cleanup test pod
kubectl delete pod amd-gpu-test-ubuntu2404
```

## 🛠️ Advanced Configuration for Ubuntu 24.04.2

### GPU Node Management and Optimization

#### Add GPU Taints and Labels for Ubuntu 24.04.2
```bash
# Identify GPU nodes
GPU_NODES=$(kubectl get nodes -o json | jq -r '.items[] | select(.status.allocatable."amd.com/gpu") | .metadata.name')

for node in $GPU_NODES; do
  echo "Configuring GPU node: $node"
  
  # Add Ubuntu 24.04.2 specific labels
  kubectl label nodes $node gpu-type=amd --overwrite
  kubectl label nodes $node gpu-driver=rocm-6.3 --overwrite
  kubectl label nodes $node os-version=ubuntu-24.04.2 --overwrite
  kubectl label nodes $node kernel-version=$(kubectl get node $node -o jsonpath='{.status.nodeInfo.kernelVersion}') --overwrite
  
  # Optional: Taint GPU nodes (prevents non-GPU pods from scheduling)
  kubectl taint nodes $node amd.com/gpu=true:NoSchedule --overwrite
done
```

#### Configure GPU Resource Limits for Ubuntu 24.04.2
```bash
# Create ResourceQuota for GPU namespace
kubectl create namespace gpu-workloads --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f - <<EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
  namespace: gpu-workloads
spec:
  hard:
    requests.amd.com/gpu: "4"  # Adjust based on your cluster
    limits.amd.com/gpu: "4"
    requests.memory: "32Gi"
    limits.memory: "64Gi"
EOF
```

### Advanced Resource Management for Ubuntu 24.04.2

```yaml
# GPU Resource Quota optimized for Ubuntu 24.04.2
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota-ubuntu2404
  namespace: gpu-workloads
spec:
  hard:
    requests.amd.com/gpu: "4"
    limits.amd.com/gpu: "4"
    requests.memory: "32Gi"
    limits.memory: "64Gi"
    requests.cpu: "16"
    limits.cpu: "32"

---
# Limit Range for GPU pods on Ubuntu 24.04.2
apiVersion: v1
kind: LimitRange
metadata:
  name: gpu-limit-range-ubuntu2404
  namespace: gpu-workloads
spec:
  limits:
  - default:
      amd.com/gpu: "1"
      memory: "8Gi"
      cpu: "4"
    defaultRequest:
      amd.com/gpu: "1"
      memory: "4Gi"
      cpu: "2"
    type: Container
    max:
      amd.com/gpu: "2"
      memory: "16Gi"
      cpu: "8"
    min:
      amd.com/gpu: "1"
      memory: "2Gi"
      cpu: "1"
```

### Multi-GPU Configuration for Ubuntu 24.04.2

```yaml
# Multi-GPU Pod Example optimized for Ubuntu 24.04.2
apiVersion: v1
kind: Pod
metadata:
  name: multi-gpu-workload-ubuntu2404
  namespace: gpu-workloads
  labels:
    os: ubuntu-24.04.2
    gpu-config: multi-amd
spec:
  nodeSelector:
    os-version: ubuntu-24.04.2
    gpu-type: amd
  tolerations:
  - key: amd.com/gpu
    operator: Exists
    effect: NoSchedule
  containers:
  - name: ml-training-rocm6
    image: rocm/pytorch:rocm6.3-py3.10-pytorch2.4.0
    resources:
      limits:
        amd.com/gpu: "2"  # Request 2 GPUs
        memory: "16Gi"
        cpu: "8"
      requests:
        amd.com/gpu: "2"
        memory: "8Gi"
        cpu: "4"
    env:
    - name: HIP_VISIBLE_DEVICES
      value: "0,1"  # Make both GPUs visible
    - name: ROCR_VISIBLE_DEVICES
      value: "0,1"
    - name: HSA_OVERRIDE_GFX_VERSION
      value: "10.3.0"  # Adjust based on your GPU generation
    - name: LD_LIBRARY_PATH
      value: "/opt/rocm/lib:/opt/rocm/lib64"
    - name: PATH
      value: "/opt/rocm/bin:/opt/rocm/opencl/bin:$PATH"
    securityContext:
      privileged: true
    volumeMounts:
    - name: dev-dri
      mountPath: /dev/dri
    - name: dev-kfd
      mountPath: /dev/kfd
  volumes:
  - name: dev-dri
    hostPath:
      path: /dev/dri
  - name: dev-kfd
    hostPath:
      path: /dev/kfd
```

## 🔧 Container Images for AMD GPU Workloads (Ubuntu 24.04.2 Compatible)

### Official ROCm 6.3 Images (Ubuntu 24.04.2 Compatible)
```bash
# TensorFlow with ROCm 6.3 (latest for Ubuntu 24.04.2)
docker pull rocm/tensorflow:rocm6.3-tf2.16-dev

# PyTorch with ROCm 6.3 (optimized for Ubuntu 24.04.2)
docker pull rocm/pytorch:rocm6.3-py3.10-pytorch2.4.0

# ROCm Development (Ubuntu 24.04 base)
docker pull rocm/dev-ubuntu-24.04:latest

# ROCm Terminal for testing
docker pull rocm/rocm-terminal:rocm6.3

# Specific stable versions for production
docker pull rocm/tensorflow:rocm6.3-tf2.16-runtime
docker pull rocm/pytorch:rocm6.3-py3.11-pytorch2.4.0
```

### Custom Image Example for Ubuntu 24.04.2
```dockerfile
# Dockerfile for custom ROCm application on Ubuntu 24.04.2
FROM rocm/dev-ubuntu-24.04:latest

    # Update package lists and install Ubuntu 24.04.2 compatible packages
    RUN apt-get update && apt-get install -y \
        python3.12 \
        python3.12-dev \
        python3.12-pip \
        build-essential \
        cmake \
        git \
        wget \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Install Python packages compatible with Ubuntu 24.04.2
RUN python3.12 -m pip install --upgrade pip setuptools wheel
RUN python3.12 -m pip install \
        torch==2.4.0+rocm6.1 \
        torchvision==0.19.0+rocm6.1 \
        tensorflow-rocm==2.16.1 \
        --extra-index-url https://download.pytorch.org/whl/rocm6.1

# Set Ubuntu 24.04.2 specific environment
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH="/opt/rocm/lib/python3.12/site-packages:$PYTHONPATH"
ENV LD_LIBRARY_PATH="/opt/rocm/lib:/opt/rocm/lib64:$LD_LIBRARY_PATH"
ENV PATH="/opt/rocm/bin:/opt/rocm/opencl/bin:$PATH"

# Ubuntu 24.04.2 specific ROCm library verification
RUN ldconfig && rocminfo
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages with ROCm support
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.0

# Copy application code
COPY . /app
WORKDIR /app

# Set ROCm environment
ENV ROCR_VISIBLE_DEVICES=0
ENV HIP_VISIBLE_DEVICES=0

CMD ["python3", "app.py"]
```

## 📊 Monitoring and Troubleshooting

### GPU Monitoring Commands

```bash
# Check GPU utilization
kubectl exec <pod-name> -- rocm-smi

# Detailed GPU information
kubectl exec <pod-name> -- rocminfo

# Check HIP runtime
kubectl exec <pod-name> -- hipconfig --check

# Monitor GPU metrics continuously
watch -n 1 'kubectl exec <pod-name> -- rocm-smi'
```

### Common Issues and Solutions

#### Issue 1: GPUs Not Detected
```bash
# Check if ROCm drivers are loaded
lsmod | grep amdgpu

# Verify GPU visibility
ls -la /dev/kfd /dev/dri/render*

# Check permissions
groups $USER | grep -E 'render|video'
```

#### Issue 2: Device Plugin Not Starting
```bash
# Check device plugin logs
kubectl logs -n kube-system -l name=amdgpu-device-plugin-ds

# Verify kubelet device plugin directory
ls -la /var/lib/kubelet/device-plugins/

# Check for socket file
ls -la /var/lib/kubelet/device-plugins/amd.com-gpu.*
```

#### Issue 3: Pod Fails to Schedule
```bash
# Check node resources
kubectl describe nodes | grep -A 10 -B 5 amd.com/gpu

# Verify taints and tolerations
kubectl describe node <node-name> | grep -A 5 -B 5 Taints

# Check resource requests vs availability
kubectl top nodes
```

### Prometheus Monitoring (Optional)

```yaml
# ServiceMonitor for GPU metrics
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: amd-gpu-metrics
spec:
  selector:
    matchLabels:
      app: amd-gpu-exporter
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

```

## 🎯 Best Practices for Ubuntu 24.04.2

### 1. **Resource Management on Ubuntu 24.04.2**
- Always set both requests and limits for GPU resources with kernel 6.8+ compatibility
- Use ResourceQuotas to prevent GPU resource exhaustion on multi-tenant clusters
- Monitor GPU utilization with ROCm 6.3 tools to optimize allocation
- Consider memory constraints with Ubuntu 24.04.2's improved memory management

### 2. **Security for Ubuntu 24.04.2**
- Leverage Ubuntu 24.04.2's enhanced security features with AppArmor profiles
- Run GPU containers with minimal privileges using Ubuntu's user namespaces
- Use securityContexts to drop unnecessary capabilities in kernel 6.8+
- Regularly update ROCm 6.3 drivers and container images for Ubuntu 24.04.2 security patches
- Implement proper SELinux policies if enabled

### 3. **Performance Optimization for Ubuntu 24.04.2**
```yaml
# Performance-optimized pod configuration for Ubuntu 24.04.2
apiVersion: v1
kind: Pod
metadata:
  name: optimized-gpu-pod-ubuntu2404
  labels:
    performance: optimized
    os: ubuntu-24.04.2
spec:
  nodeSelector:
    os-version: ubuntu-24.04.2
    kernel-version: "6.8+"
    gpu-type: amd
  containers:
  - name: ml-workload-rocm6
    image: rocm/pytorch:rocm6.3-py3.11-pytorch2.4.0
    resources:
      limits:
        amd.com/gpu: 1
        memory: "16Gi"
        cpu: "8"
      requests:
        amd.com/gpu: 1
        memory: "8Gi"  
        cpu: "4"
    env:
    - name: HIP_VISIBLE_DEVICES
      value: "0"
    - name: ROCR_VISIBLE_DEVICES  
      value: "0"
    - name: HCC_AMDGPU_TARGET
      value: "gfx906,gfx908,gfx90a,gfx1030,gfx1100,gfx1101"  # Include newer architectures
    - name: HSA_OVERRIDE_GFX_VERSION
      value: "10.3.0"  # For compatibility with older software
    - name: LD_LIBRARY_PATH
      value: "/opt/rocm/lib:/opt/rocm/lib64"
    # Ubuntu 24.04.2 specific optimizations
    - name: OMP_NUM_THREADS
      value: "4"
    - name: PYTORCH_HIP_ALLOC_CONF
      value: "backend:native"
    securityContext:
      privileged: true
      capabilities:
        add: ["SYS_PTRACE"]  # Required for ROCm profiling on Ubuntu 24.04.2
    volumeMounts:
    - name: dev-dri
      mountPath: /dev/dri
    - name: dev-kfd
      mountPath: /dev/kfd
    - name: tmp-shm
      mountPath: /dev/shm
  volumes:
  - name: dev-dri
    hostPath:
      path: /dev/dri
  - name: dev-kfd
    hostPath:
      path: /dev/kfd
  - name: tmp-shm
    emptyDir:
      medium: Memory
      sizeLimit: "2Gi"
```

### 4. **Monitoring and Maintenance for Ubuntu 24.04.2**
- Set up ROCm-SMI based monitoring compatible with kernel 6.8+
- Use Ubuntu 24.04.2's systemd journal for centralized logging
- Implement health checks for GPU device accessibility
- Monitor for Ubuntu 24.04.2 security updates affecting ROCm

### 5. **Troubleshooting Common Issues on Ubuntu 24.04.2**

#### GPU Not Detected After Ubuntu 24.04.2 Upgrade
```bash
# Verify AMDGPU driver is loaded in kernel 6.8+
lsmod | grep amdgpu

# Check dmesg for GPU initialization errors
dmesg | grep -i amd

# Verify ROCm 6.3 compatibility with kernel 6.8+
rocminfo | head -10

# Reinstall ROCm if needed
sudo apt remove rocm-dev rocm-utils
sudo apt autoremove
# Then reinstall following Step 2 instructions
```

#### Device Plugin Not Starting on Ubuntu 24.04.2
```bash
# Check device plugin logs
kubectl logs -n kube-system -l name=amdgpu-device-plugin --tail=100

# Verify containerd configuration for Ubuntu 24.04.2
sudo systemctl status containerd
sudo journalctl -u containerd --since "1 hour ago"

# Check for AppArmor conflicts (Ubuntu 24.04.2 specific)
sudo aa-status | grep containerd
```

#### Performance Issues on Ubuntu 24.04.2
```bash
# Check GPU memory utilization with ROCm 6.3
rocm-smi --showmeminfo --json

# Monitor GPU temperature and power
rocm-smi --showtemp --showpower --json

# Check for thermal throttling in kernel 6.8+
dmesg | grep -i thermal

# Verify Ubuntu 24.04.2 CPU governor settings
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
```

## 📚 Additional Resources for Ubuntu 24.04.2

- [ROCm 6.3 Installation Guide](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/)
- [Ubuntu 24.04.2 LTS Release Notes](https://wiki.ubuntu.com/NobleNumbat/ReleaseNotes)
- [Kubernetes GPU Support Documentation](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [AMD GPU Device Plugin Repository](https://github.com/RadeonOpenCompute/k8s-device-plugin)
- [Ubuntu 24.04.2 Kernel 6.8 Changes](https://kernelnewbies.org/Linux_6.8)

## 🏁 Summary

This guide provides comprehensive instructions for installing AMD GPU support in Kubernetes on Ubuntu 24.04.2 LTS with ROCm 6.3. Key components include:

1. **ROCm 6.3 Driver Installation** - Compatible with Ubuntu 24.04.2 and kernel 6.8+
2. **Container Runtime Configuration** - Optimized containerd setup for GPU access
3. **Device Plugin Deployment** - AMD GPU device plugin with Ubuntu 24.04.2 optimizations
4. **Verification and Testing** - Comprehensive validation procedures
5. **Best Practices** - Ubuntu 24.04.2 specific recommendations for production use

Follow the troubleshooting section if you encounter issues specific to Ubuntu 24.04.2's kernel 6.8+ or ROCm 6.3 compatibility.
    amd.com/gpu: "true"
  tolerations:
  - key: amd.com/gpu
    operator: Exists
    effect: NoSchedule
```

### 4. **Maintenance**
- Regularly update device plugin versions
- Monitor for ROCm driver updates
- Test GPU workloads after Kubernetes upgrades

## 🔗 Useful Commands Reference

```bash
# Quick GPU status check
kubectl get nodes -l amd.com/gpu -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.amd\.com/gpu

# List all GPU pods
kubectl get pods --all-namespaces -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,GPU:.spec.containers[*].resources.requests.amd\.com/gpu

# GPU resource usage
kubectl top nodes --selector=amd.com/gpu

# Debug GPU pod scheduling
kubectl describe pod <gpu-pod-name> | grep -A 20 Events
```

## 📚 Additional Resources

- **ROCm Documentation**: [https://rocm.docs.amd.com](https://rocm.docs.amd.com)
- **AMD GPU Kubernetes Plugin**: [https://github.com/RadeonOpenCompute/k8s-device-plugin](https://github.com/RadeonOpenCompute/k8s-device-plugin)
- **ROCm Container Images**: [https://hub.docker.com/u/rocm](https://hub.docker.com/u/rocm)
- **Kubernetes GPU Support**: [https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)

---

> **💡 Tip**: Always test GPU workloads in a development environment before deploying to production. GPU resources are expensive and debugging issues in production can be costly.