# Istio Gateway Security

This guide covers security configuration for Istio Gateways, including TLS termination, traffic filtering, and external access control.

## 🎯 Overview

Istio Gateways provide secure ingress and egress for your mesh:

- **Ingress Gateways** - Secure external traffic entry points
- **Egress Gateways** - Controlled external service access
- **TLS Termination** - Certificate management and encryption
- **Traffic Filtering** - IP-based and header-based filtering
- **Rate Limiting** - Protection against abuse

## 🚪 Ingress Gateway Security

### Basic Secure Gateway

Configure HTTPS ingress with automatic redirect:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: secure-ingress
  namespace: production
spec:
  selector:
    istio: ingressgateway
  servers:
  # HTTP to HTTPS redirect
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - api.itlusions.nl
    - "*.itlusions.nl"
    tls:
      httpsRedirect: true
  # HTTPS termination
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: itlusions-nl-tls
    hosts:
    - api.itlusions.nl
    - "*.itlusions.nl"
```

### Mutual TLS (mTLS) Gateway

Require client certificates for additional security:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: mtls-gateway
  namespace: production
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https-mtls
      protocol: HTTPS
    tls:
      mode: MUTUAL
      credentialName: server-tls-secret
      caCertificates: /etc/ssl/certs/ca-cert.pem
    hosts:
    - secure-api.itlusions.nl
```

### Multi-Domain Gateway

Handle multiple domains with different certificates:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: multi-domain-gateway
  namespace: production
spec:
  selector:
    istio: ingressgateway
  servers:
  # Main domain
  - port:
      number: 443
      name: https-main
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: itlusions-nl-tls
    hosts:
    - api.itlusions.nl
    - app.itlusions.nl
  # Development domain
  - port:
      number: 443
      name: https-dev
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: dev-itlusions-nl-tls
    hosts:
    - "*.dev.itlusions.nl"
  # Internal domain
  - port:
      number: 443
      name: https-internal
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: internal-itlusions-nl-tls
    hosts:
    - "*.internal.itlusions.nl"
```

## 🔒 Traffic Filtering and Access Control

### IP-Based Traffic Filtering

Block or allow traffic from specific IP ranges:

```yaml
# Block external traffic, allow internal subnet
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: subnet-filter
  namespace: production
spec:
  hosts:
  - internal-api.itlusions.nl
  gateways:
  - secure-ingress
  http:
  # Allow trusted subnet
  - match:
    - headers:
        x-forwarded-for:
          regex: "^10\\.99\\.2\\..*"
    route:
    - destination:
        host: internal-api-service
  # Block all other traffic
  - fault:
      abort:
        percentage:
          value: 100.0
        httpStatus: 403
    route:
    - destination:
        host: internal-api-service
```

### Geographic Traffic Control

Route traffic based on geographic location:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: geo-routing
  namespace: production
spec:
  hosts:
  - global-api.itlusions.nl
  gateways:
  - secure-ingress
  http:
  # EU traffic
  - match:
    - headers:
        cloudfront-viewer-country:
          regex: "^(NL|DE|BE|FR|IT|ES|UK)$"
    route:
    - destination:
        host: eu-api-service
  # US traffic
  - match:
    - headers:
        cloudfront-viewer-country:
          regex: "^(US|CA|MX)$"
    route:
    - destination:
        host: us-api-service
  # Default to EU
  - route:
    - destination:
        host: eu-api-service
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: EnvoyFilter
metadata:
  name: rate-limit-filter
  namespace: istio-system
spec:
  configPatches:
  - applyTo: HTTP_FILTER
    match:
      context: GATEWAY
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: INSERT_BEFORE
      value:
        name: envoy.filters.http.local_ratelimit
        typed_config:
          "@type": type.googleapis.com/udpa.type.v1.TypedStruct
          type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
          value:
            stat_prefix: rate_limiter
            token_bucket:
              max_tokens: 1000
              tokens_per_fill: 100
              fill_interval: 60s
            filter_enabled:
              runtime_key: local_rate_limit_enabled
              default_value:
                numerator: 100
                denominator: HUNDRED
```

## 🚦 Advanced Gateway Patterns

### Canary Deployments with Gateways

Route traffic for canary deployments:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: canary-routing
  namespace: production
spec:
  hosts:
  - api.itlusions.nl
  gateways:
  - secure-ingress
  http:
  # Canary traffic for beta users
  - match:
    - headers:
        x-user-group:
          exact: "beta"
    route:
    - destination:
        host: api-service
        subset: v2
  # 10% traffic to new version
  - match:
    - uri:
        prefix: "/api/v1/"
    route:
    - destination:
        host: api-service
        subset: v1
      weight: 90
    - destination:
        host: api-service
        subset: v2
      weight: 10
  # Default routing
  - route:
    - destination:
        host: api-service
        subset: v1
