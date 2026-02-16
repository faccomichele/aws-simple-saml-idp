# Testing MFA Implementation

This document provides instructions for testing the MFA implementation after deployment.

## Prerequisites

Before testing MFA, ensure you have:

1. Deployed the infrastructure with Terraform
2. Updated the Lambda layer with new dependencies (pyotp, qrcode, Pillow)
3. Updated the static/index.html file with the correct API Gateway URL
4. Uploaded the updated index.html to S3
5. Created at least one test user and role mapping

## Deployment Steps for MFA

### 1. Build and Deploy Lambda Layer

The Lambda layer needs to be rebuilt to include the new MFA dependencies:

```bash
cd /path/to/simple-saml-idp
make build-layer
```

This runs the `scripts/setup.sh` script which installs dependencies from `lambda/layer/requirements.txt`.

### 2. Apply Terraform Changes

Apply the Terraform changes to add the new API Gateway routes:

```bash
terraform apply
```

This will add:
- POST /mfa/setup route
- POST /mfa/verify route

### 3. Update and Upload Static Files

Update the API_BASE_URL in static/index.html:

```bash
# Get the API Gateway URL from Terraform
API_URL=$(terraform output -raw api_gateway_url)
echo "API Gateway URL: $API_URL"

# Update index.html with the correct URL
sed -i "s|const API_BASE_URL = 'YOUR_API_GATEWAY_URL';|const API_BASE_URL = '$API_URL';|g" static/index.html

# Upload to S3
make upload-static
```

## Test Scenarios

### Test 1: First-Time MFA Setup

**Objective**: Verify that a user without MFA configured is prompted to set it up.

**Steps**:
1. Create a new test user (if not already created):
   ```bash
   make add-user USERNAME=test.user PASSWORD=TestPass123!
   make add-role USERNAME=test.user ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/YourRole ACCOUNT_NAME="Test Account"
   ```

2. Open the login page in a browser:
   ```bash
   terraform output -raw login_page_url
   ```

3. Enter credentials:
   - Username: `test.user`
   - Password: `TestPass123!`
   - Click "Sign In"

4. **Expected Result**: 
   - MFA setup screen appears
   - QR code is displayed
   - Secret key is shown below the QR code
   - Instructions for Google Authenticator are visible

5. Install Google Authenticator on a mobile device (if not already installed)

6. Open Google Authenticator and scan the QR code

7. **Expected Result**: 
   - Account is added to Google Authenticator
   - 6-digit code appears and refreshes every 30 seconds

8. Enter the 6-digit code from Google Authenticator

9. **Expected Result**: 
   - Verification succeeds
   - User is redirected to role selection screen
   - Available AWS roles are displayed

10. Select a role and continue

11. **Expected Result**: 
    - SAML response is generated
    - User is redirected to AWS Console

### Test 2: Login with Existing MFA

**Objective**: Verify that a user with MFA configured is prompted for a token.

**Steps**:
1. Log out from AWS Console (or use a different browser/incognito)

2. Navigate to the login page

3. Enter the same credentials:
   - Username: `test.user`
   - Password: `TestPass123!`
   - Click "Sign In"

4. **Expected Result**: 
   - MFA verification screen appears
   - Prompt for 6-digit code is shown
   - No QR code (since MFA is already set up)

5. Open Google Authenticator

6. Enter the current 6-digit code

7. **Expected Result**: 
   - Verification succeeds
   - User is redirected to role selection screen

8. Select a role and continue to AWS Console

### Test 3: Invalid MFA Token

**Objective**: Verify that invalid tokens are rejected.

**Steps**:
1. Navigate to login page

2. Enter credentials and reach MFA verification screen

3. Enter an invalid code (e.g., `000000` or `123456`)

4. **Expected Result**: 
   - Error message appears: "Invalid MFA token"
   - User remains on MFA verification screen
   - Can try again with correct code

### Test 4: MFA Reset

**Objective**: Verify that MFA can be reset by clearing the secret from DynamoDB.

**Steps**:
1. Open AWS DynamoDB console

2. Navigate to the users table (e.g., `simple-saml-idp-users-dev`)

3. Find the user record (username: `test.user`)

4. Edit the item

5. Remove the `mfa_secret` attribute

6. Save changes

7. Navigate to login page

8. Enter credentials:
   - Username: `test.user`
   - Password: `TestPass123!`
   - Click "Sign In"

9. **Expected Result**: 
   - MFA setup screen appears again (as in Test 1)
   - User must scan a new QR code
   - Old authenticator entry will no longer work

### Test 5: Multiple Devices

**Objective**: Verify that the same MFA secret works on multiple devices.

**Steps**:
1. During MFA setup, note the secret key displayed below the QR code

2. On the first device, scan the QR code with Google Authenticator

3. On a second device:
   - Open Google Authenticator
   - Tap "Add account"
   - Choose "Enter a setup key"
   - Enter:
     - Account name: `test.user`
     - Key: (the secret key from step 1)
     - Type of key: Time based
   - Tap "Add"

4. **Expected Result**: 
   - Both devices now show the same 6-digit code
   - Codes refresh simultaneously every 30 seconds

5. Complete MFA setup using code from first device

6. Log out and log in again

7. Use code from second device for MFA verification

8. **Expected Result**: 
   - Verification succeeds
   - Both devices generate valid codes

## Test Checklist

