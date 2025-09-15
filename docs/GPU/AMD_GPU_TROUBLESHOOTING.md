# AMD GPU Troubleshooting Guide

## � Quick Diagnosis Table

| Symptom | Problem | Section |
|---------|---------|---------|
| `Could not find cuda drivers` | Wrong container image (CUDA vs ROCm) | [Issue 1](#issue-1-wrong-container-image-cuda-vs-rocm) |
| `GPU Available: []` | Wrong container image or driver issue | [Issue 1](#issue-1-wrong-container-image-cuda-vs-rocm) |
| `ROCm driver not found` | ROCm drivers not installed/loaded | [Issue 2](#issue-2-rocm-drivers-not-loading) |
| `Permission denied /dev/kfd` | User permissions issue | [Issue 3](#issue-3-permission-denied-errors) |
| Pod stuck `Pending` | No GPU resources or scheduling issue | [Issue 4](#issue-4-pod-stuck-in-pending-state) |
| `No AMD GPU devices found` | Device plugin or container config | [Issue 5](#issue-5-container-cannot-access-gpu) |

## �🚨 Most Common Issues and Solutions

### Issue 1: Wrong Container Image (CUDA vs ROCm)

#### Symptoms
```bash
# TensorFlow shows CUDA warnings with AMD GPU
Could not find cuda drivers on your machine, GPU will not be used.
TF-TRT Warning: Could not find TensorRT
GPU Available: []

# OR PyTorch shows CUDA initialization
RuntimeError: No CUDA GPUs are available
```

#### Root Cause
You're using a **CUDA-based** container image (designed for NVIDIA GPUs) instead of a **ROCm-based** image (designed for AMD GPUs).

#### Solutions

**❌ Wrong Images (CUDA-based)**
```bash
# These will NOT work with AMD GPUs
tensorflow/tensorflow:latest-gpu
pytorch/pytorch:latest
nvidia/cuda:*
```

**✅ Correct Images (ROCm-based)**
```bash
# Use these for AMD GPUs
rocm/tensorflow:latest                    # TensorFlow with ROCm
rocm/pytorch:latest                      # PyTorch with ROCm  
rocm/tensorflow:rocm6.3-tf2.16-dev      # Specific versions
rocm/pytorch:rocm6.3-py3.10-pytorch2.4.0
```

**Quick Fix for Your Current Pod**
```bash
# Delete current pod
kubectl delete pod alexnet-tf-gpu-pod-v2

# Create new pod with ROCm image
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: alexnet-tf-gpu-pod-rocm
spec:
  containers:
  - name: tensorflow-rocm
    image: rocm/tensorflow:rocm6.3-tf2.16-dev  # ROCm-based image
    command: ["/bin/bash", "-c", "sleep infinity"]
    resources:
      limits:
        amd.com/gpu: 1
      requests:
        amd.com/gpu: 1
    env:
    - name: HIP_VISIBLE_DEVICES
      value: "0"
  restartPolicy: Never
EOF

# Test GPU access
kubectl exec -it alexnet-tf-gpu-pod-rocm -- python3 -c "
import tensorflow as tf
print('TensorFlow version:', tf.__version__)
print('GPU devices:', tf.config.list_physical_devices('GPU'))
"
```

**Complete AlexNet Benchmark with ROCm**
```bash
# Run this inside the ROCm container
kubectl exec -it alexnet-tf-gpu-pod-rocm -- python3 -c "
import tensorflow as tf
import numpy as np
print('TensorFlow version:', tf.__version__)

# Check GPU availability
gpus = tf.config.list_physical_devices('GPU')
print('GPU devices:', gpus)

if gpus:
    print('✅ AMD GPU detected!')
    # Configure GPU memory growth to avoid OOM
    tf.config.experimental.set_memory_growth(gpus[0], True)
    
    # AlexNet-style model
    model = tf.keras.Sequential([
        tf.keras.layers.Conv2D(96, 11, strides=4, activation='relu', input_shape=(224, 224, 3)),
        tf.keras.layers.MaxPooling2D(3, strides=2),
        tf.keras.layers.Conv2D(256, 5, padding='same', activation='relu'),
        tf.keras.layers.MaxPooling2D(3, strides=2),
        tf.keras.layers.Conv2D(384, 3, padding='same', activation='relu'),
        tf.keras.layers.Conv2D(384, 3, padding='same', activation='relu'),
        tf.keras.layers.Conv2D(256, 3, padding='same', activation='relu'),
        tf.keras.layers.MaxPooling2D(3, strides=2),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(4096, activation='relu'),
        tf.keras.layers.Dense(4096, activation='relu'),
        tf.keras.layers.Dense(1000, activation='softmax')
    ])
    
    # Verify model runs on GPU
    with tf.device('/GPU:0'):
        x = tf.random.normal([8, 224, 224, 3])  # Smaller batch for testing
        y = tf.random.uniform([8], maxval=1000, dtype=tf.int32)
        
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')
        print('🚀 Running AlexNet benchmark on AMD GPU...')
        model.fit(x, y, batch_size=8, epochs=1, verbose=1)
        print('✅ Benchmark completed successfully on AMD GPU!')
else:
    print('❌ No GPU devices found - check your configuration')
"
```

### Issue 2: ROCm Drivers Not Loading

#### Symptoms
```bash
$ rocminfo
ROCm version: N/A
Error: ROCm driver not found
```

#### Solutions
```bash
# Check if amdgpu driver is loaded
lsmod | grep amdgpu

# If not loaded, try manual loading
sudo modprobe amdgpu

# Check dmesg for driver errors
dmesg | grep -i amd

# Rebuild initramfs (Ubuntu/Debian)
sudo update-initramfs -u

# Reboot system
sudo reboot
```

### Issue 2: Permission Denied Errors

#### Symptoms
```bash
Error: Permission denied when accessing /dev/kfd
```

#### Solutions
```bash
# Check current user groups
groups $USER

# Add user to required groups
sudo usermod -aG render,video $USER

# Check device permissions
ls -la /dev/kfd /dev/dri/render*

# Log out and back in, or use newgrp
newgrp render
newgrp video
```

### Issue 3: Device Plugin Not Detecting GPUs

#### Symptoms
```bash
kubectl get nodes -o yaml | grep amd.com/gpu
# Returns nothing
```

#### Diagnostic Commands
```bash
# Check device plugin logs
kubectl logs -n kube-system -l name=amdgpu-device-plugin-ds

# Verify GPU visibility from node
ssh <gpu-node>
rocminfo
rocm-smi
ls -la /dev/kfd
```

#### Solutions
```bash
# Restart device plugin
kubectl delete pod -n kube-system -l name=amdgpu-device-plugin-ds

# Check kubelet logs
journalctl -u kubelet -f

# Manually register device plugin socket
sudo ls -la /var/lib/kubelet/device-plugins/
```

### Issue 4: Container Cannot Access GPU

#### Symptoms
```
HIP error: hipErrorNoDevice
No AMD GPU devices found
```

#### Solutions
```bash
# Check container security context
kubectl describe pod <pod-name>

# Verify GPU resource request
kubectl get pod <pod-name> -o yaml | grep -A 5 -B 5 amd.com/gpu

# Check environment variables in pod
kubectl exec <pod-name> -- env | grep -E 'HIP|ROC'

# Test GPU access manually
kubectl exec -it <pod-name> -- rocm-smi
```

### Issue 5: Pod Stuck in Pending State

#### Diagnostic Commands
```bash
# Check pod events
kubectl describe pod <pod-name>

# Check resource availability
kubectl describe nodes | grep -A 10 -B 5 amd.com/gpu

# Verify node taints and tolerations
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints
```

#### Solutions
```bash
# Check if GPU nodes have resources available
kubectl get nodes -o custom-columns="NODE:.metadata.name,GPU:.status.allocatable.amd\.com/gpu"

# If no GPU resources, restart device plugin
kubectl delete pod -n kube-system -l name=amdgpu-device-plugin-ds

# Check for node taints preventing scheduling
kubectl describe node <gpu-node-name> | grep Taints
```

## 🛠️ Quick Diagnostic Script

Save this script as `diagnose_amd_gpu.sh` to quickly identify your specific issue:

```bash
#!/bin/bash
# AMD GPU Kubernetes Diagnostic Script

echo "=== AMD GPU Kubernetes Diagnostics ==="
echo

# Check 1: Are we using the right container image?
echo "🔍 Checking for common container image issues..."
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}' | tr ' ' '\n' | grep -E "(tensorflow|pytorch|cuda)" | head -5
echo

# Check 2: Do nodes have AMD GPU resources?
echo "🔍 Checking GPU resources on nodes..."
kubectl get nodes -o custom-columns="NODE:.metadata.name,GPU:.status.allocatable.amd\.com/gpu" | grep -v '<none>'
if [ $? -ne 0 ]; then
    echo "❌ No AMD GPU resources found on any nodes"
    echo "   → Check if device plugin is running:"
    kubectl get pods -n kube-system -l name=amdgpu-device-plugin-ds
else
    echo "✅ AMD GPU resources detected on nodes"
fi
echo

# Check 3: Device plugin status
echo "🔍 Checking AMD GPU device plugin status..."
PLUGIN_PODS=$(kubectl get pods -n kube-system -l name=amdgpu-device-plugin-ds --no-headers 2>/dev/null | wc -l)
if [ $PLUGIN_PODS -eq 0 ]; then
    echo "❌ No AMD GPU device plugin pods found"
    echo "   → Deploy device plugin first!"
else
    echo "✅ Found $PLUGIN_PODS device plugin pod(s)"
    kubectl get pods -n kube-system -l name=amdgpu-device-plugin-ds
fi
echo

# Check 4: GPU pods status
echo "🔍 Checking GPU workload pods..."
GPU_PODS=$(kubectl get pods -o json | jq -r '.items[] | select(.spec.containers[].resources.limits."amd.com/gpu") | .metadata.name' 2>/dev/null)
if [ -z "$GPU_PODS" ]; then
    echo "ℹ️  No pods requesting AMD GPUs currently"
else
    echo "GPU pods found:"
    for pod in $GPU_PODS; do
        STATUS=$(kubectl get pod $pod -o jsonpath='{.status.phase}')
        IMAGE=$(kubectl get pod $pod -o jsonpath='{.spec.containers[0].image}')
        echo "  📦 $pod: $STATUS (image: $IMAGE)"
        
        # Check for wrong image type
        if echo "$IMAGE" | grep -qE "(tensorflow.*gpu|pytorch.*gpu|nvidia/)"; then
            echo "     ⚠️  WARNING: This looks like a CUDA image, not ROCm!"
        fi
    done
fi
echo

echo "=== Diagnostic Summary ==="
echo "If you see 'Could not find cuda drivers' → Use rocm/ images instead"
echo "If no GPU resources on nodes → Deploy AMD device plugin"
echo "If pod stuck pending → Check GPU resource availability"
echo
echo "For detailed solutions, see: https://github.com/ITlusions/ITL.K8s/blob/main/docs/gpu/AMD_GPU_TROUBLESHOOTING.md"
```

**Usage:**
```bash
# Make script executable and run
chmod +x diagnose_amd_gpu.sh
./diagnose_amd_gpu.sh
```

## 🔧 Advanced Troubleshooting

### ROCm Installation Verification Script

```bash
#!/bin/bash
# rocm_verify.sh - Comprehensive ROCm verification

echo "=== ROCm Installation Verification ==="

echo "1. Checking ROCm installation..."
if command -v rocminfo &> /dev/null; then
    echo "✓ ROCm tools installed"
    rocminfo | head -20
else
    echo "✗ ROCm tools not found"
fi

echo -e "\n2. Checking GPU driver..."
if lsmod | grep -q amdgpu; then
    echo "✓ AMD GPU driver loaded"
else
    echo "✗ AMD GPU driver not loaded"
fi

echo -e "\n3. Checking device files..."
for dev in /dev/kfd /dev/dri/render*; do
    if [ -e "$dev" ]; then
        echo "✓ $dev exists"
        ls -la "$dev"
    else
        echo "✗ $dev not found"
    fi
done

echo -e "\n4. Checking user permissions..."
if groups | grep -q render && groups | grep -q video; then
    echo "✓ User in render and video groups"
else
    echo "✗ User missing required group memberships"
    echo "Current groups: $(groups)"
fi

echo -e "\n5. Testing GPU access..."
if rocm-smi &> /dev/null; then
    echo "✓ GPU accessible via ROCm"
    rocm-smi
else
    echo "✗ Cannot access GPU via ROCm"
fi

echo -e "\n=== Verification Complete ==="
```

### Kubernetes GPU Debug Script

```bash
#!/bin/bash
# k8s_gpu_debug.sh - Kubernetes GPU troubleshooting

echo "=== Kubernetes GPU Debug ==="

echo "1. Checking GPU nodes..."
kubectl get nodes -l amd.com/gpu --no-headers | wc -l | xargs -I {} echo "GPU nodes found: {}"

echo -e "\n2. GPU resource allocation..."
kubectl describe nodes | grep -A 5 -B 5 amd.com/gpu

echo -e "\n3. Device plugin status..."
kubectl get pods -n kube-system -l name=amdgpu-device-plugin-ds

echo -e "\n4. Device plugin logs (last 50 lines)..."
kubectl logs -n kube-system -l name=amdgpu-device-plugin-ds --tail=50

echo -e "\n5. GPU pods in cluster..."
kubectl get pods --all-namespaces -o json | jq -r '.items[] | select(.spec.containers[]?.resources.requests."amd.com/gpu"?) | "\(.metadata.namespace)/\(.metadata.name)"'

echo -e "\n6. Node feature discovery..."
kubectl get nodes -o json | jq '.items[].metadata.labels' | grep -E 'amd|gpu' | head -10

echo -e "\n=== Debug Complete ==="
```

## 📊 Monitoring and Metrics

### GPU Resource Monitoring

```bash
# Real-time GPU utilization
kubectl exec <gpu-pod> -- watch -n 1 rocm-smi

# GPU temperature and power
kubectl exec <gpu-pod> -- rocm-smi -t -p

# Memory usage
kubectl exec <gpu-pod> -- rocm-smi -u

# All GPU metrics
kubectl exec <gpu-pod> -- rocm-smi -a
```

### Custom GPU Metrics Exporter

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: amd-gpu-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: amd-gpu-exporter
  template:
    metadata:
      labels:
        app: amd-gpu-exporter
    spec:
      hostPID: true
      containers:
      - name: gpu-exporter
        image: prom/node-exporter:latest
        args:
        - --path.rootfs=/host
        - --collector.textfile.directory=/var/lib/node_exporter/textfile_collector
        ports:
        - containerPort: 9100
          name: metrics
        volumeMounts:
        - name: host-sys
          mountPath: /host/sys
          readOnly: true
        - name: host-proc
          mountPath: /host/proc
          readOnly: true
        - name: textfile-dir
          mountPath: /var/lib/node_exporter/textfile_collector
      - name: gpu-metrics-collector
        image: rocm/rocm-terminal:latest
        command: ["/bin/bash"]
        args:
        - -c
        - |
          while true; do
            rocm-smi --json > /tmp/gpu_metrics.json
            python3 -c "
          import json
          import time
          
          with open('/tmp/gpu_metrics.json') as f:
              data = json.load(f)
          
          with open('/var/lib/node_exporter/textfile_collector/amd_gpu.prom', 'w') as f:
              timestamp = int(time.time() * 1000)
              for gpu_id, gpu_data in data.items():
                  if gpu_id.startswith('card'):
                      f.write(f'amd_gpu_temperature_celsius{{gpu=\"{gpu_id}\"}} {gpu_data.get(\"Temperature (Sensor edge) (C)\", 0)} {timestamp}\n')
                      f.write(f'amd_gpu_power_watts{{gpu=\"{gpu_id}\"}} {gpu_data.get(\"Average Graphics Package Power (W)\", 0)} {timestamp}\n')
                      f.write(f'amd_gpu_utilization_percent{{gpu=\"{gpu_id}\"}} {gpu_data.get(\"GPU use (%)\", 0)} {timestamp}\n')
          "
            sleep 30
          done
        volumeMounts:
        - name: textfile-dir
          mountPath: /var/lib/node_exporter/textfile_collector
        - name: dev
          mountPath: /dev
        - name: sys
          mountPath: /sys
      volumes:
      - name: host-sys
        hostPath:
          path: /sys
      - name: host-proc
        hostPath:
          path: /proc
      - name: textfile-dir
        emptyDir: {}
      - name: dev
        hostPath:
          path: /dev
      - name: sys
        hostPath:
          path: /sys
      nodeSelector:
        amd.com/gpu: "true"
```

## 🔄 Recovery Procedures

### Complete GPU Stack Reset

```bash
#!/bin/bash
# gpu_stack_reset.sh - Reset entire GPU stack

echo "Resetting AMD GPU stack..."

# Stop all GPU pods
kubectl delete pods --all-namespaces --field-selector=spec.containers[*].resources.requests.amd\.com/gpu

# Remove device plugin
kubectl delete ds -n kube-system amdgpu-device-plugin-daemonset

# Reset ROCm on nodes (run on each GPU node)
sudo systemctl stop kubelet
sudo rmmod amdgpu
sudo modprobe amdgpu
sudo systemctl start kubelet

# Reinstall device plugin
kubectl apply -f /path/to/amd-device-plugin.yaml

# Verify recovery
sleep 30
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.amd\.com/gpu
```

### Node-specific GPU Reset

```bash
# Run on GPU node that's having issues
sudo systemctl stop kubelet

# Reset GPU driver
sudo rmmod amdgpu
sleep 5
sudo modprobe amdgpu

# Clear device plugin socket
sudo rm -f /var/lib/kubelet/device-plugins/amd.com-gpu.*

# Restart services
sudo systemctl start kubelet

# Verify GPU detection
rocminfo
rocm-smi
```

## 📋 Pre-deployment Checklist

Before deploying GPU workloads:

- [ ] ✅ ROCm drivers installed on all GPU nodes
- [ ] ✅ Users added to render/video groups
- [ ] ✅ Device plugin running and detecting GPUs
- [ ] ✅ Node labels present (amd.com/gpu)
- [ ] ✅ Container runtime configured for GPU support
- [ ] ✅ Test pod successfully scheduled and running
- [ ] ✅ GPU resources visible in kubectl describe nodes
- [ ] ✅ Monitoring configured (optional)
- [ ] ✅ Resource quotas configured (if applicable)
- [ ] ✅ Network policies allow GPU pod communication

## 🆘 Emergency Commands

```bash
# Quick GPU status check
kubectl get nodes -l amd.com/gpu -o wide

# Force recreate all device plugin pods
kubectl delete pods -n kube-system -l name=amdgpu-device-plugin-ds --force

# Emergency GPU pod termination
kubectl delete pods --all-namespaces --field-selector=spec.nodeName=<gpu-node-name> --force

# Check for stuck GPU resources
kubectl get pods --all-namespaces -o json | jq '.items[] | select(.status.phase=="Pending") | select(.spec.containers[]?.resources.requests."amd.com/gpu"?) | .metadata.name'

# Node drain for maintenance
kubectl drain <gpu-node-name> --ignore-daemonsets --delete-emptydir-data
```

## 📞 Support Resources

- **ROCm Issues**: [GitHub ROCm Issues](https://github.com/RadeonOpenCompute/ROCm/issues)
- **Device Plugin Issues**: [K8s Device Plugin Issues](https://github.com/RadeonOpenCompute/k8s-device-plugin/issues)
- **Community Support**: [ROCm Community Forum](https://community.amd.com/t5/rocm/ct-p/amd-rocm)
- **Documentation**: [ROCm Documentation](https://rocm.docs.amd.com/)

---

> **🔍 Remember**: When reporting GPU issues, always include ROCm version, GPU model, driver version, and Kubernetes version for faster resolution.