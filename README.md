# Simple SAML/OIDC IdP for AWS and Third-Party Applications

A serverless Identity Provider (IdP) built with Terraform and AWS services. Supports both SAML 2.0 and OpenID Connect (OIDC) protocols. Originally designed for AWS Console Single Sign-On (SSO), it now supports integration with multiple SAML and OIDC-enabled applications including Grafana Cloud, AWS Console, Kubernetes, and any SAML 2.0 or OIDC-compatible service. Users can authenticate and access multiple applications through unified identity management.

## 🚀 Quick Start

**Want to get started immediately?** See [QUICKSTART.md](docs/QUICKSTART.md) for a 15-minute setup guide.

For detailed deployment instructions, see [DEPLOYMENT.md](docs/DEPLOYMENT.md).

For OIDC setup, see [OIDC_SETUP.md](docs/OIDC_SETUP.md).

## Features

- **Dual Protocol Support**: Both SAML 2.0 and OpenID Connect (OIDC) on the same infrastructure
- **Serverless Architecture**: Built entirely on AWS serverless services (Lambda, API Gateway, DynamoDB, S3)
- **Multi-Application Support**: Works with AWS Console, Grafana Cloud, Kubernetes, and any SAML 2.0 or OIDC compatible application
- **Unified User Management**: Single user/role database shared between SAML and OIDC
- **Flexible SAML Attributes**: Configure custom SAML attributes per role with `attr_` prefix for easy management (see [CUSTOM_ATTRIBUTES.md](docs/CUSTOM_ATTRIBUTES.md))
- **OIDC Standard Compliance**: Full OpenID Connect 1.0 support with JWT tokens, discovery endpoint, and userinfo
- **Multi-Account SSO**: Support for accessing multiple AWS accounts through a single login
- **Multi-Factor Authentication (MFA)**: TOTP-based MFA compatible with Google Authenticator (see [MFA_SETUP.md](docs/MFA_SETUP.md))
- **Role Selection**: Users can choose from multiple IAM roles before accessing the AWS Console
- **Configurable ACS URL**: Easy configuration for different SAML integrations
- **Pay-per-use**: All resources use on-demand billing with no fixed costs
- **Secure**: Uses AWS SSM Parameter Store for secrets, DynamoDB encryption at rest, and HTTPS everywhere
- **Easy Deployment**: Deploy entire infrastructure with a single Terraform command

## Architecture

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌─────────────────┐      ┌──────────────────┐
│  CloudFront     │─────▶│  S3 Bucket       │
│  (Optional)     │      │  (Login Page)    │
└─────────────────┘      └──────────────────┘
       │
       ▼
┌─────────────────┐      ┌──────────────────────┐
│  API Gateway    │─────▶│  Lambda Functions    │
│  (HTTP API)     │      │  - SAML Processor    │
│                 │      │  - OIDC Processor    │
└─────────────────┘      └──────────┬───────────┘
                                    │
                      ┌─────────────┼─────────────┐
                      ▼             ▼             ▼
                ┌──────────┐  ┌──────────┐  ┌──────────┐
                │DynamoDB  │  │DynamoDB  │  │   SSM    │
                │ Users    │  │  Roles   │  │Parameter │
                │  Table   │  │  Table   │  │  Store   │
                └──────────┘  └──────────┘  └──────────┘
```

## AWS Resources Created

- **API Gateway (HTTP API)**: Handles SAML endpoints (metadata, SSO, login)
- **Lambda Function**: Processes authentication and generates SAML assertions
- **DynamoDB Tables**: Stores user credentials and role mappings (on-demand billing)
- **S3 Bucket**: Hosts static login page with role selection interface
- **CloudFront Distribution** (optional): CDN for login page
- **SSM Parameters**: Secure storage for SAML signing certificate and private key
- **IAM Roles & Policies**: Minimal permissions for Lambda execution
- **CloudWatch Log Groups**: For Lambda and API Gateway logs

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- Python 3.x (for building Lambda layer)
- OpenSSL (for generating SAML certificates)
- Make (optional, for using Makefile commands)

## Documentation

- **[QUICKSTART.md](docs/QUICKSTART.md)**: Get up and running in 15 minutes
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)**: Detailed deployment guide with step-by-step instructions
- **[OIDC_SETUP.md](docs/OIDC_SETUP.md)**: Complete guide for OpenID Connect (OIDC) IdP setup and configuration
- **[AUTHENTICATION_FLOW.md](docs/AUTHENTICATION_FLOW.md)**: Understand how the SAML authentication works
- **[MFA_SETUP.md](docs/MFA_SETUP.md)**: Complete guide for Multi-Factor Authentication setup and usage
- **[IAM_POLICY.md](docs/IAM_POLICY.md)**: Required IAM permissions for deployment and operations
- **[USER_ROLE_MANAGEMENT.md](docs/USER_ROLE_MANAGEMENT.md)**: Complete guide for managing users and roles via Lambda
- **[QUICKSTART_USER_MANAGEMENT.md](docs/QUICKSTART_USER_MANAGEMENT.md)**: Quick reference for user/role operations

## Quick Start (Summary)

For detailed instructions, see [QUICKSTART.md](docs/QUICKSTART.md).

### 1. Clone the Repository

```bash
git clone https://github.com/faccomichele/simple-saml-idp.git
cd simple-saml-idp
```

### 2. Generate SAML Signing Certificate

```bash
./scripts/generate-saml-cert.sh
```

This creates a self-signed certificate and private key in the `certs/` directory.

### 3. Configure Terraform Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your configuration
```

