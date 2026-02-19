# OIDC Integration Quick Reference

Quick reference for integrating applications with the Simple SAML/OIDC IdP.

## Prerequisites

- IdP deployed and accessible
- OIDC keys generated and uploaded to SSM
- User accounts created

## Get Your OIDC Endpoints

```bash
terraform output oidc_discovery_url
terraform output oidc_authorization_endpoint
terraform output oidc_token_endpoint
terraform output oidc_userinfo_endpoint
terraform output oidc_jwks_uri
```

## Common Integration Patterns

### Grafana OIDC Integration

Add to Grafana configuration (`grafana.ini` or environment variables):

```ini
[auth.generic_oauth]
enabled = true
name = Simple IdP
allow_sign_up = true
auto_login = false
client_id = grafana
client_secret = your-secret-here
scopes = openid email profile
auth_url = https://your-api-gateway-url/oauth2/authorize
token_url = https://your-api-gateway-url/oauth2/token
api_url = https://your-api-gateway-url/oauth2/userinfo
use_pkce = true
role_attribute_path = contains(groups[*], 'Admin') && 'Admin' || 'Viewer'
```

### Kubernetes OIDC Authentication

Configure your API server:

```yaml
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: https://kubernetes-api-server:6443
  name: kubernetes
users:
- name: oidc-user
  user:
    auth-provider:
      name: oidc
      config:
        idp-issuer-url: https://your-api-gateway-url
        client-id: kubernetes
        client-secret: your-secret-here
        id-token: <token-from-login>
        refresh-token: <refresh-token>
contexts:
- context:
    cluster: kubernetes
    user: oidc-user
  name: oidc-context
current-context: oidc-context
```

### Generic Application Integration

For any OIDC-compatible application:

1. **Issuer/Discovery URL**: `https://your-api-gateway-url/.well-known/openid-configuration`
2. **Client ID**: Choose any identifier (e.g., "myapp")
3. **Client Secret**: (Optional, not currently enforced)
4. **Redirect URI**: Your app's callback URL
5. **Scopes**: `openid profile email`

### Testing with curl

Test the discovery endpoint:

```bash
curl https://your-api-gateway-url/.well-known/openid-configuration | jq
```

Manual authorization flow:

```bash
# 1. Get authorization code (opens browser)
open "https://your-api-gateway-url/oauth2/authorize?client_id=test&redirect_uri=http://localhost:8080/callback&response_type=code&scope=openid&state=random123"

# 2. After login, extract code from redirect URL
CODE="code-from-redirect"

# 3. Exchange code for tokens
curl -X POST https://your-api-gateway-url/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=$CODE" \
  -d "redirect_uri=http://localhost:8080/callback" \
  -d "client_id=test" | jq

# 4. Use access token to get user info
ACCESS_TOKEN="token-from-previous-response"
curl https://your-api-gateway-url/oauth2/userinfo \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

## Configuration Variables

### Basic Configuration

In your `terraform.tfvars`:

```hcl
# Required
idp_entity_id = "https://idp.example.com"
idp_base_url = "https://your-api-gateway-url"

# OIDC Security
allowed_oidc_redirect_uris = [
  "https://app1.example.com/oauth/callback",
  "https://app2.example.com/auth/callback",
  "http://localhost:8080/callback"  # For development
]
```

### Development vs Production

**Development** (default):
- Allows localhost and https redirect URIs
- No client secret validation
- In-memory session storage

**Production** (recommended):
```hcl
allowed_oidc_redirect_uris = [
  # List all allowed redirect URIs explicitly
  "https://grafana.example.com/login/generic_oauth",
  "https://app.example.com/oauth/callback"
]
```

## Token Claims

### ID Token

```json
{
  "iss": "https://idp.example.com",
  "sub": "john.doe",
  "aud": "client-id",
  "exp": 1234567890,
  "iat": 1234567890,
  "preferred_username": "john.doe",
  "email": "john.doe@example.com",
  "name": "John Doe",
  "nonce": "random-nonce"
}
```

### Access Token

```json
{
  "iss": "https://idp.example.com",
  "sub": "john.doe",
  "exp": 1234567890,
  "iat": 1234567890,
  "preferred_username": "john.doe",
  "email": "john.doe@example.com",
  "name": "John Doe",
  "groups": ["arn:aws:iam::123456789012:role/AdminRole"]
}
```

## Troubleshooting

### "invalid_request: Invalid redirect_uri"

**Cause**: Redirect URI not in allowed list

**Solution**: Add the redirect URI to `allowed_oidc_redirect_uris` in terraform.tfvars:

```hcl
allowed_oidc_redirect_uris = [
  "https://your-app.example.com/callback"
]
```

Then redeploy:
```bash
terraform apply
```

### "Invalid token" when calling userinfo

**Cause**: Token expired or invalid signature

**Solutions**:
- Check token expiration (1 hour by default)
- Verify OIDC public key is correctly uploaded to SSM
- Use the discovery endpoint to get the correct JWKS URI

### Authorization code invalid

**Causes**:
- Code expired (5 minutes)
- Code already used
- Lambda cold start (in-memory storage limitation)

**Solutions**:
- Request a new authorization code
- For production: implement DynamoDB storage for auth codes

## User Management

Users are shared between SAML and OIDC:

```bash
# Add user
make add-user USERNAME=john.doe PASSWORD=SecurePass123

# Add role
make add-role USERNAME=john.doe \
  ROLE_ARN="arn:aws:iam::123456789012:role/Admin" \
  ACCOUNT_NAME="Production"
```

## Monitoring

```bash
# Check Lambda logs
make logs-lambda

# Check API Gateway logs
make logs-api

# View OIDC discovery
curl https://your-api-gateway-url/.well-known/openid-configuration | jq

# Test JWKS
curl https://your-api-gateway-url/oauth2/jwks | jq
```

## Security Best Practices

1. ✅ Configure `allowed_oidc_redirect_uris` explicitly for production
2. ✅ Use HTTPS for all redirect URIs (except localhost in dev)
3. ✅ Rotate JWT signing keys periodically
4. ✅ Enable MFA for sensitive accounts
5. ✅ Monitor failed authentication attempts
6. ✅ Use API Gateway throttling
7. ⚠️ Implement client secrets in production (see docs)
8. ⚠️ Use DynamoDB for session storage in production (see docs)

## More Information

- [Complete OIDC Setup Guide](OIDC_SETUP.md)
- [User Management Guide](USER_ROLE_MANAGEMENT.md)
- [MFA Setup Guide](MFA_SETUP.md)
- [Main README](../README.md)
