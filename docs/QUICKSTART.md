# Quick Start Guide

Get your Simple SAML IdP up and running in 15 minutes.

## Prerequisites

- AWS account with admin permissions
- AWS CLI configured (`aws configure`)
- Terraform installed (`brew install terraform` or download from terraform.io)
- Python 3.x and OpenSSL (usually pre-installed)

## 5-Step Quick Start

### Step 1: Generate Certificates (2 minutes)

```bash
./scripts/generate-saml-cert.sh
```

This creates self-signed certificates in the `certs/` directory.

### Step 2: Configure Variables (1 minute)

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` - minimum required:
```hcl
aws_region    = "us-east-1"
idp_entity_id = "https://saml-idp.example.com"
```

### Step 3: Deploy Infrastructure (5 minutes)

```bash
terraform init
terraform apply
```

Type `yes` when prompted. Wait 2-5 minutes for deployment.

Save the outputs:
```bash
terraform output > deployment-info.txt
```

### Step 4: Upload Certificates (1 minute)

```bash
# Using Makefile
make upload-cert

# Or manually
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

### Step 5: Configure Login Page (2 minutes)

Get your API Gateway URL:
```bash
terraform output api_gateway_url
```

Edit `static/index.html` line 237:
```javascript
const API_BASE_URL = 'YOUR_API_GATEWAY_URL_HERE';
```

Upload to S3:
```bash
make upload-static
# Or manually:
aws s3 cp static/index.html s3://$(terraform output -raw s3_bucket_name)/index.html
```

## Testing (4 minutes)

### Add Test User

```bash
make add-user USERNAME=test.user PASSWORD=Test123!
```

### Configure AWS Account

In your target AWS account:

```bash
# Download metadata
curl $(terraform output -raw saml_metadata_url) > metadata.xml

# Create SAML provider
aws iam create-saml-provider \
  --name SimpleSAMLIdP \
  --saml-metadata-document file://metadata.xml

# Create role with trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::YOUR_ACCOUNT_ID:saml-provider/SimpleSAMLIdP"
    },
    "Action": "sts:AssumeRoleWithSAML",
    "Condition": {
      "StringEquals": {"SAML:aud": "https://signin.aws.amazon.com/saml"}
    }
  }]
}
EOF

aws iam create-role \
  --role-name SAMLTestRole \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name SAMLTestRole \
  --policy-arn arn:aws:iam::aws:policy/ReadOnlyAccess
```

### Add Role Mapping

```bash
make add-role \
  USERNAME=test.user \
  ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/SAMLTestRole \
  ACCOUNT_NAME="Test Account"
```

### Test Login

1. Get login URL: `terraform output login_page_url`
2. Open in browser
3. Login with `test.user` / `Test123!`
4. Select the role
5. Click "Continue to AWS Console"
6. ✅ You should be logged into AWS Console!

## Common Commands

```bash
# View outputs
make outputs

# Add user
make add-user USERNAME=john.doe PASSWORD=MyPassword

# Add role
make add-role USERNAME=john.doe \
  ROLE_ARN=arn:aws:iam::123:role/Admin \
  ACCOUNT_NAME="Production"

# View logs
make logs-lambda
make logs-api

# Update login page
make upload-static

# Clean up
make destroy
```

## Troubleshooting

**Login page shows "Connection error"**
- Check API Gateway URL in `static/index.html` is correct
- Run `make upload-static` after editing

**"Invalid credentials" error**
- Verify user was created: Check DynamoDB Users table
- Password is case-sensitive

**"No roles available" error**
- Add role mapping with `make add-role`
- Check DynamoDB Roles table

**"Invalid SAML Response" in AWS**
- Verify certificates are in SSM: `aws ssm get-parameter --name /simple-saml-idp/dev/saml/certificate`
- Check SAML provider exists in target account
- Verify role trust policy

**View logs for debugging**
```bash
make logs-lambda
```

## Next Steps

1. **Add more users**: `make add-user USERNAME=... PASSWORD=...`
2. **Configure multiple accounts**: Repeat AWS account setup for each account
3. **Customize login page**: Edit `static/index.html` for branding
4. **Review security**: See README.md "Production Recommendations"
5. **Setup monitoring**: Configure CloudWatch alarms
6. **Add custom domain**: Use AWS Certificate Manager + API Gateway custom domain

## Production Checklist

Before going to production:

- [ ] Use strong passwords (consider password manager)
- [ ] Implement MFA (see AUTHENTICATION_FLOW.md)
- [ ] Setup CloudWatch alarms for failed logins
- [ ] Enable AWS WAF on API Gateway
- [ ] Configure custom domain with SSL
- [ ] Review IAM policies (see IAM_POLICY.md)
- [ ] Setup log retention and archival
- [ ] Document disaster recovery procedures
- [ ] Test backup and restore of DynamoDB
- [ ] Setup monitoring dashboard
- [ ] Implement rate limiting
- [ ] Review and restrict allowed_aws_accounts

## Cost Estimate

For 10 users with 5 logins per day:
- API Gateway: ~$0.01/month
- Lambda: ~$0.05/month
- DynamoDB: ~$0.50/month
- S3: ~$0.01/month
- CloudFront: ~$0.10/month

**Total: ~$0.70/month** 💰

## Support

- Documentation: README.md, DEPLOYMENT.md, AUTHENTICATION_FLOW.md
- Issues: https://github.com/faccomichele/simple-saml-idp/issues
- Logs: `make logs-lambda` or `make logs-api`

## Clean Up

To remove everything:

```bash
terraform destroy
```

⚠️ This deletes all users and configurations. Export data first if needed.

---

**That's it!** You now have a working SAML IdP for AWS Console SSO. 🎉