Required variables:
- `idp_entity_id`: Unique identifier for your IdP (e.g., "https://saml-idp.example.com")
- `idp_base_url`: Will be the API Gateway URL (can be updated after deployment)
- `aws_region`: AWS region for deployment (default: us-east-1)

### 4. Build Lambda Layer (Optional)

If you need to update dependencies:

```bash
./scripts/setup.sh
```

### 5. Deploy with Terraform

```bash
terraform init
terraform plan
terraform apply
```

### 6. Upload SAML Certificates to SSM

After deployment, store your certificates in SSM Parameter Store:

```bash
aws ssm put-parameter \
  --name "/simple-saml-idp/dev/saml/private_key" \
  --value "$(cat certs/saml-private-key.pem)" \
  --type SecureString \
  --overwrite

aws ssm put-parameter \
  --name "/simple-saml-idp/dev/saml/certificate" \
  --value "$(cat certs/saml-certificate.pem)" \
  --type String \
  --overwrite
```

### 7. Update Login Page Configuration

Get your API Gateway URL from Terraform outputs:

```bash
terraform output api_gateway_url
```

Update the `static/index.html` file with your API Gateway URL:

```javascript
const API_BASE_URL = 'https://your-api-id.execute-api.us-east-1.amazonaws.com/dev';
```

Upload the updated login page to S3:

```bash
aws s3 cp static/index.html s3://$(terraform output -raw s3_bucket_name)/index.html
```

If using CloudFront, invalidate the cache:

```bash
aws cloudfront create-invalidation \
  --distribution-id $(terraform output -raw cloudfront_distribution_id) \
  --paths "/*"
```

## Configuration

### Adding Users

Create users in DynamoDB using the helper script:

```bash
./scripts/add-user.sh simple-saml-idp-users-dev john.doe MySecurePassword123
```

Or manually add to DynamoDB (see `examples/dynamodb-user.json` for format).

**Note**: The password is hashed using SHA256. For production, consider implementing bcrypt or similar.

### Adding Role Mappings

Map AWS IAM roles to users:

```bash
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe \
  "arn:aws:iam::123456789012:role/AdminRole" \
  "Production Account"
```

You can add multiple roles for the same user to different accounts.

### Configure AWS Accounts for SAML Federation

In each AWS account you want to enable SSO for:

1. **Create a SAML Identity Provider**:
   ```bash
   aws iam create-saml-provider \
     --name SimpleSAMLIdP \
     --saml-metadata-document file://saml-metadata.xml
   ```

   Get the metadata from: `https://your-api-gateway-url/metadata`

2. **Create or Update IAM Role** with trust policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Federated": "arn:aws:iam::ACCOUNT_ID:saml-provider/SimpleSAMLIdP"
         },
         "Action": "sts:AssumeRoleWithSAML",
         "Condition": {
           "StringEquals": {
             "SAML:aud": "https://signin.aws.amazon.com/saml"
           }
         }
       }
     ]
   }
   ```

3. **Attach policies** to the role based on desired permissions.

### Configuring for Different Applications

The IdP can be configured to work with various SAML 2.0 compatible applications. Each role mapping in DynamoDB can have its own `acs_url` (Assertion Consumer Service URL), allowing different roles to redirect to different applications.

#### Adding Roles with ACS URL

When adding a role mapping, specify the ACS URL for the target application:

**AWS Console (Default)**

```bash
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe \
  "arn:aws:iam::123456789012:role/AdminRole" \
  "Production Account" \
  "https://signin.aws.amazon.com/saml"
```

Or omit the ACS URL parameter to use AWS Console as default:

```bash
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe \
  "arn:aws:iam::123456789012:role/AdminRole" \
  "Production Account"
