# MFA Deployment Quick Guide

This is a quick reference for deploying the MFA feature after merging this PR.

## Prerequisites

- Existing Simple SAML IdP infrastructure deployed
- Terraform and AWS CLI configured
- Access to AWS account with appropriate permissions

## Deployment Steps

### Step 1: Rebuild Lambda Layer

The Lambda layer needs new Python dependencies (pyotp, qrcode, Pillow):

```bash
cd /path/to/simple-saml-idp
make build-layer
```

Or manually:

```bash
./scripts/setup.sh
```

This will:
- Create `lambda/layer/python/` directory
- Install dependencies from `lambda/layer/requirements.txt`
- Package them for Lambda

### Step 2: Apply Terraform Changes

Deploy the infrastructure updates to add MFA API routes:

```bash
terraform apply
```

Review the changes - you should see:
- New API Gateway routes: `POST /mfa/setup` and `POST /mfa/verify`
- No changes to DynamoDB tables (mfa_secret uses existing schema)
- Lambda function will be updated with new layer

Type `yes` to apply when prompted.

### Step 3: Update Static Login Page

Update the API Gateway URL in the login page:

```bash
# Get the API Gateway URL
API_URL=$(terraform output -raw api_gateway_url)
echo "API Gateway URL: $API_URL"

# Update index.html (if not already done)
cd static
sed -i.bak "s|const API_BASE_URL = 'YOUR_API_GATEWAY_URL';|const API_BASE_URL = '$API_URL';|g" index.html

# Or manually edit static/index.html and replace:
# const API_BASE_URL = 'YOUR_API_GATEWAY_URL';
# with your actual API Gateway URL
```

### Step 4: Upload Updated Login Page

Upload the updated page to S3:

```bash
make upload-static
```

Or manually:

```bash
BUCKET_NAME=$(terraform output -raw s3_bucket_name)
aws s3 cp static/index.html s3://$BUCKET_NAME/index.html \
    --content-type "text/html"

# If using CloudFront, invalidate the cache
DIST_ID=$(terraform output -raw cloudfront_distribution_id)
aws cloudfront create-invalidation \
    --distribution-id $DIST_ID \
    --paths "/*"
```

### Step 5: Verify Deployment

Test the endpoints:

```bash
# Test MFA setup endpoint
API_URL=$(terraform output -raw api_gateway_url)
curl -X POST "$API_URL/mfa/setup" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test.user"

# Should return JSON with success, qr_code, and temp_secret
```

Check Lambda logs:

```bash
make logs-lambda
# Or manually:
aws logs tail /aws/lambda/simple-saml-idp-processor-dev --follow
```

### Step 6: Test MFA Flow

1. Open the login page:
   ```bash
   terraform output -raw login_page_url
   ```

2. Log in with an existing user

3. You should see the MFA setup screen

4. Scan the QR code with Google Authenticator

5. Enter the 6-digit code to complete setup

6. Select a role and verify AWS Console access works

## Rollback (If Needed)

If issues occur, you can rollback:

```bash
# Revert to previous Lambda layer
cd lambda/layer
git checkout HEAD^ requirements.txt

# Rebuild layer without MFA dependencies
make build-layer

# Revert Terraform changes
git checkout HEAD^ apigatewayv2.tf

# Revert frontend changes
git checkout HEAD^ static/index.html

# Apply reverted state
terraform apply

# Re-upload original login page
make upload-static
```

## Post-Deployment

### For Existing Users

Existing users will be prompted to set up MFA on their next login. No immediate action required.

### Disabling MFA for a User

If a user needs MFA disabled:

```bash
TABLE_NAME=$(terraform output -raw dynamodb_users_table)
USERNAME="user.name"

aws dynamodb update-item \
    --table-name "$TABLE_NAME" \
    --key "{\"username\": {\"S\": \"$USERNAME\"}}" \
    --update-expression "REMOVE mfa_secret"
```

### Monitoring

Watch for MFA-related errors in CloudWatch:

```bash
# Lambda logs
aws logs tail /aws/lambda/simple-saml-idp-processor-dev --follow --filter-pattern "MFA"

# API Gateway logs
aws logs tail /aws/apigatewayv2/simple-saml-idp-dev --follow --filter-pattern "mfa"
```

## Troubleshooting

### Lambda Layer Not Updated

**Symptom**: `ImportError: No module named 'pyotp'`

**Solution**:
```bash
make clean
make build-layer
terraform apply
```

### QR Code Not Displaying

**Symptom**: Blank image or error in browser console

**Solution**:
1. Check Lambda logs for "QR code generation error"
2. Verify Pillow is installed in Lambda layer
3. Check browser console for JavaScript errors

### API Routes Not Working

**Symptom**: 404 errors for /mfa/setup or /mfa/verify

**Solution**:
1. Verify Terraform applied correctly: `terraform plan` should show no changes
2. Check API Gateway console for routes
3. Test with curl as shown in Step 5

### Users Not Prompted for MFA

**Symptom**: Users go straight to role selection

**Solution**:
1. Verify index.html was uploaded with updated code
2. Clear browser cache or use incognito mode
3. Check browser console for JavaScript errors
4. Verify API_BASE_URL is correct in index.html

## Quick Commands Reference

```bash
# Build layer
make build-layer

# Apply Terraform
terraform apply

# Upload static files
make upload-static

# View logs
make logs-lambda
make logs-api

# Get outputs
terraform output
terraform output -raw api_gateway_url
terraform output -raw login_page_url

# Test user MFA status
TABLE_NAME=$(terraform output -raw dynamodb_users_table)
aws dynamodb get-item \
    --table-name "$TABLE_NAME" \
    --key '{"username": {"S": "test.user"}}'

# Remove user MFA
aws dynamodb update-item \
    --table-name "$TABLE_NAME" \
    --key '{"username": {"S": "test.user"}}' \
    --update-expression "REMOVE mfa_secret"
```

## Documentation Links

- **User Guide**: [MFA_SETUP.md](MFA_SETUP.md)
- **Testing Guide**: [TESTING_MFA.md](TESTING_MFA.md)
- **Main README**: [README.md](README.md)

## Support

If you encounter issues:

1. Check [TESTING_MFA.md](TESTING_MFA.md) troubleshooting section
2. Review CloudWatch logs for errors
3. Check the GitHub issues for similar problems
4. Open a new issue with:
   - Deployment logs
   - Lambda function logs
   - Browser console errors (if UI issue)
   - Steps to reproduce

## Security Notes

- MFA secrets are stored encrypted in DynamoDB (server-side encryption enabled)
- Secrets are only saved after successful verification
- Consider implementing rate limiting for MFA verification in production
- Audit MFA usage via CloudWatch logs
- Regularly review users with MFA enabled vs. disabled

## Next Steps

After successful deployment:

1. ✅ Test MFA flow with a test user
2. ✅ Inform users about MFA requirement
3. ✅ Monitor CloudWatch logs for issues
4. ✅ Document any organization-specific MFA policies
5. ✅ Consider implementing MFA enforcement policies
6. ✅ Set up alerting for failed MFA attempts
