# GitHub Authentication for Bare Metal Kubernetes

Simple setup guide for GitHub authentication on self-managed Kubernetes clusters using Keycloak.

## Overview

This guide shows how to set up GitHub authentication for a bare metal Kubernetes cluster using **Keycloak as the OIDC provider**.

**What you'll get:**
- Users login with GitHub credentials through Keycloak
- GitHub teams map to Kubernetes roles
- Centralized identity management through Keycloak
- No shared cluster passwords

## Prerequisites

- Kubernetes cluster (kubeadm installation)
- Keycloak instance running and accessible
- GitHub organization with teams
- Admin access to your cluster and Keycloak

## Authentication Methods

For bare metal Kubernetes deployments, choose the method that best fits your infrastructure:

| Method | Use Case | Complexity | Best For |
|--------|----------|------------|----------|
| **Direct OIDC** | Simple bare metal clusters | Low | Direct GitHub integration |
| **Dex Proxy** | Multi-provider setup | Medium | Enterprise environments with multiple auth sources |
| **GitHub Actions** | CI/CD automation | Low | Automated deployments and GitOps |

## Method 1: Direct OIDC Integration

This method configures the Kubernetes API server to use GitHub as an OIDC provider directly.

### Step 1: Create GitHub OAuth Application

1. **Navigate to GitHub Organization Settings**
   ```
   https://github.com/organizations/ITlusions/settings/applications
   ```

2. **Create New OAuth App**
   - Click **"New OAuth App"**
   - Fill in application details:

   ```
   Application name: Kubernetes Cluster Authentication
   Homepage URL: https://k8s.itlusions.nl
   Description: Authentication for ITlusions Kubernetes clusters
   Authorization callback URL: https://k8s.itlusions.nl/oauth/callback
   ```

## Step 1: Configure GitHub Identity Provider in Keycloak

1. Login to your Keycloak admin console
2. Go to your realm (or create a new one for Kubernetes)
3. Navigate to **Identity Providers**
4. Click **Add provider** and select **GitHub**
5. Configure the GitHub provider:
   - **Alias**: `github`
   - **Client ID**: Your GitHub OAuth app client ID
   - **Client Secret**: Your GitHub OAuth app client secret
   - **Default Scopes**: `read:user read:org`
6. Save the configuration

## Step 2: Create Kubernetes Client in Keycloak

1. In Keycloak, go to **Clients**
2. Click **Create**
3. Configure the client:
   - **Client ID**: `kubernetes`
   - **Client Protocol**: `openid-connect`
   - **Access Type**: `confidential`
   - **Valid Redirect URIs**: `http://localhost:8000/*`
   - **Web Origins**: `*`
4. Go to the **Mappers** tab and add:
   - **Name**: `groups`
   - **Mapper Type**: `Group Membership`
   - **Token Claim Name**: `groups`
   - **Add to userinfo**: On
5. Save the client and note the **Client Secret** from the Credentials tab

## Step 3: Configure GitHub Teams to Keycloak Groups

1. In Keycloak, go to **Groups**
2. Create groups that match your GitHub teams:
   - `github-admins`
   - `github-developers`
   - `github-readonly`
3. Go to **Identity Providers > GitHub > Mappers**
4. Create a mapper to sync GitHub teams:
   - **Name**: `github-teams`
   - **Mapper Type**: `Advanced Attribute to Group`
   - **Social Profile JSON Field Path**: `organizations[*].teams[*]`
   - **Group**: Map to your created groups

## Step 4: Configure API Server for Keycloak OIDC

Edit the API server to use Keycloak as the OIDC provider:

```bash
# Edit API server manifest
sudo vim /etc/kubernetes/manifests/kube-apiserver.yaml
```

Add these flags to the kube-apiserver command:
```yaml
- --oidc-issuer-url=https://keycloak.your-domain/realms/kubernetes
- --oidc-client-id=kubernetes
- --oidc-username-claim=preferred_username
- --oidc-groups-claim=groups
- --oidc-ca-file=/etc/ssl/certs/ca-certificates.crt
```

The API server will restart automatically. Check it's running:
```bash
kubectl get pods -n kube-system | grep apiserver
```

Dex acts as an OIDC proxy that can aggregate multiple authentication providers.

### Step 1: Deploy Dex

