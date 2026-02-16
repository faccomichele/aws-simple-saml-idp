# Deployment Guide

This guide provides detailed step-by-step instructions for deploying the Simple SAML IdP infrastructure.

## Pre-Deployment Checklist

- [ ] AWS CLI installed and configured
- [ ] Terraform >= 1.0 installed
- [ ] Python 3.x installed
- [ ] OpenSSL installed
- [ ] AWS credentials with appropriate permissions
- [ ] Target AWS accounts ready for SAML configuration

## Deployment Steps

### Phase 1: Initial Setup (15 minutes)

#### 1.1 Generate SAML Certificates

```bash
./scripts/generate-saml-cert.sh
```

**Output**: Creates `certs/saml-private-key.pem` and `certs/saml-certificate.pem`

**Important**: Keep these files secure. They are used to sign SAML assertions.

#### 1.2 Configure Terraform Variables

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set:

```hcl
aws_region  = "us-east-1"          # Your preferred region
environment = "dev"                 # or "staging", "prod"
project_name = "simple-saml-idp"   # Keep default or customize

# You'll update this after deployment - use placeholder for now
idp_entity_id = "https://saml-idp.yourdomain.com"
idp_base_url  = "https://placeholder.execute-api.us-east-1.amazonaws.com/dev"

session_duration_seconds = 3600     # 1 hour (900-43200)
enable_cloudfront = true            # Set to false to skip CloudFront

# Optional: Restrict to specific AWS accounts
allowed_aws_accounts = []           # Empty = allow all
```

#### 1.3 Build Lambda Layer (Optional)

If you modified `lambda/layer/requirements.txt`:

```bash
./scripts/setup.sh
```

This installs Python dependencies into `lambda/layer/python/`.

### Phase 2: Infrastructure Deployment (10 minutes)

#### 2.1 Initialize Terraform

```bash
terraform init
```

Expected output: "Terraform has been successfully initialized!"

#### 2.2 Review Deployment Plan

```bash
terraform plan
```

Review the resources that will be created (~20 resources).

#### 2.3 Deploy Infrastructure

```bash
terraform apply
```

Type `yes` when prompted.

**Duration**: 2-5 minutes

#### 2.4 Capture Outputs

```bash
terraform output > deployment-info.txt
```

Save important values:
- `api_gateway_url`
- `login_page_url`
- `saml_metadata_url`
- `s3_bucket_name`

### Phase 3: Configuration (10 minutes)

#### 3.1 Upload SAML Certificates to SSM

Replace `<project>/<env>` with your values (e.g., `simple-saml-idp/dev`):

```bash
aws ssm put-parameter \
  --name "/<project>/<env>/saml/private_key" \
  --value "$(cat certs/saml-private-key.pem)" \
  --type SecureString \
  --overwrite \
  --region us-east-1

aws ssm put-parameter \
  --name "/<project>/<env>/saml/certificate" \
  --value "$(cat certs/saml-certificate.pem)" \
  --type String \
  --overwrite \
  --region us-east-1
```

Verify:
```bash
aws ssm get-parameter --name "/<project>/<env>/saml/certificate" --region us-east-1
```

#### 3.2 Update Login Page

Edit `static/index.html` and update the API Gateway URL:

```javascript
// Around line 237
const API_BASE_URL = 'https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev';
```

Replace with the actual `api_gateway_url` from Terraform outputs.

Upload to S3:

```bash
BUCKET_NAME=$(terraform output -raw s3_bucket_name)
aws s3 cp static/index.html s3://${BUCKET_NAME}/index.html \
  --content-type "text/html" \
  --region us-east-1
```

If using CloudFront:

```bash
DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"
```

#### 3.3 Update Terraform Variables (Optional)

If you want to update the `idp_base_url` with the actual API Gateway URL:

```bash
# Edit terraform.tfvars with the real API Gateway URL
terraform apply
```

### Phase 4: AWS Account Configuration (15 minutes per account)

For each AWS account you want to enable SSO for:

#### 4.1 Download SAML Metadata

```bash
METADATA_URL=$(terraform output -raw saml_metadata_url)
curl -o saml-metadata.xml "$METADATA_URL"
```

#### 4.2 Create SAML Provider

In the **target AWS account**:

```bash
aws iam create-saml-provider \
  --name SimpleSAMLIdP \
  --saml-metadata-document file://saml-metadata.xml
```

Save the ARN returned (e.g., `arn:aws:iam::123456789012:saml-provider/SimpleSAMLIdP`).

#### 4.3 Create IAM Role for SAML

Create a file `trust-policy.json`:

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

Replace `ACCOUNT_ID` with your AWS account ID.

Create the role:

```bash
aws iam create-role \
  --role-name SAMLAdminRole \
  --assume-role-policy-document file://trust-policy.json \
  --description "Admin role for SAML SSO"
```

#### 4.4 Attach Policies to Role

```bash
aws iam attach-role-policy \
  --role-name SAMLAdminRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

**Note**: Use appropriate policies based on your security requirements.

### Phase 5: User Setup (5 minutes)

#### 5.1 Create Test User

You can use either the new Lambda function (recommended) or the bash scripts:

**Option A: Using Lambda Function (Recommended)**

```bash
LAMBDA_FUNCTION=$(terraform output -raw manage_users_roles_lambda_name)

