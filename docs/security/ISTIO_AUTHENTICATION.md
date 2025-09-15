# Istio Authentication Configuration

This guide covers Istio authentication mechanisms including mutual TLS (mTLS), JWT authentication, and identity management.

## 🎯 Overview

Istio provides two types of authentication:

- **Peer Authentication** - Service-to-service authentication using mTLS
- **Request Authentication** - End-user authentication using JWT tokens
- **Identity Management** - SPIFFE/SPIRE integration for service identity

## 🔐 Peer Authentication (mTLS)

### Mesh-Wide mTLS

Enable strict mTLS for the entire mesh:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
```

### Namespace-Level mTLS

Configure mTLS for specific namespaces:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: namespace-mtls
  namespace: production
spec:
  mtls:
    mode: STRICT
```

### Workload-Specific mTLS

Target specific workloads:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: api-server-mtls
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-server
  mtls:
    mode: STRICT
```

### Port-Specific mTLS

Configure different mTLS modes per port:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: port-specific-mtls
  namespace: production
spec:
  selector:
    matchLabels:
      app: database
  mtls:
    mode: STRICT
  portLevelMtls:
    5432:
      mode: DISABLE  # Plain PostgreSQL protocol
    9090:
      mode: STRICT   # Metrics endpoint with mTLS
```

## 🎫 Request Authentication (JWT)

### Basic JWT Authentication

Configure JWT validation with Keycloak:

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: keycloak-jwt
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-gateway
  jwtRules:
  - issuer: "https://keycloak.itlusions.nl/auth/realms/kubernetes"
    jwksUri: "https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs"
    audiences: 
    - "kubernetes-api"
    - "web-app"
    # Token location in request
    fromHeaders:
    - name: "Authorization"
      prefix: "Bearer "
    fromParams:
    - "access_token"
    # Token forwarding
    forwardOriginalToken: true
```

### Multiple JWT Providers

Support multiple identity providers:

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: multi-provider-jwt
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-server
  jwtRules:
  # Keycloak for internal users
  - issuer: "https://keycloak.itlusions.nl/auth/realms/kubernetes"
    jwksUri: "https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs"
    audiences: ["internal-api"]
  # External OAuth provider
  - issuer: "https://accounts.google.com"
    jwksUri: "https://www.googleapis.com/oauth2/v3/certs"
    audiences: ["external-api"]
  # GitHub OAuth for CI/CD
  - issuer: "https://token.actions.githubusercontent.com"
    jwksUri: "https://token.actions.githubusercontent.com/.well-known/jwks"
    audiences: ["https://github.com/ITlusions"]
```

### JWT with Custom Claims Validation

Validate specific JWT claims:

```yaml
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: custom-claims-jwt
  namespace: production
spec:
  selector:
    matchLabels:
      app: admin-api
  jwtRules:
  - issuer: "https://keycloak.itlusions.nl/auth/realms/kubernetes"
    jwksUri: "https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs"
    audiences: ["admin-api"]
    # Custom claim validation
    fromHeaders:
    - name: "Authorization"
      prefix: "Bearer "
    # Optional: specify required claims
    outputPayloadToHeader: "x-jwt-payload"
```

## 🆔 Identity Management

### Service Account Configuration

Properly configure service accounts for workload identity:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-server-sa
  namespace: production
  labels:
    app: api-server
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
      annotations:
        # Enable sidecar injection
        sidecar.istio.io/inject: "true"
    spec:
      serviceAccountName: api-server-sa
      containers:
      - name: api-server
        image: itlusions/api-server:v1.0
        ports:
        - containerPort: 8080
```

### Custom CA Integration

Integrate custom Certificate Authority:

```yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: custom-ca
spec:
  values:
    pilot:
      env:
        # Use custom CA
        EXTERNAL_CA: true
        # Custom CA configuration
        CA_ADDR: "custom-ca.istio-system:8060"
    global:
      meshConfig:
        # Custom CA root certificate
        rootCA: |
          -----BEGIN CERTIFICATE-----
          [Your custom CA certificate here]
          -----END CERTIFICATE-----
```

## 🔧 Authentication Patterns

### Pattern 1: Progressive mTLS Migration

Gradually enable mTLS across the mesh:

```yaml
# Step 1: Permissive mode (allow both mTLS and plain text)
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: migration-phase-1
  namespace: production
spec:
  mtls:
    mode: PERMISSIVE
---
# Step 2: After verification, enable strict mode
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: migration-phase-2
  namespace: production
spec:
  mtls:
    mode: STRICT
```

### Pattern 2: External Service mTLS

Configure mTLS for external services:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: external-db
  namespace: production
spec:
  hosts:
  - external-db.example.com
  ports:
  - number: 5432
    name: postgres
    protocol: TCP
  location: MESH_EXTERNAL
  resolution: DNS
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: external-db-mtls
  namespace: production
spec:
  host: external-db.example.com
  trafficPolicy:
    tls:
      mode: MUTUAL
      clientCertificate: /etc/ssl/certs/client.pem
      privateKey: /etc/ssl/private/client-key.pem
      caCertificates: /etc/ssl/certs/ca.pem
```

### Pattern 3: Gateway Authentication

Configure authentication at ingress gateway:

