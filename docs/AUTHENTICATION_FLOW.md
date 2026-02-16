# Authentication Flow

This document describes the authentication and authorization flow for the Simple SAML IdP.

## Overview

The Simple SAML IdP implements a standard SAML 2.0 authentication flow specifically designed for AWS Console SSO. The flow involves user authentication, role selection, SAML assertion generation, and automatic redirect to the AWS Console.

## Flow Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │
     │ 1. Navigate to Login Page
     ▼
┌──────────────────────┐
│  CloudFront/S3       │
│  (Login Page)        │
└──────────┬───────────┘
           │
           │ 2. Load static HTML/JS
           ▼
┌──────────────────────┐
│  User's Browser      │
│  (Login Form)        │
└──────────┬───────────┘
           │
           │ 3. POST /login (username, password)
           ▼
┌──────────────────────┐
│  API Gateway         │
│  (HTTP API)          │
└──────────┬───────────┘
           │
           │ 4. Invoke Lambda
           ▼
┌──────────────────────┐         ┌──────────────────┐
│  Lambda Function     │────────▶│  DynamoDB Users  │
│  (Auth Processor)    │  5. Get │  Table           │
└──────────┬───────────┘  User   └──────────────────┘
           │
           │ 6. Validate Password
           │
           ├──────────────────────┐
           │                      │ 7. Query User Roles
           │                      ▼
           │              ┌──────────────────┐
           │              │  DynamoDB Roles  │
           │              │  Table           │
           │              └──────────────────┘
           │
           │ 8. Return role list (JSON)
           ▼
┌──────────────────────┐
│  User's Browser      │
│  (Role Selection)    │
└──────────┬───────────┘
           │
           │ 9. User selects role
           │
           │ 10. POST /sso (username, role_arn)
           ▼
┌──────────────────────┐
│  API Gateway         │
└──────────┬───────────┘
           │
           │ 11. Invoke Lambda
           ▼
┌──────────────────────┐         ┌──────────────────┐
│  Lambda Function     │────────▶│  SSM Parameter   │
│  (SAML Generator)    │  12. Get│  Store           │
└──────────┬───────────┘  Cert   └──────────────────┘
           │
           │ 13. Generate SAML Response
           │     - Create assertion
           │     - Sign with private key
           │     - Base64 encode
           │
           │ 14. Return HTML with auto-submit form
           ▼
┌──────────────────────┐
│  User's Browser      │
│  (Auto-submit form)  │
└──────────┬───────────┘
           │
           │ 15. POST SAMLResponse
           ▼
┌──────────────────────┐
│  AWS Console         │
│  signin.aws.amazon   │
│  .com/saml           │
└──────────┬───────────┘
           │
           │ 16. Verify SAML assertion
           │     - Check signature
           │     - Validate SAML provider
           │     - Check role trust policy
           │
           │ 17. AssumeRoleWithSAML
           ▼
┌──────────────────────┐
│  AWS Console         │
│  (Logged in with     │
│   selected role)     │
└──────────────────────┘
```

## Detailed Steps

### Step 1-2: Initial Page Load

- User navigates to the IdP login page URL
- CloudFront (or S3) serves the static HTML page
- Browser loads JavaScript that will handle authentication

### Step 3-8: Authentication Phase

1. **User submits credentials**: Username and password are sent via POST to `/login` endpoint

2. **API Gateway receives request**: Routes the request to Lambda function

3. **Lambda retrieves user**: Queries DynamoDB Users table by username

4. **Password validation**: Compares submitted password hash with stored hash
   - Hash algorithm: SHA256 (configurable)
   - Comparison is case-sensitive

5. **Fetch available roles**: If authentication succeeds, Lambda queries DynamoDB Roles table
   - Filters by username
   - Applies `allowed_aws_accounts` restriction if configured

6. **Return role list**: Lambda returns JSON response with available roles:
   ```json
   {
     "success": true,
     "username": "john.doe",
     "roles": [
       {
         "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
         "account_id": "123456789012",
         "role_name": "AdminRole",
         "account_name": "Production Account",
         "description": "Full admin access"
       }
     ]
   }
   ```

### Step 9-14: Role Selection and SAML Generation

1. **User selects role**: Browser displays available roles, user clicks one

2. **SSO request**: Browser submits POST to `/sso` with:
   - `username`: Authenticated username
   - `role_arn`: Selected role ARN

3. **Lambda retrieves signing materials**: Fetches from SSM Parameter Store:
   - SAML private key (for signing)
   - SAML certificate (included in assertion)

4. **Generate SAML assertion**: Lambda creates XML assertion with:
   - **Subject**: User identifier (username)
   - **Attributes**:
     - `RoleSessionName`: Username for AWS session
     - `Role`: Role ARN and SAML provider ARN
     - `SessionDuration`: Session timeout in seconds
   - **Conditions**: NotBefore and NotOnOrAfter timestamps
   - **Signature**: Digital signature using private key

5. **Return auto-submit form**: Lambda returns HTML page containing:
   - Hidden form with SAMLResponse
   - JavaScript to auto-submit form
   - Form action: `https://signin.aws.amazon.com/saml`

### Step 15-17: AWS Console Login

1. **Form submission**: Browser automatically submits SAML response to AWS

2. **AWS validates assertion**:
   - Verifies digital signature using SAML provider certificate
   - Checks SAML provider exists in target account
   - Validates role trust policy allows SAML authentication
   - Verifies timestamps (NotBefore, NotOnOrAfter)

