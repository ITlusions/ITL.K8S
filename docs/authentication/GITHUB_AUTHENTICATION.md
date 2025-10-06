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

For bare metal Kubernetes deployments, we use Keycloak as the OIDC provider that integrates with GitHub:

| Method | Use Case | Complexity | Best For |
|--------|----------|------------|----------|
| **Keycloak OIDC** | GitHub integration via Keycloak | Medium | Centralized identity management with GitHub teams |
| **GitHub Actions** | CI/CD automation | Low | Automated deployments and GitOps |

## Method 1: Keycloak OIDC Integration

This method configures Kubernetes to use Keycloak as the OIDC provider, which integrates with GitHub for authentication.

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

## Method 2: GitHub Actions Secure Kubernetes Access

For CI/CD workflows on bare metal clusters, GitHub Actions can securely authenticate with Kubernetes using multiple approaches. This section covers secure methods to access the Kubernetes API from GitHub Actions workflows.

### Approach 1: Service Account with Token-based Authentication

This approach uses Kubernetes service accounts with time-limited tokens for secure access.

#### Step 1: Create Service Account with Minimal Permissions

```yaml
# github-actions-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: github-actions-deployer
  namespace: ci-cd
  annotations:
    # Restrict to specific GitHub repository for security
    github.com/repository: "ITlusions/your-repo"
    github.com/organization: "ITlusions"
---
# Create namespace-specific role instead of cluster-wide admin
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: ci-cd
  name: github-actions-deployer-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "secrets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["networking.k8s.io"]
  resources: ["ingresses"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: github-actions-deployer-binding
  namespace: ci-cd
subjects:
- kind: ServiceAccount
  name: github-actions-deployer
  namespace: ci-cd
roleRef:
  kind: Role
  name: github-actions-deployer-role
  apiGroup: rbac.authorization.k8s.io
---
# Create a secret for the service account token (K8s 1.24+)
apiVersion: v1
kind: Secret
metadata:
  name: github-actions-deployer-token
  namespace: ci-cd
  annotations:
    kubernetes.io/service-account.name: github-actions-deployer
type: kubernetes.io/service-account-token
```

Apply the configuration:
```bash
# Create namespace first
kubectl create namespace ci-cd

# Apply RBAC configuration
kubectl apply -f github-actions-rbac.yaml
```

#### Step 2: Extract Service Account Token Securely

```bash
# Get the service account token
TOKEN=$(kubectl get secret github-actions-deployer-token -n ci-cd -o jsonpath='{.data.token}' | base64 -d)

# Get cluster CA certificate
CLUSTER_CA=$(kubectl get secret github-actions-deployer-token -n ci-cd -o jsonpath='{.data.ca\.crt}')

# Get cluster server URL
CLUSTER_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')

echo "Add these to your GitHub repository secrets:"
echo "KUBE_TOKEN: $TOKEN"
echo "KUBE_CA_CERT: $CLUSTER_CA"
echo "KUBE_SERVER: $CLUSTER_SERVER"
```

#### Step 3: Configure Secure GitHub Actions Workflow