```

### Emergency Traffic Blocking

Implement emergency traffic blocking capability:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: emergency-block
  namespace: production
  labels:
    emergency: "false"  # Change to "true" to activate blocking
spec:
  hosts:
  - resources.dev.itlusions.com
  - resources.dev.itlusions.nl
  gateways:
  - production-gateway
  http:
  # Emergency block - activated by label change
  - match:
    - headers:
        emergency-bypass:
          exact: "itl-emergency-2025"
    route:
    - destination:
        host: itl-k8s-resourceexplorer
  # Normal operation - block when emergency label is true
  - fault:
      abort:
        percentage:
          value: 100.0
        httpStatus: 503
    match:
    - uri:
        prefix: "/"
    route:
    - destination:
        host: itl-k8s-resourceexplorer
```

### Custom Security Headers

Add security headers at the gateway:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: EnvoyFilter
metadata:
  name: security-headers
  namespace: istio-system
spec:
  configPatches:
  - applyTo: HTTP_ROUTE
    match:
      context: GATEWAY
    patch:
      operation: MERGE
      value:
        response_headers_to_add:
        # HSTS
        - header:
            key: "Strict-Transport-Security"
            value: "max-age=31536000; includeSubDomains"
        # Content Security Policy
        - header:
            key: "Content-Security-Policy"
            value: "default-src 'self'; script-src 'self' 'unsafe-inline'"
        # X-Frame-Options
        - header:
            key: "X-Frame-Options"
            value: "DENY"
        # X-Content-Type-Options
        - header:
            key: "X-Content-Type-Options"
            value: "nosniff"
        # Referrer Policy
        - header:
            key: "Referrer-Policy"
            value: "strict-origin-when-cross-origin"
```

## 🌐 Egress Gateway Security

### Controlled External Access

Secure outbound traffic through egress gateway:

```yaml
# Egress gateway deployment
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: egress-gateway
  namespace: istio-system
spec:
  selector:
    istio: egressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    hosts:
    - api.github.com
    - "*.googleapis.com"
---
# Service entry for external services
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: github-api
  namespace: production
spec:
  hosts:
  - api.github.com
  ports:
  - number: 443
    name: https
    protocol: HTTPS
  location: MESH_EXTERNAL
  resolution: DNS
---
# Virtual service routing through egress gateway
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: github-via-egress
  namespace: production
spec:
  hosts:
  - api.github.com
  gateways:
  - mesh
  - egress-gateway
  http:
  - match:
    - gateways:
      - mesh
      port: 443
    route:
    - destination:
        host: istio-egressgateway.istio-system.svc.cluster.local
        subset: github
      weight: 100
  - match:
    - gateways:
      - egress-gateway
      port: 443
    route:
    - destination:
        host: api.github.com
      weight: 100
```

### Egress Traffic Monitoring

Monitor and log egress traffic:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: EnvoyFilter
metadata:
  name: egress-access-log
  namespace: istio-system
spec:
  workloadSelector:
    labels:
      istio: egressgateway
  configPatches:
  - applyTo: NETWORK_FILTER
    match:
      listener:
        filterChain:
          filter:
            name: envoy.filters.network.http_connection_manager
    patch:
      operation: MERGE
      value:
        typed_config:
          access_log:
          - name: envoy.access_loggers.file
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.access_loggers.file.v3.FileAccessLog
              path: /dev/stdout
              format: |
                [%START_TIME%] "%REQ(:METHOD)% %REQ(X-ENVOY-ORIGINAL-PATH?:PATH)% %PROTOCOL%"
                %RESPONSE_CODE% %RESPONSE_FLAGS% %BYTES_RECEIVED% %BYTES_SENT%
                %DURATION% %RESP(X-ENVOY-UPSTREAM-SERVICE-TIME)% "%REQ(X-FORWARDED-FOR)%"
                "%REQ(USER-AGENT)%" "%REQ(X-REQUEST-ID)%" "%REQ(:AUTHORITY)%"
                "%UPSTREAM_HOST%" %DOWNSTREAM_REMOTE_ADDRESS%
```

## 🛡️ Gateway Security Hardening

### TLS Configuration Best Practices

Secure TLS configuration for gateways:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: hardened-gateway
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
      credentialName: secure-tls-cert
      # TLS version restrictions
      minProtocolVersion: TLSV1_2
      maxProtocolVersion: TLSV1_3
      # Cipher suites (if needed for compliance)
      cipherSuites:
      - "ECDHE-ECDSA-AES256-GCM-SHA384"
      - "ECDHE-RSA-AES256-GCM-SHA384"
      - "ECDHE-ECDSA-AES128-GCM-SHA256"
      - "ECDHE-RSA-AES128-GCM-SHA256"
    hosts:
    - secure.itlusions.nl
```

### Gateway Resource Limits

Configure resource limits for gateway pods:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-ingress-gateway
  namespace: istio-system
data:
  values.yaml: |
    gateways:
      istio-ingressgateway:
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 2000m
            memory: 1024Mi
        # Security context
        securityContext:
          runAsUser: 1337
          runAsGroup: 1337
          runAsNonRoot: true
          fsGroup: 1337
        # Pod security context
        podSecurityContext:
          seccompProfile:
            type: RuntimeDefault
```

