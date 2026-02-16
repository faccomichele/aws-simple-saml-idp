# User and Role Management Lambda

This Lambda function provides a programmatic interface for managing users and roles in DynamoDB, replacing the local bash scripts (`add-user.sh` and `add-role.sh`).

## Overview

The Lambda function handles:
- **User Creation**: Create new users with automatic password hashing
- **User Updates**: Update user properties (email, name, password, enabled status)
- **Role Creation**: Map users to AWS IAM roles for SAML SSO
- **Role Updates**: Update role mapping metadata

**Note**: Deletion is intentionally not implemented. Users and roles should be deleted manually at the DynamoDB level when needed.

## Lambda Function Details

- **Function Name**: `simple-saml-idp-manage-users-roles-{environment}`
- **Runtime**: Python 3.11
- **Timeout**: 30 seconds
- **Memory**: 256 MB
- **Environment Variables**:
  - `USERS_TABLE`: DynamoDB users table name
  - `ROLES_TABLE`: DynamoDB roles table name
  - `BCRYPT_ROUNDS` (optional): Bcrypt work factor (default: 12)

## Event Structure

All invocations use the following structure:

```json
{
  "operation": "<operation_name>",
  "data": {
    // operation-specific fields
  }
}
```

## User Operations

### Create User

Creates a new user in the DynamoDB users table.

**Operation**: `create_user`

**Required Fields**:
- `username` (string): Unique username
- `password` (string): Plain text password (will be hashed with bcrypt)

**Optional Fields**:
- `email` (string): User's email address (default: `{username}@example.com`)
- `first_name` (string): First name (default: derived from username)
- `last_name` (string): Last name (default: derived from username)
- `enabled` (boolean): Account status (default: `true`)

**Example - Full**:
```json
{
  "operation": "create_user",
  "data": {
    "username": "john.doe",
    "password": "password",
    "email": "john.doe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "enabled": true
  }
}
```

**Example - Minimal**:
```json
{
  "operation": "create_user",
  "data": {
    "username": "jane.smith",
    "password": "password"
  }
}
```

**Automatic Behavior**:
- If username contains a dot (e.g., `john.doe`), first and last names are derived: `John` and `Doe`
- If username has no dot, first name is capitalized username, last name is `User`
- Email defaults to `{username}@example.com`
- Account is enabled by default
- `created_at` timestamp is automatically added

**DynamoDB Fields Created**:
```json
{
  "username": "john.doe",
  "email": "john.doe@example.com",
  "password_hash": "$2b$12$K2p8Rd.../7n7X9Z2qB0Ke8gEHvWqGKf8cK0n8pD6Y",
  "first_name": "John",
  "last_name": "Doe",
  "enabled": true,
  "created_at": "2024-01-08T00:00:00Z"
}
```

**Note**: The password_hash shown is a bcrypt hash (starting with `$2b$`), which includes the salt and cost factor automatically.

### Update User

Updates an existing user's properties.

**Operation**: `update_user`

**Required Fields**:
- `username` (string): Username to update

**Optional Fields** (at least one required):
- `password` (string): New password (will be hashed with bcrypt)
- `email` (string): New email address
- `first_name` (string): New first name
- `last_name` (string): New last name
- `enabled` (boolean): New account status

**Example - Update Multiple Fields**:
```json
{
  "operation": "update_user",
  "data": {
    "username": "john.doe",
    "email": "john.doe@newdomain.com",
    "first_name": "Jonathan",
    "enabled": false
  }
}
```

**Example - Password Update**:
```json
{
  "operation": "update_user",
  "data": {
    "username": "john.doe",
    "password": "newpassword"
  }
}
```

**Automatic Behavior**:
- `updated_at` timestamp is automatically added
- Only specified fields are updated
- Password is hashed before storage

## Role Operations

### Create Role

Creates a new role mapping for a user in the DynamoDB roles table.

**Operation**: `create_role`

**Required Fields**:
- `username` (string): Username to map the role to
- `role_arn` (string): AWS IAM role ARN (e.g., `arn:aws:iam::123456789012:role/AdminRole`)

**Optional Fields**:
- `account_name` (string): Friendly name for the AWS account (default: account ID)
- `description` (string): Description of the role mapping (default: `"Role access for {username}"`)

**Example - Full**:
```json
{
  "operation": "create_role",
  "data": {
    "username": "john.doe",
    "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
    "account_name": "Production Account",
    "description": "Full administrator access to production resources"
  }
}
```