- [ ] Test 1: First-time MFA setup with QR code scanning
- [ ] Test 2: Login with existing MFA configuration
- [ ] Test 3: Invalid MFA token rejection
- [ ] Test 4: MFA reset via DynamoDB
- [ ] Test 5: Multiple devices with same secret
- [ ] Verify QR code displays correctly
- [ ] Verify manual secret key entry works
- [ ] Verify instructions are clear and helpful
- [ ] Test on different browsers (Chrome, Firefox, Safari)
- [ ] Test on mobile browsers
- [ ] Verify CloudWatch logs show no errors
- [ ] Verify API Gateway logs show correct routing

## Troubleshooting Tests

### Check Lambda Logs

```bash
# Tail Lambda function logs
aws logs tail /aws/lambda/simple-saml-idp-processor-dev --follow
```

Look for:
- "MFA setup error"
- "MFA verify error"
- "MFA verification successful"

### Check API Gateway Logs

```bash
# Tail API Gateway logs
aws logs tail /aws/apigatewayv2/simple-saml-idp-dev --follow
```

Look for:
- POST /mfa/setup requests
- POST /mfa/verify requests
- Response status codes (200, 400, 401, 500)

### Verify DynamoDB

Check that the `mfa_secret` field is present after successful setup:

```bash
TABLE_NAME=$(terraform output -raw dynamodb_users_table)
aws dynamodb get-item \
    --table-name "$TABLE_NAME" \
    --key '{"username": {"S": "test.user"}}'
```

Expected output should include:
```json
{
  "Item": {
    "username": {"S": "test.user"},
    "mfa_secret": {"S": "BASE32ENCODEDSECRET"},
    ...
  }
}
```

### Test API Endpoints Directly

#### Test MFA Setup

```bash
API_URL=$(terraform output -raw api_gateway_url)

curl -X POST "$API_URL/mfa/setup" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test.user"
```

Expected response:
```json
{
  "success": true,
  "qr_code": "BASE64_ENCODED_PNG_IMAGE",
  "temp_secret": "BASE32_SECRET"
}
```

#### Test MFA Verify

```bash
# First, get a valid token from your authenticator app
TOTP_TOKEN="123456"  # Replace with actual token
TEMP_SECRET="YOUR_TEMP_SECRET"  # From setup response

curl -X POST "$API_URL/mfa/verify" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test.user&token=$TOTP_TOKEN&temp_secret=$TEMP_SECRET"
```

Expected response:
```json
{
  "success": true,
  "message": "MFA verification successful"
}
```

## Performance Tests

### Test 1: Time to Generate QR Code

Measure the time taken for MFA setup:

```bash
time curl -X POST "$API_URL/mfa/setup" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test.user"
```

Expected: < 1 second

### Test 2: Token Verification Speed

Measure the time taken for MFA verification:

```bash
time curl -X POST "$API_URL/mfa/verify" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test.user&token=$TOTP_TOKEN"
```

Expected: < 500ms

## Security Tests

### Test 1: Token Expiration

1. Get a token from Google Authenticator
2. Wait 30+ seconds for it to expire
3. Try to use the expired token

**Expected Result**: Token should be rejected (unless within the 30s window)

### Test 2: Brute Force Prevention

1. Attempt to verify with multiple invalid tokens in rapid succession
2. Check if rate limiting or account lockout occurs

**Note**: The current implementation does not include rate limiting. Consider adding this for production use.

### Test 3: Secret Storage

1. After MFA setup, check DynamoDB
2. Verify the `mfa_secret` is stored as a string
3. Verify it's a valid BASE32 encoded string

```bash
# Get the secret from DynamoDB
TABLE_NAME=$(terraform output -raw dynamodb_users_table)
SECRET=$(aws dynamodb get-item \
    --table-name "$TABLE_NAME" \
    --key '{"username": {"S": "test.user"}}' \
    --query 'Item.mfa_secret.S' \
    --output text)

echo "MFA Secret: $SECRET"
echo "Length: ${#SECRET}"

# Verify it's base32 (should only contain A-Z and 2-7)
if [[ $SECRET =~ ^[A-Z2-7]+$ ]]; then
    echo "✓ Valid BASE32 secret"
else
    echo "✗ Invalid BASE32 secret"
fi
```

## Browser Compatibility

Test on the following browsers:

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Chrome Mobile (Android)

## Accessibility Tests

1. Test with screen reader (e.g., NVDA, JAWS, VoiceOver)
2. Verify all form fields are properly labeled
3. Test keyboard navigation (Tab, Enter, Escape)
4. Verify focus indicators are visible
5. Test with high contrast mode
6. Verify text is readable at 200% zoom

## Documentation

After testing, verify:

- [ ] MFA_SETUP.md is comprehensive and accurate
- [ ] README.md mentions MFA feature
- [ ] TESTING_MFA.md (this document) is complete
- [ ] All API endpoints are documented
- [ ] Troubleshooting section covers common issues

## Clean Up

After testing, you can reset test users:

```bash
# Delete test user's MFA secret
TABLE_NAME=$(terraform output -raw dynamodb_users_table)
aws dynamodb update-item \
    --table-name "$TABLE_NAME" \
    --key '{"username": {"S": "test.user"}}' \
    --update-expression "REMOVE mfa_secret"
```

Or delete the test user entirely if no longer needed.