```yaml
# .github/workflows/secure-deploy.yml
name: Secure Deploy to Kubernetes
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# Use minimal permissions for GitHub token
permissions:
  contents: read
  packages: read

jobs:
  security-checks:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Run security scanning
      run: |
        # Add your security scanning tools here
        echo "Running security checks..."
        
    - name: Validate Kubernetes manifests
      run: |
        # Validate YAML syntax and security policies
        find k8s/ -name "*.yaml" -o -name "*.yml" | xargs -I {} kubectl --dry-run=client apply -f {}

  deploy:
    needs: security-checks
    runs-on: ubuntu-latest
    # Only run on main branch for production deployments
    if: github.ref == 'refs/heads/main'
    environment: production  # Use GitHub environments for additional protection
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up kubectl
      uses: azure/setup-kubectl@v3
      with:
        version: 'v1.28.0'  # Pin specific version for consistency
    
    - name: Configure kubectl securely
      env:
        KUBE_TOKEN: ${{ secrets.KUBE_TOKEN }}
        KUBE_CA_CERT: ${{ secrets.KUBE_CA_CERT }}
        KUBE_SERVER: ${{ secrets.KUBE_SERVER }}
      run: |
        # Create secure kubeconfig
        mkdir -p ~/.kube
        
        # Write CA certificate to file
        echo "$KUBE_CA_CERT" | base64 -d > ~/.kube/ca.crt
        
        # Create kubeconfig with token authentication
        kubectl config set-cluster kubernetes \
          --server="$KUBE_SERVER" \
          --certificate-authority=~/.kube/ca.crt
        
        kubectl config set-credentials github-actions \
          --token="$KUBE_TOKEN"
        
        kubectl config set-context github-actions \
          --cluster=kubernetes \
          --user=github-actions \
          --namespace=ci-cd
        
        kubectl config use-context github-actions
        
        # Test connection
        kubectl auth can-i get pods -n ci-cd
    
    - name: Deploy to cluster
      run: |
        # Apply manifests with explicit namespace
        kubectl apply -f k8s/ -n ci-cd
        
        # Wait for rollout to complete
        kubectl rollout status deployment/your-app -n ci-cd --timeout=300s
        
        # Verify deployment
        kubectl get pods -n ci-cd -l app=your-app
    
    - name: Cleanup sensitive files
      if: always()
      run: |
        rm -f ~/.kube/ca.crt
        rm -f ~/.kube/config
```

### Approach 2: GitHub OIDC with Workload Identity

For enhanced security, use GitHub's OIDC provider to authenticate without long-lived tokens.

#### Step 1: Configure OIDC Trust Relationship

```yaml
# github-oidc-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: github-oidc-deployer
  namespace: ci-cd
  annotations:
    # Map to GitHub OIDC claims
    github.com/repository: "ITlusions/your-repo"
    github.com/actor: "github-actions[bot]"
    github.com/workflow: "deploy"
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: ci-cd
  name: github-oidc-deployer-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: github-oidc-deployer-binding
  namespace: ci-cd
subjects:
- kind: ServiceAccount
  name: github-oidc-deployer
  namespace: ci-cd
roleRef:
  kind: Role
  name: github-oidc-deployer-role
  apiGroup: rbac.authorization.k8s.io
```

#### Step 2: Configure API Server for GitHub OIDC (requires cluster admin)

Add these flags to your API server configuration:

```yaml
# Add to /etc/kubernetes/manifests/kube-apiserver.yaml
spec:
  containers:
  - command:
    - kube-apiserver
    # ... other flags ...
    - --oidc-issuer-url=https://token.actions.githubusercontent.com
    - --oidc-client-id=sts.amazonaws.com  # or your custom audience
    - --oidc-username-claim=actor
    - --oidc-groups-claim=repository
    - --oidc-username-prefix=github:
    - --oidc-groups-prefix=github:
```

#### Step 3: GitHub Actions Workflow with OIDC

```yaml
# .github/workflows/oidc-deploy.yml
name: OIDC Deploy to Kubernetes
on:
  push:
    branches: [main]

# Required permissions for OIDC
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Configure AWS credentials (if using AWS for intermediate auth)
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: arn:aws:iam::ACCOUNT:role/GitHubOIDC
        aws-region: us-west-2
        
    - name: Get OIDC token
      id: oidc
      run: |
        # Get GitHub OIDC token
        OIDC_TOKEN=$(curl -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
          "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=kubernetes" | jq -r .value)
        echo "token=$OIDC_TOKEN" >> $GITHUB_OUTPUT
        
    - name: Deploy with OIDC token
      env:
        OIDC_TOKEN: ${{ steps.oidc.outputs.token }}
        KUBE_SERVER: ${{ secrets.KUBE_SERVER }}
        KUBE_CA_CERT: ${{ secrets.KUBE_CA_CERT }}
      run: |
        # Configure kubectl with OIDC token
        kubectl config set-cluster kubernetes \
          --server="$KUBE_SERVER" \
          --certificate-authority-data="$KUBE_CA_CERT"
        
        kubectl config set-credentials github-oidc \
          --token="$OIDC_TOKEN"
        
        kubectl config set-context github-oidc \
          --cluster=kubernetes \
          --user=github-oidc \
          --namespace=ci-cd
        
        kubectl config use-context github-oidc
        
        # Deploy
        kubectl apply -f k8s/ -n ci-cd
```