**Example - Minimal**:
```json
{
  "operation": "create_role",
  "data": {
    "username": "john.doe",
    "role_arn": "arn:aws:iam::987654321098:role/ReadOnlyRole"
  }
}
```

**Automatic Behavior**:
- Account ID is automatically extracted from the role ARN
- If `account_name` is not provided, it defaults to the account ID
- If `description` is not provided, it defaults to `"Role access for {username}"`
- `created_at` timestamp is automatically added

**DynamoDB Fields Created**:
```json
{
  "username": "john.doe",
  "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
  "account_name": "Production Account",
  "account_id": "123456789012",
  "description": "Full administrator access to production resources",
  "created_at": "2024-01-08T00:00:00Z"
}
```

### Update Role

Updates an existing role mapping's metadata.

**Operation**: `update_role`

**Required Fields**:
- `username` (string): Username of the role mapping
- `role_arn` (string): Role ARN of the mapping to update

**Optional Fields** (at least one required):
- `account_name` (string): New account name
- `description` (string): New description

**Example**:
```json
{
  "operation": "update_role",
  "data": {
    "username": "john.doe",
    "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
    "account_name": "Production Environment",
    "description": "Updated: Full administrative access with enhanced permissions"
  }
}
```

**Automatic Behavior**:
- `updated_at` timestamp is automatically added
- Only specified fields are updated

## Usage Examples

### Using AWS CLI

#### Create a User
```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --payload file://examples/lambda-create-user.json \
  response.json

cat response.json
```

#### Update a User
```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --payload file://examples/lambda-update-user.json \
  response.json

cat response.json
```

#### Create a Role Mapping
```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --payload file://examples/lambda-create-role.json \
  response.json

cat response.json
```

#### Update a Role Mapping
```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --payload file://examples/lambda-update-role.json \
  response.json

cat response.json
```

### Using Python Boto3

```python
import boto3
import json

lambda_client = boto3.client('lambda')

# Create a user
response = lambda_client.invoke(
    FunctionName='simple-saml-idp-manage-users-roles-dev',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        "operation": "create_user",
        "data": {
            "username": "john.doe",
            "password": "password",
            "email": "john.doe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "enabled": True
        }
    })
)

result = json.loads(response['Payload'].read())
print(result)
```

### Using Terraform

You can invoke the Lambda during infrastructure provisioning:

```hcl
resource "null_resource" "create_admin_user" {
  provisioner "local-exec" {
    command = <<EOT
      aws lambda invoke \
        --function-name ${aws_lambda_function.manage_users_roles.function_name} \
        --payload '{"operation":"create_user","data":{"username":"admin","password":"${var.admin_password}"}}' \
        /tmp/lambda-response.json
    EOT
  }

  depends_on = [aws_lambda_function.manage_users_roles]
}
```

## Response Format

### Success Response

```json
{
  "statusCode": 200,
  "body": "{\"success\": true, \"message\": \"User 'john.doe' created successfully\", \"data\": {...}}"
}
```

### Error Response

```json
{
  "statusCode": 400,
  "body": "{\"success\": false, \"error\": \"Missing required field: username\"}"
}
```

**Status Codes**:
- `200`: Success
- `400`: Bad request (validation error)
- `404`: Resource not found
- `409`: Conflict (resource already exists)
- `500`: Internal server error

## Field Mapping: Bash Scripts vs Lambda

### User Fields

Both the bash script (`add-user.sh`) and Lambda function support the same fields:

| Field | Bash Script | Lambda | Notes |
|-------|-------------|--------|-------|
| `username` | ✅ Required | ✅ Required | Unique identifier |
| `email` | ✅ Auto-generated | ✅ Optional | Defaults to `{username}@example.com` |
| `password_hash` | ✅ bcrypt | ✅ bcrypt | Secure password hashing with automatic salting |
| `first_name` | ✅ Derived | ✅ Optional | Auto-derived from username |
| `last_name` | ✅ Derived | ✅ Optional | Auto-derived from username |
| `enabled` | ✅ Always true | ✅ Optional | Lambda allows false |
| `created_at` | ✅ Timestamp | ✅ Timestamp | ISO 8601 format |

### Role Fields

Both the bash script (`add-role.sh`) and Lambda function support the same fields:

