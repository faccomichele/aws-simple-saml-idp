# Multi-Factor Authentication (MFA) Setup Guide

This guide explains how to set up and use Multi-Factor Authentication (MFA) with the Simple SAML IdP for enhanced security.

## Overview

The Simple SAML IdP now supports Time-based One-Time Password (TOTP) multi-factor authentication, compatible with Google Authenticator and other TOTP apps. MFA is implemented using the `pyotp` library and runs entirely locally within your AWS infrastructure - no external services or Google accounts are required.

## Features

- **TOTP-based MFA**: Compatible with Google Authenticator, Microsoft Authenticator, Authy, and other TOTP apps
- **Local Implementation**: Everything runs within your AWS environment
- **User-Friendly Setup**: QR code scanning for easy configuration
- **Flexible Reset**: MFA can be reset by clearing the `mfa_secret` field in DynamoDB

## How MFA Works

1. **First Login (MFA Setup)**:
   - User enters username and password
   - If MFA is not configured, the login page displays MFA setup instructions
   - A QR code and secret key are generated and displayed
   - User scans the QR code with their authenticator app
   - User enters a verification code to complete setup

2. **Subsequent Logins (MFA Verification)**:
   - User enters username and password
   - System detects MFA is enabled
   - User is prompted to enter a 6-digit code from their authenticator app
   - After successful MFA verification, user proceeds to role selection

## Setting Up MFA

### For End Users

1. **Initial Login**:
   - Navigate to your IdP login page
   - Enter your username and password
   - Click "Sign In"

2. **MFA Setup Screen**:
   - You'll be automatically directed to the MFA setup screen
   - Follow the on-screen instructions