### Security Best Practices for GitHub Actions

#### 1. Secrets Management

```yaml
# Store sensitive data in GitHub secrets, not in code
secrets:
  KUBE_TOKEN: ${{ secrets.KUBE_TOKEN }}
  KUBE_CA_CERT: ${{ secrets.KUBE_CA_CERT }}
  KUBE_SERVER: ${{ secrets.KUBE_SERVER }}
  REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
```

#### 2. Environment Protection

Configure GitHub environments with protection rules:
- Required reviewers for production deployments
- Deployment branches restriction
- Environment secrets scope

#### 3. Network Security

```yaml
# Restrict egress from GitHub Actions runners
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: github-actions-network-policy
  namespace: ci-cd
spec:
  podSelector:
    matchLabels:
      deployed-by: github-actions
  policyTypes:
  - Egress
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS only
```

#### 4. Audit and Monitoring

```bash
# Monitor GitHub Actions deployments
kubectl logs -n ci-cd -l app=your-app | grep "github-actions"

# Audit service account usage
kubectl get events -n ci-cd --field-selector involvedObject.kind=ServiceAccount

# Check RBAC permissions
kubectl auth can-i --list --as=system:serviceaccount:ci-cd:github-actions-deployer -n ci-cd
```

#### 5. Token Rotation

```bash
#!/bin/bash
# Script to rotate GitHub Actions service account tokens
NAMESPACE="ci-cd"
SA_NAME="github-actions-deployer"
SECRET_NAME="github-actions-deployer-token"

# Delete existing secret
kubectl delete secret $SECRET_NAME -n $NAMESPACE

# Create new secret
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: $SECRET_NAME
  namespace: $NAMESPACE
  annotations:
    kubernetes.io/service-account.name: $SA_NAME
type: kubernetes.io/service-account-token
EOF

# Wait for token generation
sleep 5

# Get new token
NEW_TOKEN=$(kubectl get secret $SECRET_NAME -n $NAMESPACE -o jsonpath='{.data.token}' | base64 -d)
echo "New token: $NEW_TOKEN"
echo "Update your GitHub secrets with this new token"
```

#### 6. Least Privilege Access

```yaml
# Example of minimal permissions for different deployment scenarios

# For applications that only need to update their own deployment
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: app-deployer
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  resourceNames: ["my-app"]  # Restrict to specific deployment
  verbs: ["get", "update", "patch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]  # Read-only for status checks

---
# For infrastructure deployments
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: infrastructure
  name: infra-deployer
rules:
- apiGroups: [""]
  resources: ["services", "configmaps", "secrets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "daemonsets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["networking.k8s.io"]
  resources: ["networkpolicies", "ingresses"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

## Setup Client Access for Keycloak Authentication

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
      - --oidc-client-secret=kubernetes-client-secret
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
**Solution**: Verify the user is a member of the specified GitHub organization

**Problem**: "Access denied"  
**Solution**: Check the RBAC configuration matches your GitHub teams



# Check for authorization decisions
kubectl logs -n kube-system kube-apiserver-master-node | grep -i rbac

# Monitor Keycloak logs  
kubectl logs -n keycloak deployment/keycloak -f
```

That's it! Your bare metal Kubernetes cluster now authenticates users via GitHub through Keycloak with team-based authorization.

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