| Field | Bash Script | Lambda | Notes |
|-------|-------------|--------|-------|
| `username` | ✅ Required | ✅ Required | User to map role to |
| `role_arn` | ✅ Required | ✅ Required | AWS IAM role ARN |
| `account_name` | ✅ Required | ✅ Optional | Friendly account name |
| `account_id` | ✅ Extracted | ✅ Extracted | From role ARN |
| `description` | ✅ Auto-generated | ✅ Optional | Descriptive text |
| `created_at` | ✅ Timestamp | ✅ Timestamp | ISO 8601 format |

**Lambda Advantages**:
- Update operations (not available in bash scripts)
- Better error handling and validation
- Programmatic invocation
- Integration with AWS services
- No local AWS CLI required

## Security Considerations

### Password Hashing

This implementation uses **bcrypt** for password hashing, which is a secure, industry-standard algorithm that:
- Automatically generates unique salts for each password
- Uses a configurable work factor to defend against brute-force attacks
- Is specifically designed for password hashing (unlike general-purpose hash functions)

**Password Storage**:
- Passwords are hashed using bcrypt with a default work factor of 12 rounds
- Each password gets a unique salt automatically
- The salt and hash are stored together in the bcrypt format: `$2b$12$...`
- The work factor can be adjusted via the `BCRYPT_ROUNDS` environment variable (range: 10-14 recommended)

**Adjusting Security Level**:
To increase security at the cost of performance, set a higher rounds value in Terraform:
```hcl
resource "aws_lambda_function" "manage_users_roles" {
  # ... other configuration ...
  
  environment {
    variables = {
      USERS_TABLE   = aws_dynamodb_table.users.name
      ROLES_TABLE   = aws_dynamodb_table.roles.name
      BCRYPT_ROUNDS = "13"  # Higher = more secure but slower
    }
  }
}
```

**Password Verification** (for authentication):
```python
import bcrypt

# Verify password during login
is_valid = bcrypt.checkpw(
    provided_password.encode('utf-8'), 
    stored_hash.encode('utf-8')
)
```

**Security Note**: Passwords are never logged. All log entries redact password fields with `***REDACTED***` to prevent exposure in CloudWatch Logs.

**Note**: The Lambda function only handles user/role management (creation and updates). Password verification should be implemented in your authentication logic (e.g., in the SAML processor Lambda).

### IAM Permissions

The Lambda function requires the following IAM permissions:
- `dynamodb:GetItem` - Check for existing resources
- `dynamodb:PutItem` - Create new resources
- `dynamodb:UpdateItem` - Update existing resources

Deletion permissions (`dynamodb:DeleteItem`) are intentionally granted but not used by the Lambda function.

## Deletion

Deletion operations are **not implemented** in this Lambda function. To delete users or roles:

1. Use the AWS Console:
   - Navigate to DynamoDB
   - Select the appropriate table
   - Find and delete the item

2. Use AWS CLI:
   ```bash
   # Delete a user
   aws dynamodb delete-item \
     --table-name simple-saml-idp-users-dev \
     --key '{"username": {"S": "john.doe"}}'

   # Delete a role mapping
   aws dynamodb delete-item \
     --table-name simple-saml-idp-roles-dev \
     --key '{"username": {"S": "john.doe"}, "role_arn": {"S": "arn:aws:iam::123456789012:role/AdminRole"}}'
   ```

## Troubleshooting

### Common Errors

**"Missing required field: username"**
- Ensure the `data` object includes all required fields for the operation

**"User 'xxx' already exists"**
- Use `update_user` operation instead of `create_user`

**"User 'xxx' not found"**
- Verify the username is correct
- Use `create_user` if the user doesn't exist

**"Invalid role_arn format"**
- Role ARN must follow format: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`
- Example: `arn:aws:iam::123456789012:role/AdminRole`

**"No fields to update"**
- Update operations require at least one optional field to update

### Viewing Lambda Logs

```bash
aws logs tail /aws/lambda/simple-saml-idp-manage-users-roles-dev --follow
```

### Testing

Test the Lambda function in the AWS Console:
1. Navigate to Lambda > Functions
2. Select `simple-saml-idp-manage-users-roles-{environment}`
3. Click "Test" tab
4. Create a test event with one of the example payloads
5. Click "Test" to invoke

## Migration from Bash Scripts

To migrate from bash scripts to Lambda:

1. **Deploy the Lambda function** via Terraform
2. **Test Lambda invocations** with example payloads
3. **Update automation/scripts** to use `aws lambda invoke` instead of bash scripts
4. **Keep bash scripts** as a backup during transition period
5. **Remove bash scripts** once Lambda is proven stable

The Lambda function provides full feature parity with the bash scripts while adding update capabilities.