3. **Install Authenticator App** (if not already installed):
   - **Google Authenticator**: [iOS](https://apps.apple.com/app/google-authenticator/id388497605) | [Android](https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2)
   - **Microsoft Authenticator**: [iOS](https://apps.apple.com/app/microsoft-authenticator/id983156458) | [Android](https://play.google.com/store/apps/details?id=com.azure.authenticator)
   - **Authy**: [iOS](https://apps.apple.com/app/authy/id494168017) | [Android](https://play.google.com/store/apps/details?id=com.authy.authy)

4. **Add Account to Authenticator**:
   - Open your authenticator app
   - Tap "Add account" or "+"
   - Choose "Scan QR code" or "Scan a barcode"
   - Scan the QR code displayed on the screen
   - **Alternative**: If you can't scan, manually enter the secret key shown below the QR code

5. **Complete Setup**:
   - Your authenticator app will now show a 6-digit code that refreshes every 30 seconds
   - Enter the current 6-digit code in the verification field
   - Click "Complete Setup"

6. **Success**:
   - Once verified, you'll proceed to role selection as normal
   - From now on, you'll need your authenticator app code for every login

### Using MFA for Login

After MFA is configured:

1. Enter your username and password
2. Click "Sign In"
3. You'll be prompted for your MFA code
4. Open your authenticator app
5. Enter the 6-digit code displayed for "Simple SAML IdP"
6. Click "Verify & Continue"
7. Select your AWS role and continue to the console

## Resetting MFA

If a user loses access to their authenticator app or needs to reset MFA:

### Option 1: Manual Reset via DynamoDB Console

1. Open the AWS DynamoDB console
2. Navigate to your users table (e.g., `simple-saml-idp-users-dev`)
3. Find the user's record by username
4. Edit the item
5. Remove the `mfa_secret` attribute
6. Save the changes

### Option 2: Reset via AWS CLI

```bash
# Set your variables
TABLE_NAME="simple-saml-idp-users-dev"
USERNAME="user.name"

# Remove MFA secret
aws dynamodb update-item \
    --table-name "$TABLE_NAME" \
    --key "{\"username\": {\"S\": \"$USERNAME\"}}" \
    --update-expression "REMOVE mfa_secret"
```

### Option 3: Reset via Management Lambda

You can extend the `manage_users_roles.py` Lambda function to include an MFA reset operation:

```bash
aws lambda invoke \
    --function-name simple-saml-idp-manage-users-dev \
    --payload '{
        "operation": "update_user",
        "data": {
            "username": "user.name"
        }
    }' \
    response.json
```

Then manually remove the `mfa_secret` field from DynamoDB.

After reset, the user will go through the MFA setup process again on their next login.

## Security Best Practices

1. **Backup Codes**: Advise users to save the secret key displayed during setup as a backup
2. **Secure Storage**: Store the secret key in a secure password manager
3. **Multiple Devices**: Users can add the same secret to multiple authenticator apps for redundancy
4. **Regular Testing**: Test MFA after setup to ensure it works correctly
5. **Prompt Reset**: If a device is lost, reset MFA immediately

## Technical Details

### Implementation

- **Library**: Uses `pyotp` for TOTP generation and verification
- **QR Code**: Generated using `qrcode` and `Pillow` libraries
- **Storage**: MFA secrets are stored in the DynamoDB users table
- **Validation**: Tokens are validated with a 1-interval window (30 seconds before/after) for clock skew tolerance

### API Endpoints

The following new endpoints are added to the Lambda function:

- `POST /mfa/setup`: Generate QR code and secret for MFA setup
  - Request: `username`
  - Response: `secret`, `qr_code` (base64-encoded PNG)

- `POST /mfa/verify`: Verify a TOTP token
  - Request: `username`, `token`
  - Response: `success`, `message`

- `POST /login`: Updated to handle MFA
  - Request: `username`, `password`, `mfa_token` (optional)
  - Response: Includes `mfa_required` and `mfa_setup_needed` flags

### Database Schema

The `mfa_secret` field is added to user records in DynamoDB:

```json
{
  "username": "user.name",
  "email": "user.name@example.com",
  "password_hash": "...",
  "mfa_secret": "BASE32ENCODEDSECRET",
  "first_name": "User",
  "last_name": "Name",
  "enabled": true,
  "created_at": "2024-01-09T12:00:00Z",
  "updated_at": "2024-01-09T12:30:00Z"
}
```

## Troubleshooting

### "Invalid MFA token" Error

**Causes**:
- Clock skew between your device and the server
- Entered code expired (codes refresh every 30 seconds)
- Incorrect secret key entered manually

**Solutions**:
- Ensure your device's time is synchronized (Settings → Date & Time → Set Automatically)
- Try entering a fresh code
- If manually entered, verify the secret key matches exactly
- Reset MFA and set up again

### "MFA not configured" Error

**Causes**:
- MFA secret was removed from DynamoDB
- User record doesn't have `mfa_secret` field

**Solutions**:
- Complete MFA setup by logging in again
- The setup screen will appear automatically

### QR Code Not Scanning

**Causes**:
- QR code image quality issues
- Camera focus problems
- Screen brightness too low

**Solutions**:
- Increase screen brightness
- Try manually entering the secret key instead
- Use the manual entry option in your authenticator app

### Lost Authenticator Device

**Solutions**:
1. Contact your administrator to reset MFA
2. Administrator follows "Resetting MFA" steps above
3. Set up MFA again with a new device

## FAQ

**Q: Can I use the same MFA secret on multiple devices?**  
A: Yes! You can scan the same QR code or enter the same secret key on multiple devices. All will generate identical codes.

**Q: What happens if I lose my phone?**  
A: Contact your administrator to reset your MFA. After reset, you'll set up MFA again with a new device.

**Q: Can I disable MFA after setting it up?**  
A: Yes, an administrator can remove the `mfa_secret` field from your user record in DynamoDB. MFA will be required again on next login if you want to re-enable it.

**Q: Is MFA required for all users?**  
A: Currently, MFA is prompted on first login but becomes required once set up. The system is designed to encourage MFA adoption while allowing gradual rollout.

**Q: Does this work offline?**  
A: Your authenticator app generates codes offline using the secret key. However, you need internet access to reach the IdP login page.

**Q: How secure is TOTP MFA?**  
A: TOTP is an industry-standard MFA method used by many services. It provides strong security against password-only attacks while being user-friendly.

## Additional Resources

- [TOTP RFC 6238](https://tools.ietf.org/html/rfc6238)
- [pyotp Documentation](https://pyotp.readthedocs.io/)
- [Google Authenticator](https://support.google.com/accounts/answer/1066447)
- [OWASP MFA Guide](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review CloudWatch logs for the IdP Lambda function
3. Check the browser console for client-side errors
4. Open an issue on the GitHub repository
