# OIDC IdP Setup Guide

This guide explains how to set up and use the OpenID Connect (OIDC) Identity Provider functionality that runs alongside the SAML IdP.

## Overview

The OIDC IdP shares the same user and role database as the SAML IdP, providing a unified identity management system. Users created for SAML authentication can also authenticate via OIDC.

## Features

- **OpenID Connect 1.0 compliant**: Full implementation of OIDC Core specification
- **Authorization Code Flow**: Secure OAuth 2.0 authorization code grant
- **JWT Token Support**: ID tokens and access tokens signed with RS256
- **User Info Endpoint**: Standard OIDC userinfo endpoint
- **Discovery Endpoint**: Well-known OpenID configuration for automatic client setup
- **Shared User Base**: Same users and roles as SAML IdP
- **MFA Support**: Supports the same MFA configuration as SAML IdP

## OIDC Endpoints

After deployment, your OIDC IdP will expose the following endpoints:

| Endpoint | URL | Description |
|----------|-----|-------------|
| Discovery | `${API_URL}/.well-known/openid-configuration` | OpenID Connect discovery document |
| Authorization | `${API_URL}/oauth2/authorize` | OAuth 2.0 authorization endpoint |
| Token | `${API_URL}/oauth2/token` | OAuth 2.0 token endpoint |
| UserInfo | `${API_URL}/oauth2/userinfo` | OIDC userinfo endpoint |
| JWKS | `${API_URL}/oauth2/jwks` | JSON Web Key Set for token verification |

Where `${API_URL}` is your API Gateway URL from Terraform outputs.

## Setup Instructions

### 1. Generate OIDC JWT Signing Keys

Generate RSA key pair for signing JWT tokens:

```bash
make generate-oidc-keys
```

Or manually:

```bash
./scripts/generate-oidc-keys.sh
```

This creates:
- `certs/oidc-private-key.pem` - Private key for signing tokens
- `certs/oidc-public-key.pem` - Public key for token verification

### 2. Deploy Infrastructure

Build Lambda functions and deploy with Terraform:

```bash
# Build Lambda functions
make build-layer

# Deploy infrastructure
terraform init
terraform plan
terraform apply
```

### 3. Upload OIDC Keys to SSM

After deployment, upload the JWT signing keys to SSM Parameter Store:

```bash
make upload-oidc-keys
```

Or manually:

```bash
./scripts/upload-oidc-keys.sh
```

This uploads:
- Private key to: `/simple-saml-idp/dev/oidc/private_key` (SecureString)
- Public key to: `/simple-saml-idp/dev/oidc/public_key` (String)

### 4. Get OIDC Endpoints

Retrieve your OIDC endpoint URLs:

```bash
terraform output oidc_discovery_url
terraform output oidc_authorization_endpoint
terraform output oidc_token_endpoint
terraform output oidc_userinfo_endpoint
terraform output oidc_jwks_uri
```

### 5. Test OIDC Discovery

Verify the OIDC IdP is working:

```bash
curl $(terraform output -raw oidc_discovery_url)
```

You should receive a JSON response with the OpenID Connect configuration.

## User Management

OIDC uses the same user database as the SAML IdP. Users created for SAML can authenticate via OIDC without any additional configuration.

### Add Users

Users are added the same way as for SAML:

```bash
make add-user USERNAME=john.doe PASSWORD=MySecurePassword123
```

### Add Roles

Roles are also shared:

```bash
make add-role USERNAME=john.doe \
  ROLE_ARN="arn:aws:iam::123456789012:role/AdminRole" \
  ACCOUNT_NAME="Production"
```

## Configuring OIDC Clients

### Generic OIDC Client Configuration

To integrate an application with your OIDC IdP:

1. **Issuer/Discovery URL**: Use the discovery endpoint URL from outputs
2. **Client ID**: Any string identifier for your application
3. **Client Secret**: (Optional) Not currently enforced, but recommended for production
4. **Redirect URI**: Your application's callback URL
5. **Scopes**: `openid profile email` (all supported)
6. **Response Type**: `code` (authorization code flow)

### Example: Grafana OIDC Configuration

Add to your Grafana configuration:

```ini
[auth.generic_oauth]
enabled = true
name = Simple SAML IdP
allow_sign_up = true
client_id = grafana-client
client_secret = your-secret
scopes = openid profile email
auth_url = https://your-api-gateway-url/oauth2/authorize
token_url = https://your-api-gateway-url/oauth2/token
api_url = https://your-api-gateway-url/oauth2/userinfo
use_pkce = true
```

### Example: Kubernetes OIDC Configuration

Configure kubectl to use OIDC authentication:

```yaml
users:
- name: oidc-user
  user:
    auth-provider:
      config:
        client-id: kubernetes
        idp-issuer-url: https://your-api-gateway-url
        idp-certificate-authority-data: <base64-encoded-ca-cert>
      name: oidc
```

## Token Claims

### ID Token Claims

The ID token includes the following claims:

```json
{
  "iss": "https://your-idp-entity-id",
  "sub": "username",
  "aud": "client-id",
  "exp": 1234567890,
  "iat": 1234567890,
  "preferred_username": "username",
  "email": "user@example.com",
  "name": "User Name",
  "nonce": "client-provided-nonce"
}
```

### Access Token Claims

The access token includes:

```json
{
  "iss": "https://your-idp-entity-id",
  "sub": "username",
  "exp": 1234567890,
  "iat": 1234567890,
  "preferred_username": "username",
  "email": "user@example.com",
  "name": "User Name",
  "groups": ["arn:aws:iam::123456789012:role/AdminRole"]
}
```

### UserInfo Response

The userinfo endpoint returns:

```json
{
  "sub": "username",
  "preferred_username": "username",
  "email": "user@example.com",
  "name": "User Name",
  "given_name": "User",
  "family_name": "Name",
  "groups": ["arn:aws:iam::123456789012:role/AdminRole"]
}
```

## Authentication Flow

1. **Authorization Request**: Client redirects user to `/oauth2/authorize` with parameters:
   - `client_id`: Application identifier
   - `redirect_uri`: Callback URL
   - `response_type`: `code`
   - `scope`: `openid` (required), `profile`, `email`
   - `state`: CSRF protection token
   - `nonce`: Replay protection (for ID token)

2. **User Authentication**: User enters credentials on login page (GET shows form, POST submits)

3. **Authorization Code**: IdP redirects back to client with authorization code

4. **Token Exchange**: Client POSTs to `/oauth2/token` with:
   - `grant_type`: `authorization_code`
   - `code`: Authorization code from step 3
   - `redirect_uri`: Must match the one from step 1
   - `client_id`: Application identifier

5. **Token Response**: IdP returns:
   - `access_token`: JWT for API access
   - `id_token`: JWT with user identity claims
   - `refresh_token`: Token for getting new access tokens
   - `token_type`: `Bearer`
   - `expires_in`: Token lifetime in seconds

6. **API Access**: Client uses access token to call `/oauth2/userinfo` or other APIs

## Security Considerations

### Current Implementation

- **Token Signing**: RS256 (RSA with SHA-256)
- **Token Expiry**: 1 hour for access/ID tokens
- **Authorization Code**: 5-minute expiry, single-use
- **Shared User Database**: Same bcrypt/SHA256 hashed passwords as SAML
- **MFA Support**: TOTP-based MFA when enabled for user

### Production Recommendations

1. **Implement Client Authentication**: Add client secret validation in token endpoint
2. **Use DynamoDB for Session Storage**: Replace in-memory storage with DynamoDB
3. **Add Refresh Token Support**: Implement refresh token rotation
4. **Implement PKCE**: Add Proof Key for Code Exchange for public clients
5. **Rate Limiting**: Use API Gateway throttling or AWS WAF
6. **Add Logging**: Enhanced CloudWatch logging for security events
7. **Key Rotation**: Implement automatic key rotation for JWT signing keys
8. **Add Consent Screen**: Implement OAuth consent flow
9. **Client Registration**: Add dynamic client registration endpoint
10. **Scope-based Access Control**: Implement fine-grained scope validation

## Troubleshooting

### Discovery Endpoint Returns Error

- Check Lambda logs: `make logs-lambda`
- Verify OIDC keys are uploaded to SSM
- Check API Gateway configuration

### Token Validation Fails

- Verify public key is correctly uploaded to SSM
- Check token expiry (`exp` claim)
- Verify issuer (`iss` claim) matches your IDP_ENTITY_ID

### Authorization Code Invalid

- Authorization codes expire after 5 minutes
- Codes can only be used once
- Verify client_id and redirect_uri match

### UserInfo Endpoint Returns 401

- Verify Bearer token is present in Authorization header
- Check token hasn't expired
- Verify token signature with public key

## Cost Estimation

OIDC endpoints use the same infrastructure as SAML:

- **API Gateway**: $1.00 per million requests
- **Lambda**: $0.20 per 1M requests + compute time
- **Additional cost for 1000 users with 20 logins/day**: ~$2-3/month

## Monitoring

Monitor OIDC usage:

```bash
# Lambda logs
make logs-lambda

# API Gateway logs
make logs-api
```

Key metrics to monitor:
- Token generation rate
- Failed authentication attempts
- Token validation errors
- API response times

## Limitations

Current implementation limitations:

1. **In-Memory Storage**: Auth codes stored in Lambda memory (lost on cold start)
2. **No Client Secrets**: Client authentication not enforced
3. **No Refresh Token Implementation**: Refresh tokens generated but not validated
4. **Limited Flows**: Only authorization code flow supported
5. **No Dynamic Registration**: Clients must be pre-configured

These limitations are suitable for development/testing but should be addressed for production use.

## Next Steps

- Review [USER_ROLE_MANAGEMENT.md](USER_ROLE_MANAGEMENT.md) for managing users and roles
- See [MFA_SETUP.md](MFA_SETUP.md) for Multi-Factor Authentication setup
- Check main [README.md](../README.md) for general deployment information
