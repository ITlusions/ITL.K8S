# Istio Network Security

This guide covers network-level security configurations in Istio, including mTLS, network policies, and traffic encryption.

## 🎯 Overview

Istio network security provides multiple layers of protection:

- **Transport Security** - Automatic mTLS for service-to-service communication
- **Traffic Encryption** - End-to-end encryption for all mesh traffic  
- **Network Segmentation** - Secure network boundaries and isolation
- **Traffic Filtering** - Network-level access controls
- **Certificate Management** - Automated PKI for secure communication

## 🔒 Mutual TLS (mTLS) Configuration

### Mesh-Wide mTLS

Enable automatic mTLS for all services in the mesh:

```yaml
# Strict mTLS for entire mesh
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
```

### Progressive mTLS Migration

Gradually migrate to mTLS across your services:

```yaml
# Phase 1: Permissive mode (accept both mTLS and plaintext)
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: migration-permissive
  namespace: production
spec:
  mtls:
    mode: PERMISSIVE
---
# Phase 2: After verification, enable strict mode
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: migration-strict
  namespace: production
spec:
  mtls:
    mode: STRICT
```

### Service-Specific mTLS

Configure mTLS for individual services:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: database-mtls
  namespace: production
spec:
  selector:
    matchLabels:
      app: postgres
  mtls:
    mode: STRICT
  portLevelMtls:
    5432:
      mode: STRICT    # Database connection
    9187:
      mode: DISABLE   # Metrics endpoint (plaintext)
```

### External Service mTLS

Configure mTLS for external services:

```yaml
# Service entry for external mTLS service
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: external-secure-api
  namespace: production
spec:
  hosts:
  - secure-api.external.com
  ports:
  - number: 443
    name: https
    protocol: HTTPS
  location: MESH_EXTERNAL
  resolution: DNS
---
# Destination rule with mTLS
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: external-secure-api
  namespace: production
spec:
  host: secure-api.external.com
  trafficPolicy:
    tls:
      mode: MUTUAL
      clientCertificate: /etc/ssl/certs/client-cert.pem
      privateKey: /etc/ssl/private/client-key.pem
      caCertificates: /etc/ssl/certs/ca-cert.pem
```

## 🛡️ Network Policies Integration

### Kubernetes Network Policies with Istio

Combine Kubernetes NetworkPolicies with Istio security:

```yaml
# Kubernetes NetworkPolicy - basic network segmentation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: production-isolation
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow from same namespace
  - from:
    - namespaceSelector:
        matchLabels:
          name: production
  # Allow from ingress gateway
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
    - podSelector:
        matchLabels:
          istio: ingressgateway
  # Allow monitoring
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 15090  # Envoy admin
    - protocol: TCP
      port: 15000  # Envoy stats
  egress:
  # Allow DNS
  - to: []
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
  # Allow HTTPS outbound
  - to: []
    ports:
    - protocol: TCP
      port: 443
---
# Istio AuthorizationPolicy - application-level security
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: production-access-control
  namespace: production
spec:
  action: ALLOW
  rules:
  # Allow authenticated service-to-service communication
  - from:
    - source:
        namespaces: ["production"]
  # Allow specific monitoring access
  - from:
    - source:
        namespaces: ["monitoring"]
        principals: ["cluster.local/ns/monitoring/sa/prometheus"]
  - to:
    - operation:
        methods: ["GET"]
        paths: ["/metrics", "/health"]
```

### Multi-Tenant Network Isolation

Implement strict network isolation between tenants:

```yaml
# Tenant A namespace isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-a-isolation
  namespace: tenant-a
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Only allow traffic from same tenant
  - from:
    - namespaceSelector:
        matchLabels:
          tenant: "a"
  # Allow ingress from gateway
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
  egress:
  # Allow DNS and system services
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
  # Allow same tenant communication
  - to:
    - namespaceSelector:
        matchLabels:
          tenant: "a"
---
# Istio-level tenant isolation
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: tenant-a-authz
  namespace: tenant-a
spec:
  action: ALLOW
  rules:
  # Only allow same tenant services
  - from:
    - source:
        namespaces: ["tenant-a"]
  # Allow platform services
  - from:
    - source:
        namespaces: ["istio-system", "monitoring"]
        principals: 
        - "cluster.local/ns/monitoring/sa/prometheus"
        - "cluster.local/ns/istio-system/sa/istio-ingressgateway-service-account"
```

## 🔐 Traffic Encryption

### Automatic Encryption

Istio automatically encrypts all mTLS traffic:

```yaml
# Verify encryption is enabled
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: default-encryption
  namespace: istio-system
spec:
  host: "*.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL  # Automatic mTLS
