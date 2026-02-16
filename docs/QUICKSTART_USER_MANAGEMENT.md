# Quick Start: User and Role Management Lambda

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform deployed the infrastructure (including the new Lambda function)

## Getting the Lambda Function Name

After deploying with Terraform:

```bash
terraform output manage_users_roles_lambda_name
```

Or use the default pattern:
- `simple-saml-idp-manage-users-roles-{environment}`
- Example: `simple-saml-idp-manage-users-roles-dev`

## Common Operations

### 1. Create a User (Full Example)

```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_user",
    "data": {
      "username": "john.doe",
      "password": "SecurePassword123!",
      "email": "john.doe@company.com",
      "first_name": "John",
      "last_name": "Doe",
      "enabled": true
    }
  }' \
  response.json && cat response.json && echo
```

### 2. Create a User (Minimal)

```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_user",
    "data": {
      "username": "jane.smith",
      "password": "SecurePassword123!"
    }
  }' \
  response.json && cat response.json && echo
```

Auto-generates:
- Email: `jane.smith@example.com`
- First name: `Jane`
- Last name: `Smith`
- Enabled: `true`

### 3. Update User Password

```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "update_user",
    "data": {
      "username": "john.doe",
      "password": "NewSecurePassword456!"
    }
  }' \
  response.json && cat response.json && echo
```

### 4. Disable a User

```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "update_user",
    "data": {
      "username": "john.doe",
      "enabled": false
    }
  }' \
  response.json && cat response.json && echo
```

### 5. Create a Role Mapping

```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_role",
    "data": {
      "username": "john.doe",
      "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
      "account_name": "Production Account",
      "description": "Full administrator access"
    }
  }' \
  response.json && cat response.json && echo
```

### 6. Add Multiple Roles for a User

```bash
# Development role
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_role",
    "data": {
      "username": "john.doe",
      "role_arn": "arn:aws:iam::111111111111:role/DeveloperRole",
      "account_name": "Development Account"
    }
  }' \
  /dev/null

# Staging role
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_role",
    "data": {
      "username": "john.doe",
      "role_arn": "arn:aws:iam::222222222222:role/DeveloperRole",
      "account_name": "Staging Account"
    }
  }' \
  /dev/null

echo "All roles added successfully"
```

## Using JSON Files

### Create User from File

```bash
# Using example file
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload file://examples/lambda-create-user.json \
  response.json && cat response.json && echo
```

### Create Your Own JSON Files

```bash
# Create a custom user
cat > /tmp/my-user.json << 'EOF'
{
  "operation": "create_user",
  "data": {
    "username": "my.user",
    "password": "MySecurePassword123!",
    "email": "myuser@company.com",
    "first_name": "My",
    "last_name": "User"
  }
}
EOF

aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload file:///tmp/my-user.json \
  response.json && cat response.json && echo
```

## Bulk Operations Script

Create a script to add multiple users:

```bash
#!/bin/bash
# bulk-add-users.sh

LAMBDA_FUNCTION="simple-saml-idp-manage-users-roles-dev"

# Array of users (username:password)
USERS=(
  "alice.johnson:Password123!"
  "bob.wilson:Password123!"
  "carol.brown:Password123!"
)

for user_data in "${USERS[@]}"; do
  IFS=':' read -r username password <<< "$user_data"
  
  echo "Creating user: $username"
  aws lambda invoke \
    --function-name "$LAMBDA_FUNCTION" \
    --cli-binary-format raw-in-base64-out \
    --payload "{
      \"operation\": \"create_user\",
      \"data\": {
        \"username\": \"$username\",
        \"password\": \"$password\"
      }
    }" \
    /tmp/response-$username.json
  
  if grep -q '"success": true' /tmp/response-$username.json; then
    echo "✓ User $username created successfully"
  else
    echo "✗ Failed to create user $username"
    cat /tmp/response-$username.json
  fi
  echo
done

echo "Bulk user creation completed"
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
  "body": "{\"success\": false, \"error\": \"User 'john.doe' already exists\"}"
}
```

## Checking Results

### View User in DynamoDB

```bash
aws dynamodb get-item \
  --table-name simple-saml-idp-users-dev \
  --key '{"username": {"S": "john.doe"}}'
```

### View All Users

```bash
aws dynamodb scan \
  --table-name simple-saml-idp-users-dev \
  --projection-expression "username,email,first_name,last_name,enabled"
```

### View User's Roles

```bash
aws dynamodb query \
  --table-name simple-saml-idp-roles-dev \
  --key-condition-expression "username = :username" \
  --expression-attribute-values '{":username": {"S": "john.doe"}}'
```

## Troubleshooting

### View Lambda Logs

```bash
# Follow logs in real-time
aws logs tail /aws/lambda/simple-saml-idp-manage-users-roles-dev --follow

# View recent logs
aws logs tail /aws/lambda/simple-saml-idp-manage-users-roles-dev --since 1h
```

### Common Issues

**Error: "User already exists"**
- Solution: Use `update_user` operation instead

**Error: "User not found"**
- Solution: User doesn't exist, use `create_user` first

**Error: "Invalid role_arn format"**
- Solution: Verify ARN format: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`

**Error: "AccessDeniedException"**
- Solution: Check IAM permissions for Lambda execution role

## Migration from Bash Scripts

The Lambda function is a drop-in replacement for bash scripts:

### Old Way (Bash Script)
```bash
./scripts/add-user.sh simple-saml-idp-users-dev john.doe password123
./scripts/add-role.sh simple-saml-idp-roles-dev john.doe arn:aws:iam::123456789012:role/AdminRole "Production"
```

### New Way (Lambda)
```bash
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_user",
    "data": {"username": "john.doe", "password": "password123"}
  }' response.json

aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "operation": "create_role",
    "data": {
      "username": "john.doe",
      "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
      "account_name": "Production"
    }
  }' response.json
```

### Benefits of Lambda Approach

✅ Update operations supported  
✅ Better error handling  
✅ Works from anywhere (no local AWS CLI needed)  
✅ Can be integrated with other AWS services  
✅ Proper logging in CloudWatch  
✅ Secure bcrypt password hashing  

## Security Best Practices

1. **Strong Passwords**: Require minimum 12 characters with complexity
2. **Regular Rotation**: Update passwords periodically using `update_user`
3. **Least Privilege**: Only grant necessary role mappings
4. **Audit Logs**: Monitor CloudWatch logs for all operations
5. **Disable Inactive Users**: Use `enabled: false` instead of deletion

## Next Steps

- Review [USER_ROLE_MANAGEMENT.md](USER_ROLE_MANAGEMENT.md) for complete documentation
- Set up automated user provisioning workflows
- Integrate with your CI/CD pipeline
- Configure CloudWatch alarms for Lambda errors
