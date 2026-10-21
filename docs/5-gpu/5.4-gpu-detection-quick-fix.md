# Fix for alexnet-tf-gpu-pod-v2 ROCm Detection Issue

## Problem Analysis
- ✅ Using ROCm image: `rocm/tensorflow:rocm5.7-tf2.13-dev`
- ✅ Device plugins running
- ✅ GPU resources available on nodes
- ❌ TensorFlow showing CUDA errors instead of detecting AMD GPU

## Root Cause
ROCm 5.7 may not be compatible with your host GPU drivers or GPU hardware. The container needs access to host GPU devices.

## Solution Steps

### Step 1: Create New Pod with Updated ROCm Version and Proper Device Access
```bash
# Delete current pod
kubectl delete pod alexnet-tf-gpu-pod-v2

# Create new pod with better ROCm version and device access
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: alexnet-tf-gpu-pod-v3-fixed
  labels:
    app: gpu-test
spec:
  containers:
  - name: tensorflow-rocm
    image: rocm/tensorflow:rocm6.3-tf2.16-dev  # Newer ROCm version
    command: ["/bin/bash", "-c", "sleep infinity"]
    resources:
      limits:
        amd.com/gpu: 1
        memory: 8Gi
      requests:
        amd.com/gpu: 1
        memory: 4Gi
    env:
    - name: HIP_VISIBLE_DEVICES
      value: "0"
    - name: ROCR_VISIBLE_DEVICES
      value: "0"
    - name: HSA_OVERRIDE_GFX_VERSION
      value: "10.3.0"  # May need adjustment for your GPU
    securityContext:
      privileged: true  # Required for GPU access
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
  restartPolicy: Never
EOF
```

### Step 2: Test GPU Detection
```bash
# Wait for pod to be ready
kubectl get pod alexnet-tf-gpu-pod-v3-fixed -w

# Test GPU detection
kubectl exec -it alexnet-tf-gpu-pod-v3-fixed -- python3 -c "
import tensorflow as tf
print('TensorFlow version:', tf.__version__)
print('GPU devices:', tf.config.list_physical_devices('GPU'))
if tf.config.list_physical_devices('GPU'):
    print('✅ AMD GPU detected successfully!')
else:
    print('❌ Still no GPU detected')
"
```

### Step 3: Run AlexNet Benchmark (if GPU detected)
```bash
kubectl exec -it alexnet-tf-gpu-pod-v3-fixed -- python3 -c "
import tensorflow as tf
import numpy as np

gpus = tf.config.list_physical_devices('GPU')
if gpus:
    # Configure GPU memory growth
    tf.config.experimental.set_memory_growth(gpus[0], True)
    
    # AlexNet model
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
    
    with tf.device('/GPU:0'):
        x = tf.random.normal([8, 224, 224, 3])
        y = tf.random.uniform([8], maxval=1000, dtype=tf.int32)
        
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')
        print('🚀 Running AlexNet on AMD GPU...')
        model.fit(x, y, batch_size=8, epochs=1, verbose=1)
        print('✅ AlexNet benchmark completed on AMD GPU!')
else:
    print('❌ No GPU available - running on CPU')
"
```

### Alternative: Try Different ROCm Images
If the above doesn't work, try these images:
```bash
# Option 1: Latest stable
rocm/tensorflow:latest

# Option 2: Specific stable version
rocm/tensorflow:rocm6.1-tf2.15-dev

# Option 3: Ubuntu-based
rocm/dev-ubuntu-22.04:6.1.2
```

### Debug Commands if Still Not Working
```bash
# Check GPU devices in container
kubectl exec -it alexnet-tf-gpu-pod-v3-fixed -- ls -la /dev/dri/
kubectl exec -it alexnet-tf-gpu-pod-v3-fixed -- ls -la /dev/kfd

# Check ROCm info in container  
kubectl exec -it alexnet-tf-gpu-pod-v3-fixed -- rocminfo

# Check environment variables
kubectl exec -it alexnet-tf-gpu-pod-v3-fixed -- env | grep -E 'HIP|ROC'
```

The key changes are:
1. **Newer ROCm version** (6.3 vs 5.7)
2. **Privileged security context** for GPU access
3. **Host device mounts** (/dev/dri and /dev/kfd)
4. **Proper environment variables** for ROCm