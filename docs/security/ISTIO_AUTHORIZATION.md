# Istio Authorization Policies

This guide covers Istio authorization policies for implementing fine-grained access control in your service mesh.

## 🎯 Overview

Istio authorization policies provide Layer 7 access control for workloads in the mesh. They support:

- **RBAC** - Role-based access control
- **ABAC** - Attribute-based access control  
- **Source-based controls** - IP, subnet, and service identity
- **Operation-based controls** - HTTP methods, paths, headers
- **Custom conditions** - Complex authorization logic

## 🔧 Policy Types

### 1. ALLOW Policies

Grant access to specific sources or operations:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-read-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-server
  action: ALLOW
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/production/sa/web-app"]
  - to:
    - operation:
        methods: ["GET"]
```

### 2. DENY Policies

Block specific traffic (higher priority than ALLOW):

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-external-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: internal-api
  action: DENY
  rules:
  - from:
    - source:
        notNamespaces: ["production", "staging"]
```

### 3. AUDIT Policies

Log access for compliance (requires telemetry configuration):

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: audit-admin-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: admin-panel
  action: AUDIT
  rules:
  - to:
    - operation:
        methods: ["POST", "PUT", "DELETE"]
```

## 📋 Common Patterns

### Pattern 1: Subnet-Based Access Control

Restrict access to specific IP ranges:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-trusted-subnet
  namespace: itl-k8s-resourceexplorer
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: itl-k8s-re
  action: ALLOW
  rules:
  # Allow trusted corporate network
  - from:
    - source:
        ipBlocks:
        - 10.99.2.0/24
  # Allow internal cluster communication
  - from:
    - source:
        ipBlocks:
        - 10.244.0.0/16    # Pod CIDR
        - 10.96.0.0/12     # Service CIDR
        - 127.0.0.1/32     # Localhost
  # Allow service account communication within namespace
  - from:
    - source:
        namespaces: ["itl-k8s-resourceexplorer"]
```

### Pattern 2: Service-to-Service Authorization

Control inter-service communication:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: database-access-control
  namespace: production
spec:
  selector:
    matchLabels:
      app: postgres
  action: ALLOW
  rules:
  # Only allow specific services to access database
  - from:
    - source:
        principals: 
        - "cluster.local/ns/production/sa/api-server"
        - "cluster.local/ns/production/sa/batch-processor"
  - to:
    - operation:
        ports: ["5432"]
```

### Pattern 3: HTTP Method Restrictions

Control access based on HTTP operations:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: api-method-restrictions
  namespace: production
spec:
  selector:
    matchLabels:
      app: rest-api
  action: ALLOW
  rules:
  # Read-only access for regular users
  - from:
    - source:
        principals: ["cluster.local/ns/production/sa/web-app"]
  - to:
    - operation:
        methods: ["GET", "HEAD", "OPTIONS"]
  # Full access for admin services
  - from:
    - source:
        principals: ["cluster.local/ns/production/sa/admin-service"]
  - to:
    - operation:
        methods: ["GET", "POST", "PUT", "DELETE"]
```

### Pattern 4: Path-Based Authorization

Control access to specific API endpoints:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: path-based-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-gateway
  action: ALLOW
  rules:
  # Public endpoints - no restrictions
  - to:
    - operation:
        paths: ["/health", "/version", "/metrics"]
  # User data endpoints - authenticated users only
  - from:
    - source:
        requestPrincipals: ["*"]  # Any authenticated user
  - to:
    - operation:
        paths: ["/api/v1/users/*", "/api/v1/profile/*"]
  # Admin endpoints - admin role required
  - from:
    - source:
        custom:
        - key: request.auth.claims[role]
          values: ["admin"]
  - to:
    - operation:
        paths: ["/api/v1/admin/*"]
```

### Pattern 5: Namespace Isolation

Implement strict namespace boundaries:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: namespace-isolation
  namespace: production
spec:
  action: ALLOW
  rules:
  # Allow intra-namespace communication
  - from:
    - source:
        namespaces: ["production"]
  # Allow specific cross-namespace communication
  - from:
    - source:
        namespaces: ["monitoring"]
        principals: ["cluster.local/ns/monitoring/sa/prometheus"]
  # Allow ingress traffic
  - from:
    - source:
        namespaces: ["istio-system"]
        principals: ["cluster.local/ns/istio-system/sa/istio-ingressgateway-service-account"]
```

## 🔒 Advanced Security Patterns

### JWT-Based Authorization

Combine with RequestAuthentication for JWT validation:

```yaml
# First, configure JWT authentication
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-server
  jwtRules:
  - issuer: "https://keycloak.itlusions.nl/auth/realms/kubernetes"
    jwksUri: "https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs"
    audiences: ["kubernetes-api"]
---
# Then, enforce authorization based on JWT claims
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: jwt-authorization
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-server
  action: ALLOW
  rules:
  # Require valid JWT with specific claims
  - from:
    - source:
        requestPrincipals: ["https://keycloak.itlusions.nl/auth/realms/kubernetes/*"]
  - when:
    - key: request.auth.claims[groups]
      values: ["ITlusions:Developers", "ITlusions:Admins"]
```

### Header-Based Routing and Authorization

Control access based on custom headers:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: header-based-auth
  namespace: production
spec:
  selector:
    matchLabels:
      app: feature-api
  action: ALLOW
  rules:
  # Allow requests with API key
  - when:
    - key: request.headers[x-api-key]
      values: ["*"]  # Any non-empty value
  # Allow requests from internal services
  - from:
    - source:
        namespaces: ["production"]
  # Allow requests with specific user agent
  - when:
    - key: request.headers[user-agent]
      values: ["ITLusions-Service/*"]
```

### Time-Based Access Control

Implement temporary access controls:

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: maintenance-window
  namespace: production
spec:
  selector:
    matchLabels:
      app: maintenance-api
  action: ALLOW
  rules:
  # Only allow access during maintenance window
  - when:
    - key: request.headers[x-maintenance-token]
      values: ["maint-2025-09-15"]
  - from:
    - source:
        principals: ["cluster.local/ns/production/sa/maintenance-service"]
```

## 🛠️ Policy Management

### Policy Ordering and Precedence

1. **CUSTOM action** (if configured)
2. **DENY policies** (highest priority)
3. **ALLOW policies** (if no DENY matches)
4. **Default DENY** (if no ALLOW policies exist)

### Testing Policies

```bash
# Test authorization with istioctl
istioctl authz check <pod-name> -n <namespace>

# Dry run policy changes
kubectl apply --dry-run=client -f authorization-policy.yaml

# Check policy status
kubectl get authorizationpolicy -n production -o wide
```

### Policy Validation

```yaml
# Use annotations for policy validation
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: validated-policy
  namespace: production
  annotations:
    # Validate policy syntax
    config.istio.io/validate: "true"
    # Policy description
    security.istio.io/description: "Allow access to API from web frontend"
spec:
  # Policy configuration...
```

## 📊 Monitoring and Debugging

### Key Metrics

Monitor these authorization-related metrics:

```bash
# Authorization policy evaluation
istio_requests_total{response_code="403"}

# Policy enforcement
istio_request_duration_milliseconds{source_app="policy-enforcer"}

# Authentication failures  
istio_requests_total{response_code="401"}
```

### Debug Commands

```bash
# Check authorization policies for a workload
istioctl proxy-config cluster <pod-name>.<namespace> --fqdn <service-fqdn>

# View authorization policy configuration
kubectl describe authorizationpolicy -n <namespace>

# Check Envoy authorization config
istioctl proxy-config listeners <pod-name>.<namespace> --port 80 -o json
```

### Troubleshooting Tips

1. **Policy Not Working**
   - Check selector labels match target workloads
   - Verify namespace and service account names
   - Ensure proper mTLS configuration

2. **Unexpected Denials**
   - Review DENY policies (they take precedence)
   - Check for conflicting policies
   - Verify source identities and IP blocks

3. **Performance Issues**
   - Minimize policy complexity
   - Use efficient selectors
   - Consider policy consolidation

## 📋 Best Practices

### Policy Design

- **Start with DENY-all** approach for security
- **Use specific selectors** to target workloads precisely
- **Minimize policy count** for better performance
- **Document policies** with clear descriptions
- **Test policies** in non-production first

### Security Considerations

- **Regular policy reviews** and audits
- **Principle of least privilege** in all policies
- **Monitor policy violations** for security events
- **Use automation** for policy deployment
- **Maintain policy templates** for consistency

## 📖 Related Documentation

- **[Istio Authentication](ISTIO_AUTHENTICATION.md)** - Authentication configuration
- **[Gateway Security](ISTIO_GATEWAY_SECURITY.md)** - Ingress security
- **[Network Security](ISTIO_NETWORK_SECURITY.md)** - Network-level controls
- **[Security Best Practices](ISTIO_SECURITY_BEST_PRACTICES.md)** - Comprehensive security guide

---

*For questions about authorization policies, contact the Platform Team at platform@itlusions.nl*