---
# Monitor encryption coverage
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: mtls-metrics
  namespace: istio-system
spec:
  metrics:
  - providers:
    - name: prometheus
  - overrides:
    - match:
        metric: ALL_METRICS
      tagOverrides:
        mtls_status:
          value: |
            has(connection.mtls) ? 
            (connection.mtls ? "encrypted" : "plaintext") : 
            "unknown"
```

### Custom Certificate Integration

Use custom certificates for specific services:

```yaml
# Custom CA certificate secret
apiVersion: v1
kind: Secret
metadata:
  name: custom-ca-cert
  namespace: istio-system
  labels:
    istio.io/key-and-cert: custom-ca
type: istio.io/ca-root
data:
  root-cert.pem: [base64-encoded-ca-certificate]
  cert-chain.pem: [base64-encoded-certificate-chain]
  ca-cert.pem: [base64-encoded-ca-certificate]
  ca-key.pem: [base64-encoded-ca-private-key]
---
# Use custom CA for specific namespace
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: custom-ca-auth
  namespace: secure-services
spec:
  mtls:
    mode: STRICT
```

### End-to-End Encryption Verification

Verify encryption is working correctly:

```bash
#!/bin/bash
# Verify mTLS encryption status

echo "Checking mTLS status across the mesh..."

# Check mesh-wide mTLS configuration
kubectl get peerauthentication default -n istio-system -o yaml

# Verify mTLS for specific services
for namespace in production staging; do
  echo "Checking mTLS in namespace: $namespace"
  
  # Get all pods in namespace
  pods=$(kubectl get pods -n $namespace -o jsonpath='{.items[*].metadata.name}')
  
  for pod in $pods; do
    if kubectl get pod $pod -n $namespace -o jsonpath='{.metadata.annotations.sidecar\.istio\.io/status}' > /dev/null 2>&1; then
      echo "Checking mTLS for pod: $pod"
      istioctl authn tls-check $pod.$namespace
    fi
  done
done

# Check for any plaintext connections
echo "Checking for plaintext connections..."
kubectl logs -n istio-system -l app=istiod | grep -i "plaintext\|unencrypted" | tail -10
```

## 🌐 Network Segmentation

### Microservice Network Boundaries

Create secure network boundaries between microservices:

```yaml
# Database tier isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-tier
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: database
  policyTypes:
  - Ingress
  ingress:
  # Only application tier can access database
  - from:
    - podSelector:
        matchLabels:
          tier: application
    ports:
    - protocol: TCP
      port: 5432
    - protocol: TCP
      port: 3306
  # Allow monitoring
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 9187  # Postgres exporter
---
# Application tier isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: application-tier
  namespace: production
spec:
  podSelector:
    matchLabels:
      tier: application
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow from presentation tier and ingress
  - from:
    - podSelector:
        matchLabels:
          tier: presentation
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
  egress:
  # Allow to database tier
  - to:
    - podSelector:
        matchLabels:
          tier: database
    ports:
    - protocol: TCP
      port: 5432
  # Allow external API calls
  - to: []
    ports:
    - protocol: TCP
      port: 443
```

### Environment Isolation

Isolate different environments within the same cluster:

```yaml
# Production environment isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: production-environment
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Only production services
  - from:
    - namespaceSelector:
        matchLabels:
          environment: production
  # Platform services
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
  egress:
  # System services
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
  # Production services only
  - to:
    - namespaceSelector:
        matchLabels:
          environment: production
  # External services
  - to: []
    ports:
    - protocol: TCP
      port: 443
    - protocol: UDP
      port: 53
---
# Staging environment isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: staging-environment
  namespace: staging
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Only staging services
  - from:
    - namespaceSelector:
        matchLabels:
          environment: staging
  # Platform services
  - from:
    - namespaceSelector:
        matchLabels:
          name: istio-system
  egress:
  # Staging services only - prevent access to production
  - to:
    - namespaceSelector:
        matchLabels:
          environment: staging
  # External services
  - to: []
    ports:
    - protocol: TCP
      port: 443
```

## 🚦 Traffic Control and Filtering

### Source IP Filtering

Filter traffic based on source IP addresses:

```yaml
# Allow only trusted IP ranges
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: ip-whitelist
  namespace: production
spec:
  selector:
    matchLabels:
      app: admin-panel
  action: ALLOW
  rules:
  # Corporate network
  - from:
    - source:
        ipBlocks:
        - 10.99.2.0/24
        - 172.16.0.0/16
  # VPN users
  - from:
    - source:
        ipBlocks:
        - 192.168.100.0/24
  # Cluster internal
  - from:
    - source:
        ipBlocks:
        - 10.244.0.0/16   # Pod CIDR
        - 10.96.0.0/12    # Service CIDR