```yaml
# dex-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: auth-system
---
# dex-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dex-config
  namespace: auth-system
data:
  config.yaml: |
    issuer: https://dex.k8s.itlusions.nl
    
    storage:
      type: kubernetes
      config:
        inCluster: true
    
    web:
      http: 0.0.0.0:5556
      tlsCert: /etc/dex/tls/tls.crt
      tlsKey: /etc/dex/tls/tls.key
    
    connectors:
    - type: github
      id: github
      name: GitHub
      config:
        clientID: your-github-client-id
        clientSecret: your-github-client-secret
        redirectURI: https://dex.k8s.itlusions.nl/callback
        orgs:
        - name: ITlusions
          teams:
          - Admins
          - Developers
          - DevOps
          - Readonly
    
    oauth2:
      skipApprovalScreen: true
      
    staticClients:
    - id: kubernetes
      redirectURIs:
      - 'urn:ietf:wg:oauth:2.0:oob'
      - 'http://localhost:8000'
      - 'http://localhost:18000'
      name: 'Kubernetes CLI'
      secret: kubernetes-client-secret
      
    enablePasswordDB: false
---
# dex-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dex
  namespace: auth-system
spec:
  replicas: 2
  selector:
    matchLabels:
      app: dex
  template:
    metadata:
      labels:
        app: dex
    spec:
## Step 5: Create Team-based RBAC

Map your Keycloak groups to Kubernetes roles:

```yaml
# rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: admin-users
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: keycloak-admins
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: admin-users
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: Group
  name: github-admins
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: dev-users
rules:
- apiGroups: ["", "apps", "extensions"]
  resources: ["*"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: keycloak-developers
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: dev-users
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: Group
  name: github-developers
```

Apply the RBAC configuration:
```bash
kubectl apply -f rbac.yaml
```
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: dex
            port:
              number: 5556
```

## Method 3: GitHub Actions OIDC

For CI/CD workflows on bare metal clusters, GitHub Actions can use OIDC to authenticate with Kubernetes using service accounts.

### Step 1: Create Service Account for GitHub Actions

```yaml
# github-actions-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: github-actions
  namespace: default
  annotations:
    # Optional: restrict to specific GitHub repository
    github.com/repository: "ITlusions/your-repo"
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: github-actions-binding
subjects:
- kind: ServiceAccount
  name: github-actions
  namespace: default
roleRef:
  kind: ClusterRole
  name: admin  # Adjust permissions as needed
  apiGroup: rbac.authorization.k8s.io
---
# Create a secret for the service account token (K8s 1.24+)
apiVersion: v1
kind: Secret
metadata:
  name: github-actions-token
## Step 5: Setup Client Access

Install and configure kubectl with OIDC:

```bash
# Install kubectl-oidc plugin
kubectl krew install oidc-login

# Create kubeconfig for users
cat > ~/.kube/config-github << EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: https://your-cluster-api:6443
    certificate-authority-data: <your-cluster-ca-cert>
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: github-user
  name: github-auth
current-context: github-auth
users:
- name: github-user
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: kubectl
      args:
      - oidc-login
      - get-token
      - --oidc-issuer-url=https://dex.your-cluster-domain
      - --oidc-client-id=kubernetes
      - --oidc-client-secret=kubernetes-client-secret
EOF
```

## Testing the Setup

Test authentication:
```bash
# Use the GitHub auth kubeconfig
export KUBECONFIG=~/.kube/config-github

# This will open browser for GitHub login
kubectl get nodes

# Check your permissions
kubectl auth can-i get pods
kubectl auth can-i delete pods
```

## Common Issues

**Problem**: "Unable to connect to OIDC provider"  
**Solution**: Check that Dex is running and accessible from your cluster

**Problem**: "User not found"  
**Solution**: Verify the user is a member of the specified GitHub organization

**Problem**: "Access denied"  
**Solution**: Check the RBAC configuration matches your GitHub teams



# Check for authorization decisions
kubectl logs -n kube-system kube-apiserver-master-node | grep -i rbac

# Monitor Dex logs (if using Dex)
kubectl logs -n auth-system deployment/dex -f
```

### Step 4: Test Different User Scenarios

```bash
# Test admin user
kubectl get nodes --as=github:admin@itlusions.nl --as-group=github:ITlusions:Admins

# Test developer user
kubectl get pods -n development --as=github:dev@itlusions.nl --as-group=github:ITlusions:Developers

## Step 6: Setup Client Access

Install and configure kubectl with OIDC:

```bash
# Install kubectl-oidc plugin
kubectl krew install oidc-login

# Create kubeconfig for users
cat > ~/.kube/config-keycloak << EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: https://your-cluster-api:6443
    certificate-authority-data: <your-cluster-ca-cert>
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: keycloak-user
  name: keycloak-auth
current-context: keycloak-auth
users:
- name: keycloak-user
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: kubectl
      args:
      - oidc-login
      - get-token
      - --oidc-issuer-url=https://keycloak.your-domain/realms/kubernetes
      - --oidc-client-id=kubernetes
      - --oidc-client-secret=<your-keycloak-client-secret>
EOF
```

## Testing the Setup

Test authentication:
```bash
# Use the Keycloak auth kubeconfig
export KUBECONFIG=~/.kube/config-keycloak

# This will open browser for Keycloak login (which redirects to GitHub)
kubectl get nodes

# Check your permissions
kubectl auth can-i get pods
kubectl auth can-i delete pods
```

## Common Issues

**Problem**: "Unable to connect to OIDC provider"  
**Solution**: Check that Keycloak is running and accessible from your cluster

**Problem**: "User not found"  
**Solution**: Verify the user authenticated through GitHub in Keycloak and groups are mapped correctly

**Problem**: "Access denied"  
**Solution**: Check the RBAC configuration matches your Keycloak groups

That's it! Your bare metal Kubernetes cluster now authenticates users via GitHub through Keycloak with team-based authorization.

#!/bin/bash

echo "=== Kubernetes OIDC Debugging ==="

echo "1. Checking API Server OIDC Configuration..."
kubectl get pods -n kube-system -l component=kube-apiserver -o yaml | grep -A 20 -B 5 oidc

echo "2. Testing OIDC Discovery..."
curl -s https://token.actions.githubusercontent.com/.well-known/openid_configuration | jq .

echo "3. Checking RBAC Bindings..."
kubectl get clusterrolebindings | grep github
kubectl get rolebindings -A | grep github

echo "4. Testing Authentication..."
kubectl auth whoami 2>&1

echo "5. Testing Authorization..."
kubectl auth can-i --list 2>&1

echo "6. Checking Recent Events..."
kubectl get events --sort-by='.lastTimestamp' | grep -i auth

echo "7. API Server Logs (last 50 lines)..."
kubectl logs -n kube-system -l component=kube-apiserver --tail=50 | grep -i "oidc\|auth\|rbac"

echo "=== End Debug Information ==="
```

### Emergency Access

If authentication breaks and you lose cluster access:

```bash
# Use emergency admin kubeconfig
export KUBECONFIG=/etc/kubernetes/admin.conf

# Or use service account token
kubectl --token=$(kubectl get secret -n kube-system -o jsonpath='{.items[0].data.token}' | base64 -d) get pods

# Reset OIDC configuration if needed
kubectl patch deployment kube-apiserver -n kube-system --type json \
  -p='[{"op": "remove", "path": "/spec/template/spec/containers/0/command", "value": "--oidc-issuer-url"}]'
```

## Security Considerations

### Token Security

1. **Token Lifetime Management**
```bash
# Configure short-lived tokens
--oidc-token-ttl=1h

# Implement token refresh
--oidc-refresh-token-ttl=24h
```

2. **Secure Token Storage**
```bash
# Protect kubeconfig files
chmod 600 ~/.kube/config

# Use encrypted storage for cached tokens
--oidc-cache-dir=/secure/cache
```

### Network Security

1. **TLS/SSL Configuration**
```yaml
# Ensure all communication is encrypted
spec:
  containers:
  - command:
    - kube-apiserver
    - --tls-cert-file=/etc/kubernetes/pki/apiserver.crt
    - --tls-private-key-file=/etc/kubernetes/pki/apiserver.key
    - --oidc-ca-file=/etc/ssl/certs/ca-certificates.crt
```

2. **Network Policies**
```yaml
# Restrict egress to GitHub APIs
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-server-github-access
  namespace: kube-system
spec:
  podSelector:
    matchLabels:
      component: kube-apiserver
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector: {}
  - to: []
    ports:
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 80
```

### Audit Logging

1. **Enable Audit Logging**
```yaml
# audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: Metadata
  namespaces: ["kube-system", "kube-public", "kube-node-lease"]
  verbs: ["get", "list", "watch"]
  
- level: RequestResponse
  resources:
  - group: ""
    resources: ["secrets", "configmaps"]
    
- level: Request
  users: ["github:*"]
  verbs: ["create", "update", "patch", "delete"]
```

2. **Configure API Server Audit**
```yaml
spec:
  containers:
  - command:
    - kube-apiserver
    - --audit-log-path=/var/log/audit.log
    - --audit-policy-file=/etc/kubernetes/audit-policy.yaml
    - --audit-log-maxage=30
    - --audit-log-maxbackup=3
    - --audit-log-maxsize=100
```

### Monitoring Authentication

1. **Set Up Monitoring**
```yaml
# prometheus-auth-rules.yaml
groups:
- name: kubernetes-auth
  rules:
  - alert: HighAuthFailureRate
    expr: rate(apiserver_audit_total{verb="create",objectRef_resource="tokenreviews"}[5m]) > 0.1
    labels:
      severity: warning
    annotations:
      summary: High authentication failure rate
      
  - alert: UnauthorizedAPIAccess
    expr: rate(apiserver_audit_total{verb="get",objectRef_resource="secrets",user!~"system:.*"}[5m]) > 0
    labels:
      severity: critical
    annotations:
      summary: Unauthorized access to secrets
```

2. **Log Analysis**
```bash
# Monitor authentication patterns
kubectl logs -n kube-system -l component=kube-apiserver | \
  grep "authentication\|authorization" | \
  awk '{print $1, $6, $7}' | \
  sort | uniq -c | sort -nr

# Track user activity
kubectl get events --field-selector reason=TokenAudiences | \
  grep github
```

## Best Practices

### Access Management

1. **Use Teams, Not Individual Users**
```yaml
# ✅ Good - Team-based access
subjects:
- kind: Group
  name: github:ITlusions:Developers
  
# ❌ Avoid - Individual user access
subjects:
- kind: User
  name: github:john.doe@itlusions.nl
```

2. **Implement Principle of Least Privilege**
```yaml
# ✅ Good - Namespace-specific permissions
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developers-dev-namespace
  namespace: development
  
# ❌ Avoid - Cluster-wide permissions for developers
kind: ClusterRoleBinding
```

3. **Regular Access Reviews**
```bash
# Quarterly access review script
#!/bin/bash
echo "=== GitHub Teams Access Review ==="
kubectl get clusterrolebindings -o yaml | grep -A 5 -B 5 "github:ITlusions"
kubectl get rolebindings -A -o yaml | grep -A 5 -B 5 "github:ITlusions"
```

### Configuration Management

1. **Infrastructure as Code**
```yaml
# Store all RBAC configurations in Git
# Use GitOps for deployment
# Version control all changes
```

2. **Environment Separation**
```bash
# Different GitHub OAuth apps per environment
# dev-k8s-github-oauth
# staging-k8s-github-oauth  
# prod-k8s-github-oauth
```

3. **Backup and Recovery**
```bash
# Backup RBAC configurations
kubectl get clusterrolebindings -o yaml > rbac-backup.yaml
kubectl get rolebindings -A -o yaml >> rbac-backup.yaml

# Emergency admin access
cp /etc/kubernetes/admin.conf ~/.kube/emergency-config
```

### Operational Excellence

1. **Automated Testing**
```bash
# Test script for RBAC validation
#!/bin/bash
test_user_access() {
    local user=$1
    local group=$2
    local resource=$3
    local namespace=${4:-""}
    
    if [ -n "$namespace" ]; then
        kubectl auth can-i $resource -n $namespace --as=$user --as-group=$group
    else
        kubectl auth can-i $resource --as=$user --as-group=$group
    fi
}

# Run tests
test_user_access "github:dev@itlusions.nl" "github:ITlusions:Developers" "get pods" "development"
test_user_access "github:admin@itlusions.nl" "github:ITlusions:Admins" "get nodes"
```

2. **Documentation and Training**
```markdown
# Team onboarding checklist:
- [ ] Add user to appropriate GitHub teams
- [ ] Provide kubeconfig template
- [ ] Install kubectl and oidc-login plugin
- [ ] Complete authentication walkthrough
- [ ] Test permissions in each environment
```

3. **Monitoring and Alerting**
```yaml
# Key metrics to monitor:
- Authentication success/failure rates
- Token expiration events
- RBAC permission denials
- Unusual access patterns
- API server availability
```

---

*This documentation is maintained by the ITlusions Platform Team. For questions or issues, please create an issue in the ITL.K8s repository or contact the Platform Team.*