### Network Policies for Gateways

Restrict network access to gateway pods:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: istio-ingressgateway-netpol
  namespace: istio-system
spec:
  podSelector:
    matchLabels:
      istio: ingressgateway
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Allow traffic from load balancer
  - from: []
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 15021  # Health check
  egress:
  # Allow DNS
  - to: []
    ports:
    - protocol: UDP
      port: 53
  # Allow communication to workloads
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 443
```

## 📊 Gateway Monitoring and Observability

### Key Gateway Metrics

Monitor these important gateway metrics:

```bash
# Connection success rate
istio_requests_total{source_app="istio-ingressgateway"}

# TLS handshake failures  
envoy_ssl_connection_error

# Rate limiting effectiveness
envoy_http_local_rate_limit_rate_limited

# Certificate expiry
pilot_k8s_cfg_events{type="Secret"}
```

### Gateway Access Logs

Configure comprehensive access logging:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: istio-ingress-access-log
  namespace: istio-system
data:
  custom_access_log.json: |
    {
      "timestamp": "%START_TIME%",
      "method": "%REQ(:METHOD)%",
      "path": "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%",
      "protocol": "%PROTOCOL%",
      "response_code": %RESPONSE_CODE%,
      "response_flags": "%RESPONSE_FLAGS%",
      "bytes_received": %BYTES_RECEIVED%,
      "bytes_sent": %BYTES_SENT%,
      "duration": %DURATION%,
      "upstream_service_time": "%RESP(X-ENVOY-UPSTREAM-SERVICE-TIME)%",
      "x_forwarded_for": "%REQ(X-FORWARDED-FOR)%",
      "user_agent": "%REQ(USER-AGENT)%",
      "request_id": "%REQ(X-REQUEST-ID)%",
      "authority": "%REQ(:AUTHORITY)%",
      "upstream_host": "%UPSTREAM_HOST%",
      "client_ip": "%DOWNSTREAM_REMOTE_ADDRESS%"
    }
```

### Health Checks and Readiness

Configure proper health checks:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: istio-ingressgateway
  namespace: istio-system
spec:
  selector:
    istio: ingressgateway
  ports:
  - name: status-port
    port: 15021
    targetPort: 15021
    protocol: TCP
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-health-checks
  namespace: istio-system
spec:
  podSelector:
    matchLabels:
      istio: ingressgateway
  policyTypes:
  - Ingress
  ingress:
  - from: []
    ports:
    - protocol: TCP
      port: 15021
```

## 🚨 Troubleshooting Gateway Issues

### Common Problems

1. **Certificate Issues**
   ```bash
   # Check certificate status
   kubectl get secret -n istio-system
   
   # Verify certificate validity
   kubectl get secret itlusions-nl-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout
   
   # Check certificate in gateway
   istioctl proxy-config secret istio-ingressgateway-xxx -n istio-system
   ```

2. **Gateway Configuration Issues**
   ```bash
   # Verify gateway configuration
   kubectl describe gateway -n production
   
   # Check virtual service routing
   istioctl proxy-config routes istio-ingressgateway-xxx.istio-system
   
   # Verify listener configuration
   istioctl proxy-config listeners istio-ingressgateway-xxx.istio-system
   ```

3. **Traffic Routing Problems**
   ```bash
   # Test connectivity
   curl -v -H "Host: api.itlusions.nl" http://GATEWAY_IP/health
   
   # Check access logs
   kubectl logs -n istio-system -l istio=ingressgateway -f
   
   # Verify backend connectivity
   istioctl proxy-config cluster istio-ingressgateway-xxx.istio-system
   ```

## 📋 Gateway Security Best Practices

### Security Checklist

- ✅ **Enable HTTPS redirect** for all HTTP traffic
- ✅ **Use TLS 1.2+** minimum version
- ✅ **Implement proper HSTS** headers
- ✅ **Configure rate limiting** for abuse prevention
- ✅ **Monitor certificate expiry** proactively
- ✅ **Use network policies** to restrict gateway access
- ✅ **Implement IP filtering** for sensitive endpoints
- ✅ **Enable comprehensive logging** for security events
- ✅ **Regular security scanning** of gateway configurations
- ✅ **Test failover scenarios** for high availability

### Configuration Management

- **Use GitOps** for gateway configuration management
- **Implement configuration validation** before deployment
- **Maintain separate gateways** for different environments
- **Regular configuration audits** and compliance checks
- **Automated certificate renewal** processes

## 📖 Related Documentation

- **[Istio Authentication](ISTIO_AUTHENTICATION.md)** - Authentication configuration
- **[Istio Authorization](ISTIO_AUTHORIZATION.md)** - Access control policies
- **[Network Security](ISTIO_NETWORK_SECURITY.md)** - Network-level security
- **[Certificate Management](ISTIO_CERTIFICATE_MANAGEMENT.md)** - TLS certificate operations

---

*For gateway security questions, contact the Platform Team at platform@itlusions.nl*