```

**Grafana Cloud**

For Grafana Cloud, you can configure custom SAML attributes directly in DynamoDB. Use a descriptive role identifier instead of an AWS IAM ARN:

```bash
# Using AWS CLI to invoke the Lambda function with custom attributes
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --payload file://examples/lambda-create-role-grafana.json \
  response.json

# Or manually add to DynamoDB with attributes like:
# - attr_email: user email
# - attr_display_name: user's display name
# - attr_groups: Grafana role (Viewer, Editor, Admin)
```

See [CUSTOM_ATTRIBUTES.md](docs/CUSTOM_ATTRIBUTES.md) for detailed Grafana configuration examples.

**Legacy Grafana Setup (without custom attributes)**

```bash
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe \
  "grafana:viewer" \
  "Grafana Monitoring" \
  "https://YOUR-STACK.grafana.net/saml/acs"
```

**Other SAML Applications**

```bash
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe \
  "arn:aws:iam::123456789012:role/AppRole" \
  "Custom Application" \
  "https://your-app-domain.com/saml/acs"
```

#### Multi-Application Support

You can configure a single user to access multiple applications by creating separate role mappings with different ACS URLs:

```bash
# AWS Console access with AWS-specific attributes
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe \
  "arn:aws:iam::123456789012:role/AdminRole" \
  "AWS Production" \
  "https://signin.aws.amazon.com/saml"

# Grafana Cloud access with custom attributes (use Lambda function)
# See examples/lambda-create-role-grafana.json for the full configuration
```

When the user logs in, they'll see all available roles and can choose which application to access.

#### Manual Role Configuration

You can also manually add roles to DynamoDB with the `acs_url` field:

```json
{
  "username": "john.doe",
  "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
  "account_name": "Production Account",
  "account_id": "123456789012",
  "acs_url": "https://signin.aws.amazon.com/saml",
  "description": "Full administrator access",
  "created_at": "2024-01-08T00:00:00Z"
}
```

**Note**: If `acs_url` is not specified in a role, it defaults to AWS Console (`https://signin.aws.amazon.com/saml`) for backward compatibility.

## Usage

1. Navigate to your login page URL (from Terraform outputs)
2. Enter your username and password
3. Select the AWS account and role you want to access
4. Click "Continue to AWS Console"
5. You'll be automatically redirected to the AWS Console with the selected role

## Security Considerations

### Current Implementation

- Password hashing: SHA256 (simple but not recommended for production)
- Secrets storage: AWS SSM Parameter Store with encryption
- API: HTTPS only via API Gateway
- Storage: DynamoDB encryption at rest enabled
- S3: Private bucket with CloudFront OAI access

### Production Recommendations

1. **Implement stronger password hashing**: Use bcrypt or Argon2
2. **Add MFA support**: Implement TOTP or SMS-based MFA
3. **Enable AWS WAF**: Protect API Gateway from common attacks
4. **Add rate limiting**: Prevent brute force attacks
5. **Implement session management**: Track and invalidate sessions
6. **Add audit logging**: Log all authentication attempts
7. **Use custom domain**: Configure custom domain with SSL certificate
8. **Implement IP whitelisting**: Restrict access to known IP ranges
9. **Regular key rotation**: Rotate SAML certificates periodically
10. **Monitor and alert**: Set up CloudWatch alarms for failed logins

## Cost Estimation

All resources use on-demand pricing:

- **API Gateway**: $1.00 per million requests
- **Lambda**: $0.20 per 1M requests + compute time
- **DynamoDB**: On-demand, pay per request
- **S3**: $0.023 per GB + requests
- **CloudFront**: $0.085 per GB transfer (first 10 TB)
- **CloudWatch Logs**: $0.50 per GB ingested

**Estimated monthly cost for 1000 users with 20 logins/day**: ~$5-10

## Troubleshooting

### Login page shows "Connection error"

- Ensure API Gateway URL is correctly configured in `static/index.html`
- Check API Gateway logs in CloudWatch

### "Invalid credentials" error

- Verify user exists in DynamoDB users table
- Check password hash matches (use scripts/add-user.sh)

### "No roles available" error

- Ensure role mappings exist in DynamoDB roles table
- Verify role ARNs are correct
- Check `allowed_aws_accounts` variable if configured

### AWS Console shows "Invalid SAML Response"

- Verify SAML certificate is correctly stored in SSM
- Check SAML provider exists in target AWS account
- Ensure role trust policy includes SAML provider
- Review Lambda function logs

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

**Note**: This will delete all DynamoDB data. Export important data first.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for AWS Console SSO use cases
- Designed for simplicity and cost-effectiveness
- Inspired by the need for lightweight SAML IdP solutions

## Support

For issues and questions:
- Open an issue on GitHub
- Review CloudWatch logs for debugging
- Check AWS service quotas and limits