3. **Assume role**: AWS STS processes `AssumeRoleWithSAML`:
   - Creates temporary credentials
   - Duration based on `SessionDuration` attribute
   - Applies role's permission policies

4. **Console access**: User is redirected to AWS Console with temporary session

## SAML Assertion Structure

Example SAML assertion generated by the Lambda function:

```xml
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                ID="_abc123..."
                Version="2.0"
                IssueInstant="2024-01-08T12:00:00Z"
                Destination="https://signin.aws.amazon.com/saml">
  <saml:Issuer>https://saml-idp.example.com</saml:Issuer>
  <samlp:Status>
    <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
  </samlp:Status>
  <saml:Assertion ID="_xyz789..." Version="2.0" IssueInstant="2024-01-08T12:00:00Z">
    <saml:Issuer>https://saml-idp.example.com</saml:Issuer>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:2.0:nameid-format:persistent">
        john.doe
      </saml:NameID>
      <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
        <saml:SubjectConfirmationData 
          NotOnOrAfter="2024-01-08T13:00:00Z"
          Recipient="https://signin.aws.amazon.com/saml"/>
      </saml:SubjectConfirmation>
    </saml:Subject>
    <saml:Conditions NotBefore="2024-01-08T11:55:00Z" NotOnOrAfter="2024-01-08T13:00:00Z">
      <saml:AudienceRestriction>
        <saml:Audience>urn:amazon:webservices</saml:Audience>
      </saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AttributeStatement>
      <saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/RoleSessionName">
        <saml:AttributeValue>john.doe</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/Role">
        <saml:AttributeValue>
          arn:aws:iam::123456789012:role/AdminRole,arn:aws:iam::123456789012:saml-provider/SimpleSAMLIdP
        </saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/SessionDuration">
        <saml:AttributeValue>3600</saml:AttributeValue>
      </saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>
```

## Security Considerations

### Authentication

- **Password Storage**: Passwords are hashed (SHA256 by default)
- **HTTPS Only**: All communication over TLS
- **Session Management**: No server-side sessions; stateless JWT could be added

### SAML Security

- **Digital Signatures**: All assertions are signed with RSA private key
- **Time-limited**: Assertions valid for configured duration (default 1 hour)
- **Replay Protection**: Each assertion has unique ID
- **Audience Restriction**: Assertions only valid for AWS (`urn:amazon:webservices`)

### AWS Integration

- **Trust Policy**: Roles must explicitly trust the SAML provider
- **Temporary Credentials**: AWS generates time-limited credentials
- **Principle of Least Privilege**: Users only see roles they're assigned

## API Endpoints

### GET /metadata

Returns SAML IdP metadata XML.

**Response**: SAML metadata XML document

**Usage**: Download and upload to AWS IAM SAML provider

### POST /login

Authenticates user and returns available roles.

**Request Body** (form-encoded):
```
username=john.doe&password=MyPassword123
```

**Response** (JSON):
```json
{
  "success": true,
  "username": "john.doe",
  "roles": [...]
}
```

### POST /sso

Generates SAML response for selected role.

**Request Body** (form-encoded):
```
username=john.doe&role_arn=arn:aws:iam::123456789012:role/AdminRole
```

**Response** (HTML):
Auto-submit form with SAMLResponse

## Error Handling

### Authentication Failures

- **Invalid Credentials**: Returns 401 with error message
- **User Not Found**: Returns 401 (same as invalid password for security)
- **Account Disabled**: Returns 403 with specific message

### Authorization Failures

- **No Roles Available**: Returns 403 with message
- **Invalid Role ARN**: Returns 400 with error
- **Account Restricted**: Returns 403 if account not in allowed list

### System Errors

- **DynamoDB Unavailable**: Returns 500 with generic error
- **SSM Parameter Missing**: Returns 500, logs detailed error
- **SAML Generation Failed**: Returns 500 with error message

## Monitoring and Logging

All authentication attempts and SAML generation are logged to CloudWatch:

- **Successful logins**: Username, timestamp, selected role
- **Failed logins**: Username, timestamp, failure reason
- **SAML generation**: Username, role ARN, assertion ID
- **Errors**: Full stack traces for debugging

## Session Duration

AWS session duration is controlled by:

1. **IdP Configuration**: `session_duration_seconds` variable (900-43200)
2. **Role Maximum**: IAM role's maximum session duration setting
3. **Effective Duration**: Minimum of the two values

To extend sessions:

```bash
# Update Terraform variable
session_duration_seconds = 43200  # 12 hours

# Update IAM role max session duration
aws iam update-role --role-name YourRole --max-session-duration 43200
```

## Multi-Account Considerations

The IdP supports SSO to multiple AWS accounts:

1. **Each account** must have:
   - SAML provider configured with IdP metadata
   - IAM roles with SAML trust policy

2. **User can switch** between accounts:
   - Logout and login again
   - Select different role from different account

3. **Account filtering**: Use `allowed_aws_accounts` to restrict access

## Extending the Flow

### Adding MFA

1. Store MFA secret in DynamoDB user record
2. Add MFA token field to login form
3. Verify TOTP token in Lambda before returning roles

### Adding Groups

1. Create Groups table in DynamoDB
2. Link users to groups
3. Query group memberships during authentication
4. Map groups to roles instead of direct user-to-role

### Adding Audit Trail

1. Create Audit table in DynamoDB
2. Record all authentication events
3. Store: timestamp, username, action, IP, user-agent, result
4. Query for compliance reporting