# Create user
aws lambda invoke \
  --function-name "$LAMBDA_FUNCTION" \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_user",
    "data": {
      "username": "john.doe",
      "password": "MySecurePassword123"
    }
  }' response.json && cat response.json
```

**Option B: Using Bash Script**

```bash
USERS_TABLE=$(terraform output -raw dynamodb_users_table)
./scripts/add-user.sh "$USERS_TABLE" john.doe "MySecurePassword123"
```

**Note**: The Lambda function uses secure bcrypt password hashing and supports update operations. See [QUICKSTART_USER_MANAGEMENT.md](QUICKSTART_USER_MANAGEMENT.md) for more details.

#### 5.2 Add Role Mapping

**Option A: Using Lambda Function (Recommended)**

```bash
LAMBDA_FUNCTION=$(terraform output -raw manage_users_roles_lambda_name)

# Add role mapping
aws lambda invoke \
  --function-name "$LAMBDA_FUNCTION" \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_role",
    "data": {
      "username": "john.doe",
      "role_arn": "arn:aws:iam::123456789012:role/SAMLAdminRole",
      "account_name": "Production Account"
    }
  }' response.json && cat response.json
```

**Option B: Using Bash Script**

```bash
ROLES_TABLE=$(terraform output -raw dynamodb_roles_table)
./scripts/add-role.sh "$ROLES_TABLE" john.doe \
  "arn:aws:iam::123456789012:role/SAMLAdminRole" \
  "Production Account"
```

Repeat for each account/role combination.

### Phase 6: Testing (5 minutes)

#### 6.1 Test SAML Metadata

```bash
curl "$(terraform output -raw saml_metadata_url)"
```

Should return XML metadata.

#### 6.2 Test Login Page

Open in browser:
```bash
terraform output -raw login_page_url
```

#### 6.3 End-to-End Test

1. Navigate to login page URL
2. Enter credentials: `john.doe` / `MySecurePassword123`
3. Select the AWS account and role
4. Click "Continue to AWS Console"
5. Verify you're logged into AWS Console with the correct role

## Post-Deployment

### Monitor Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/simple-saml-idp-processor-dev --follow

# API Gateway logs
aws logs tail /aws/apigateway/simple-saml-idp-dev --follow
```

### Add More Users

```bash
./scripts/add-user.sh "$USERS_TABLE" jane.smith "AnotherPassword456"
./scripts/add-role.sh "$ROLES_TABLE" jane.smith \
  "arn:aws:iam::987654321098:role/SAMLReadOnlyRole" \
  "Development Account"
```

### Update Login Page

After making changes to `static/index.html`:

```bash
aws s3 cp static/index.html s3://${BUCKET_NAME}/index.html \
  --content-type "text/html"

# Invalidate CloudFront cache if using CloudFront
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"
```

## Troubleshooting

### Issue: "Terraform not found"

**Solution**: Install Terraform:
```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_linux_amd64.zip
unzip terraform_1.7.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### Issue: "Access Denied" during deployment

**Solution**: Verify AWS credentials have necessary permissions:
- IAM (create roles, policies)
- Lambda (create functions, layers)
- API Gateway (create APIs)
- DynamoDB (create tables)
- S3 (create buckets)
- CloudFront (create distributions)
- SSM (create parameters)
- CloudWatch (create log groups)

### Issue: Login page shows "Connection error"

**Solution**: 
1. Verify API Gateway URL is correct in `static/index.html`
2. Check browser console for errors
3. Verify API Gateway is deployed and accessible

### Issue: "Invalid SAML Response" in AWS Console

**Solution**:
1. Check SAML certificate is in SSM Parameter Store
2. Verify SAML provider exists in target AWS account
3. Check role trust policy includes correct SAML provider ARN
4. Review Lambda logs for errors

### Issue: "No roles available" for user

**Solution**:
1. Verify role mappings exist in DynamoDB
2. Check role ARNs are correct
3. Verify `allowed_aws_accounts` doesn't exclude the account

## Cleanup

To remove all resources:

```bash
# Export data if needed
aws dynamodb scan --table-name $(terraform output -raw dynamodb_users_table) > users-backup.json
aws dynamodb scan --table-name $(terraform output -raw dynamodb_roles_table) > roles-backup.json

# Destroy infrastructure
terraform destroy
```

Type `yes` when prompted.

**Note**: This is irreversible. All user data and configurations will be deleted.

## Cost Optimization

- **Disable CloudFront**: Set `enable_cloudfront = false` if not needed
- **Adjust log retention**: Reduce CloudWatch log retention days
- **DynamoDB on-demand**: Already optimized for variable workloads
- **Lambda memory**: Adjust if 512MB is excessive for your use case

## Security Hardening

See README.md "Production Recommendations" section for security enhancements.

## Support

- GitHub Issues: https://github.com/faccomichele/simple-saml-idp/issues
- Documentation: README.md
- AWS CloudWatch Logs: For debugging