---
# Block specific IP ranges
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: ip-blacklist
  namespace: production
spec:
  selector:
    matchLabels:
      app: public-api
  action: DENY
  rules:
  # Block known bad actors
  - from:
    - source:
        ipBlocks:
        - 192.0.2.0/24    # TEST-NET-1
        - 198.51.100.0/24 # TEST-NET-2
  # Block specific countries (example)
  - when:
    - key: request.headers[x-country-code]
      values: ["XX", "YY"]  # Replace with actual blocked countries
```

### Protocol-Level Filtering

Filter traffic based on protocols and ports:

```yaml
# Allow only specific protocols
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: protocol-restrictions
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: web-server
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Only HTTP/HTTPS traffic
  - ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 8080
  egress:
  # Allow DNS
  - ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
  # Allow HTTPS outbound only
  - ports:
    - protocol: TCP
      port: 443
  # Block all other protocols (implicit)
```

### Rate Limiting at Network Level

Implement network-level rate limiting:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: EnvoyFilter
metadata:
  name: network-rate-limit
  namespace: production
spec:
  workloadSelector:
    labels:
      app: api-gateway
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: SIDECAR_INBOUND
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          stat_prefix: rate_limit
          token_bucket:
            max_tokens: 100
            tokens_per_fill: 10
            fill_interval: 1s
          filter_enabled:
            default_value:
              numerator: 100
              denominator: HUNDRED
          filter_enforced:
            default_value:
              numerator: 100
              denominator: HUNDRED
```

## 📊 Network Security Monitoring

### Security Metrics Collection

Monitor network security events:

```yaml
apiVersion: telemetry.istio.io/v1alpha1
kind: Telemetry
metadata:
  name: network-security-metrics
  namespace: istio-system
spec:
  metrics:
  - providers:
    - name: prometheus
  - overrides:
    - match:
        metric: ALL_METRICS
      tagOverrides:
        # Track mTLS usage
        connection_security:
          value: |
            has(connection.mtls) ? 
            (connection.mtls ? "mtls" : "plaintext") : 
            "unknown"
        # Track source IP ranges
        source_network:
          value: |
            has(source.ip) ? 
            (source.ip | startsWith("10.") ? "internal" : 
             source.ip | startsWith("172.") ? "internal" : 
             source.ip | startsWith("192.168.") ? "internal" : "external") : 
            "unknown"
        # Track denied connections
        connection_denied:
          value: |
            response.code == 403 ? "true" : "false"
```

### Network Flow Analysis

Monitor network flows for security analysis:

```bash
#!/bin/bash
# Network security monitoring script

echo "=== Network Security Status ==="

# Check mTLS status
echo "mTLS Status:"
istioctl authn tls-check --all 2>/dev/null | grep -E "(HOST|CONFLICT|OK)"

# Check for plaintext connections
echo -e "\nPlaintext Connections:"
kubectl logs -n istio-system -l app=istiod --since=1h | grep -i "plaintext" | wc -l

# Check authorization denials
echo -e "\nAuthorization Denials (last hour):"
kubectl logs -n istio-system -l app=istiod --since=1h | grep -c "RBAC: access denied"

# Check network policy violations
echo -e "\nNetwork Policy Status:"
kubectl get networkpolicies --all-namespaces --no-headers | wc -l

# Check for external connections
echo -e "\nExternal Service Entries:"
kubectl get serviceentries --all-namespaces --no-headers | wc -l

# Security alert summary
echo -e "\n=== Security Alerts ==="
kubectl logs -n istio-system -l app=istiod --since=1h | grep -E "(WARNING|ERROR)" | tail -5
```

### Automated Security Scanning

Implement automated network security scanning:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: network-security-scan
  namespace: security
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: security-scanner
          containers:
          - name: scanner
            image: istio/pilot:latest
            command:
            - /bin/bash
            - -c
            - |
              echo "Starting network security scan..."
              
              # Check for insecure configurations
              kubectl get peerauthentication --all-namespaces -o yaml | \
                yq eval '.items[] | select(.spec.mtls.mode != "STRICT") | .metadata.name' -
              
              # Scan for overly permissive policies
              kubectl get authorizationpolicy --all-namespaces -o yaml | \
                yq eval '.items[] | select(.spec.rules[0].from == null and .spec.action == "ALLOW") | .metadata.name' -
              
              # Check network policy coverage
              namespaces=$(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}')
              for ns in $namespaces; do
                if ! kubectl get networkpolicy -n $ns >/dev/null 2>&1; then
                  echo "WARNING: No network policies in namespace $ns"
                fi
              done
              
              echo "Security scan completed"
          restartPolicy: OnFailure