```yaml
# Gateway with TLS termination
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: secure-gateway
  namespace: production
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: api-tls-secret
    hosts:
    - api.itlusions.nl
---
# Request authentication for gateway traffic
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: gateway-jwt
  namespace: istio-system
spec:
  selector:
    matchLabels:
      istio: ingressgateway
  jwtRules:
  - issuer: "https://keycloak.itlusions.nl/auth/realms/kubernetes"
    jwksUri: "https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs"
    audiences: ["api-gateway"]
    fromHeaders:
    - name: "Authorization"
      prefix: "Bearer "
```

### Pattern 4: Mixed Authentication Modes

Support both authenticated and anonymous access:

```yaml
# Request authentication (optional JWT)
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: optional-jwt
  namespace: production
spec:
  selector:
    matchLabels:
      app: public-api
  jwtRules:
  - issuer: "https://keycloak.itlusions.nl/auth/realms/kubernetes"
    jwksUri: "https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs"
    audiences: ["public-api"]
---
# Authorization policy with conditional access
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: mixed-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: public-api
  action: ALLOW
  rules:
  # Allow public endpoints for everyone
  - to:
    - operation:
        paths: ["/health", "/version", "/docs"]
  # Require authentication for protected endpoints
  - from:
    - source:
        requestPrincipals: ["*"]
  - to:
    - operation:
        paths: ["/api/v1/protected/*"]
```

## 🛠️ Certificate Management

### Automatic Certificate Rotation

Configure automatic certificate rotation:

```yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: certificate-config
spec:
  values:
    pilot:
      env:
        # Certificate lifetime (24 hours)
        DEFAULT_WORKLOAD_CERT_TTL: "24h"
        # Maximum certificate lifetime
        MAX_WORKLOAD_CERT_TTL: "90d"
        # Certificate rotation grace period
        SECRET_TTL: "24h"
```

### Manual Certificate Injection

Inject custom certificates for workloads:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: custom-cert
  namespace: production
  labels:
    istio.io/key: custom-cert
    istio.io/cert-chain: custom-cert-chain
type: istio.io/key-and-cert
data:
  key: [base64-encoded-private-key]
  cert: [base64-encoded-certificate]
  cacert: [base64-encoded-ca-certificate]
---
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: custom-cert-auth
  namespace: production
spec:
  selector:
    matchLabels:
      app: secure-service
  mtls:
    mode: STRICT
```

## 📊 Monitoring Authentication

### Key Metrics

Monitor authentication-related metrics:

```bash
# mTLS success rate
istio_request_total{security_policy="mutual_tls"}

# JWT validation failures
istio_request_total{response_code="401"}

# Certificate expiry monitoring
pilot_k8s_cfg_events{type="Secret"}
```

### Verification Commands

```bash
# Check mTLS status
istioctl authn tls-check <pod-name>.<namespace>

# Verify JWT configuration
kubectl describe requestauthentication -n <namespace>

# Check certificate status
istioctl proxy-config secret <pod-name>.<namespace>

# Test authentication
curl -H "Authorization: Bearer $JWT_TOKEN" https://api.itlusions.nl/protected
```

### Debug Authentication Issues

```bash
# Check Envoy authentication filters
istioctl proxy-config listeners <pod-name>.<namespace> --port 8080 -o json

# View authentication policy status
kubectl get peerauthentication,requestauthentication -A

# Check certificate details
openssl x509 -in /etc/ssl/certs/cert-chain.pem -text -noout
```

## 🚨 Troubleshooting

### Common Issues

1. **mTLS Connection Failures**
   ```bash
   # Check certificate validity
   istioctl proxy-config secret <pod-name>.<namespace>
   
   # Verify peer authentication policy
   kubectl describe peerauthentication -n <namespace>
   
   # Check for certificate rotation issues
   kubectl logs -n istio-system deployment/istiod | grep certificate
   ```

2. **JWT Validation Errors**
   ```bash
   # Verify JWT issuer and audience
   jwt-cli decode $JWT_TOKEN
   
   # Check JWKS endpoint accessibility
   curl https://keycloak.itlusions.nl/auth/realms/kubernetes/protocol/openid_connect/certs
   
   # Review request authentication configuration
   kubectl describe requestauthentication -n <namespace>
   ```

3. **Certificate Expiry Issues**
   ```bash
   # Check certificate expiration
   istioctl proxy-config secret <pod-name>.<namespace> -o json | jq '.dynamicActiveSecrets[0].secret.tlsCertificate.certificateChain.inlineBytes' | base64 -d | openssl x509 -text -noout
   
   # Force certificate renewal
   kubectl delete secret istio.default -n <namespace>
   ```

## 📋 Best Practices

### Security Guidelines

- **Enable strict mTLS** in production environments
- **Use short-lived certificates** (24-hour default)
- **Implement proper JWT validation** with audience verification
- **Monitor certificate expiry** proactively
- **Test authentication policies** in staging first
- **Use service accounts** consistently for workload identity
- **Implement certificate rotation** monitoring and alerting

### Performance Considerations

- **Minimize JWT payload size** for better performance
- **Cache JWKS responses** when possible
- **Use efficient authentication policies** with specific selectors
- **Monitor authentication latency** and optimize accordingly

## 📖 Related Documentation

- **[Istio Authorization](ISTIO_AUTHORIZATION.md)** - Access control policies
- **[Gateway Security](ISTIO_GATEWAY_SECURITY.md)** - Ingress authentication
- **[Network Security](ISTIO_NETWORK_SECURITY.md)** - Network-level security
- **[Certificate Management](ISTIO_CERTIFICATE_MANAGEMENT.md)** - PKI operations

---

*For authentication configuration questions, contact the Platform Team at platform@itlusions.nl*