```

## 🚨 Network Security Troubleshooting

### Connection Issues Diagnosis

Debug mTLS and network connectivity problems:

```bash
#!/bin/bash
# Network security troubleshooting script

SOURCE_POD=$1
DEST_SERVICE=$2
NAMESPACE=${3:-production}

if [[ -z "$SOURCE_POD" || -z "$DEST_SERVICE" ]]; then
  echo "Usage: $0 <source-pod> <destination-service> [namespace]"
  exit 1
fi

echo "Diagnosing network connectivity from $SOURCE_POD to $DEST_SERVICE in namespace $NAMESPACE"

# Check if pods have Istio sidecar
echo "1. Checking Istio sidecar injection..."
kubectl get pod $SOURCE_POD -n $NAMESPACE -o jsonpath='{.spec.containers[*].name}' | grep -q istio-proxy
if [ $? -eq 0 ]; then
  echo "✓ Source pod has Istio sidecar"
else
  echo "✗ Source pod missing Istio sidecar"
fi

# Check mTLS status
echo "2. Checking mTLS configuration..."
istioctl authn tls-check $SOURCE_POD.$NAMESPACE $DEST_SERVICE.$NAMESPACE.svc.cluster.local

# Check authorization policies
echo "3. Checking authorization policies..."
kubectl get authorizationpolicy -n $NAMESPACE -o yaml | grep -A 10 -B 5 $DEST_SERVICE

# Check network policies
echo "4. Checking network policies..."
kubectl get networkpolicy -n $NAMESPACE -o yaml

# Test connectivity
echo "5. Testing connectivity..."
kubectl exec $SOURCE_POD -n $NAMESPACE -c istio-proxy -- curl -s -o /dev/null -w "%{http_code}" http://$DEST_SERVICE:80/

# Check Envoy configuration
echo "6. Checking Envoy configuration..."
istioctl proxy-config cluster $SOURCE_POD.$NAMESPACE --fqdn $DEST_SERVICE.$NAMESPACE.svc.cluster.local
```

### Common Network Security Issues

1. **mTLS Not Working**
   ```bash
   # Check PeerAuthentication policies
   kubectl get peerauthentication --all-namespaces
   
   # Verify certificate status
   istioctl proxy-config secret <pod-name>.<namespace>
   
   # Check for DestinationRule conflicts
   kubectl get destinationrule --all-namespaces -o yaml | grep -A 5 -B 5 "mode:"
   ```

2. **Authorization Denials**
   ```bash
   # Check authorization policies
   kubectl get authorizationpolicy --all-namespaces
   
   # View Envoy access logs
   kubectl logs <pod-name> -c istio-proxy -n <namespace> | grep "RBAC"
   
   # Test with verbose logging
   istioctl proxy-config log <pod-name>.<namespace> --level rbac:debug
   ```

3. **Network Policy Conflicts**
   ```bash
   # Check network policy coverage
   kubectl get networkpolicy --all-namespaces
   
   # Test connectivity
   kubectl exec <source-pod> -n <namespace> -- nc -zv <target-service> <port>
   
   # Check for policy conflicts
   kubectl describe networkpolicy -n <namespace>
   ```

## 📋 Network Security Best Practices

### Security Hardening Checklist

- ✅ **Enable strict mTLS** for all production workloads
- ✅ **Implement network policies** for every namespace
- ✅ **Use IP whitelisting** for sensitive services
- ✅ **Monitor certificate expiry** and rotation
- ✅ **Regular security scanning** of network configurations
- ✅ **Implement rate limiting** to prevent abuse
- ✅ **Use protocol-specific filtering** where appropriate
- ✅ **Monitor network flows** for anomalies
- ✅ **Test failover scenarios** regularly
- ✅ **Document security architecture** and update regularly

### Performance Considerations

- **mTLS Overhead** - Monitor latency impact of encryption
- **Network Policy Complexity** - Keep policies simple and efficient
- **Certificate Rotation** - Plan for brief connection interruptions
- **Monitoring Impact** - Balance security monitoring with performance

## 📖 Related Documentation

- **[Istio Security Overview](ISTIO_SECURITY_OVERVIEW.md)** - Complete security guide
- **[Istio Authentication](ISTIO_AUTHENTICATION.md)** - Authentication configuration
- **[Istio Authorization](ISTIO_AUTHORIZATION.md)** - Authorization policies
- **[Gateway Security](ISTIO_GATEWAY_SECURITY.md)** - Gateway security configuration
- **[Security Best Practices](ISTIO_SECURITY_BEST_PRACTICES.md)** - Comprehensive security practices

---

*For network security questions, contact the Platform Team at platform@itlusions.nl*