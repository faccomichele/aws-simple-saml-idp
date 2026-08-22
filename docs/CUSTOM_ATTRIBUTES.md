# Custom SAML Attributes Configuration

This document explains how to configure custom SAML attributes for different applications like Grafana Cloud, AWS Console, and other SAML 2.0 compatible services.

## Overview

The SAML IdP now supports flexible, application-specific SAML attributes that can be configured directly in DynamoDB. This allows you to:

- **Use different attributes for different applications** (e.g., AWS Console vs Grafana Cloud)
- **Store attributes with `attr_` prefix** for visual distinction in DynamoDB
- **Map short attribute names to full SAML attribute URIs** automatically
- **Make attributes optional** - only attributes present in DynamoDB are included in SAML assertions

## Attribute Mapping Table

The attribute mapping is centrally managed in the Terraform configuration (`definitions.tf`) as a local variable. This ensures both Lambda functions use the same mapping and prevents inconsistencies.

To add or modify attribute mappings, update the `local.attribute_mapping` in `definitions.tf`:

```hcl
locals {
  attribute_mapping = {
    attr_aws_role                = "https://aws.amazon.com/SAML/Attributes/Role"
    attr_aws_role_session_name   = "https://aws.amazon.com/SAML/Attributes/RoleSessionName"
    attr_aws_session_duration    = "https://aws.amazon.com/SAML/Attributes/SessionDuration"
    attr_email                   = "email"
    attr_name                    = "name"
    attr_given_name              = "givenName"
    attr_surname                 = "surname"
    attr_display_name            = "displayName"
    attr_uid                     = "uid"
    attr_groups                  = "groups"
  }
}
```

The following short attribute names (stored in DynamoDB) are automatically mapped to their full SAML attribute names:

| Short Name (DynamoDB) | Full SAML Attribute Name |
|----------------------|--------------------------|
| `attr_aws_role` | `https://aws.amazon.com/SAML/Attributes/Role` |
| `attr_aws_role_session_name` | `https://aws.amazon.com/SAML/Attributes/RoleSessionName` |
| `attr_aws_session_duration` | `https://aws.amazon.com/SAML/Attributes/SessionDuration` |
| `attr_email` | `email` |
| `attr_name` | `name` |
| `attr_given_name` | `givenName` |
| `attr_surname` | `surname` |
| `attr_display_name` | `displayName` |
| `attr_uid` | `uid` |
| `attr_groups` | `groups` |

You can also add custom attributes not in this table - they will be included with their name (without the `attr_` prefix).

## Configuration Examples

### AWS Console Configuration

For AWS Console access, you need to include AWS-specific attributes:

**DynamoDB Role Record:**
```json
{
  "username": "john.doe",
  "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
  "account_name": "Production Account",
  "account_id": "123456789012",
  "description": "Full administrator access to production resources",
  "acs_url": "https://signin.aws.amazon.com/saml",
  "attr_aws_role": "true",
  "attr_aws_role_session_name": "true",
  "attr_aws_session_duration": "43200",
  "created_at": "2024-01-08T00:00:00Z"
}
```

**Lambda Invocation (create role):**
```json
{
  "operation": "create_role",
  "data": {
    "username": "john.doe",
    "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
    "account_name": "Production Account",
    "acs_url": "https://signin.aws.amazon.com/saml",
    "description": "Full administrator access to production resources",
    "attr_aws_role": "true",
    "attr_aws_role_session_name": "true",
    "attr_aws_session_duration": "43200"
  }
}
```

**Resulting SAML Attributes:**
```xml
<saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/Role">
  <saml:AttributeValue>arn:aws:iam::123456789012:role/AdminRole,arn:aws:iam::123456789012:saml-provider/SimpleSAMLIdP</saml:AttributeValue>
</saml:Attribute>
<saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/RoleSessionName">
  <saml:AttributeValue>john.doe</saml:AttributeValue>
</saml:Attribute>
<saml:Attribute Name="https://aws.amazon.com/SAML/Attributes/SessionDuration">
  <saml:AttributeValue>43200</saml:AttributeValue>
</saml:Attribute>
```

### Grafana Cloud Configuration

For Grafana Cloud, you don't need AWS-specific attributes. Instead, configure user profile attributes plus two role-level SP settings:

- `acs_url`: Grafana's Assertion Consumer Service URL (`https://<stack>.grafana.net/saml/acs`)
- `audience`: Grafana's SP Entity ID as shown in its SAML settings (used for `<saml:Audience>`; omit to keep `urn:amazon:webservices` for AWS)
- `nameid_format`: NameID format URI. Use `urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress` so users are identified by email; when set, the user's `email` from the Users table is used as NameID value

**DynamoDB Role Record:**
```json
{
  "username": "jane.smith",
  "role_arn": "grafana:viewer",
  "account_name": "Grafana Cloud",
  "account_id": "",
  "description": "Grafana Cloud monitoring access",
  "acs_url": "https://mystack.grafana.net/saml/acs",
  "audience": "https://mystack.grafana.net",
  "nameid_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
  "attr_email": "jane.smith@example.com",
  "attr_display_name": "Jane Smith",
  "attr_name": "Jane Smith",
  "attr_groups": "Editors",
  "created_at": "2024-01-08T00:00:00Z"
}
```

**Lambda Invocation (create role):**
```json
{
  "operation": "create_role",
  "data": {
    "username": "jane.smith",
    "role_arn": "grafana:viewer",
    "account_name": "Grafana Cloud",
    "acs_url": "https://mystack.grafana.net/saml/acs",
    "audience": "https://mystack.grafana.net",
    "nameid_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
    "description": "Grafana Cloud monitoring access",
    "attr_email": "jane.smith@example.com",
    "attr_display_name": "Jane Smith",
    "attr_name": "Jane Smith",
    "attr_groups": "Editors"
  }
}
```

**Resulting SAML Attributes:**
```xml
<saml:Attribute Name="email">
  <saml:AttributeValue>jane.smith@example.com</saml:AttributeValue>
</saml:Attribute>
<saml:Attribute Name="displayName">
  <saml:AttributeValue>Jane Smith</saml:AttributeValue>
</saml:Attribute>
<saml:Attribute Name="name">
  <saml:AttributeValue>Jane Smith</saml:AttributeValue>
</saml:Attribute>
<saml:Attribute Name="groups">
  <saml:AttributeValue>Editors</saml:AttributeValue>
</saml:Attribute>
```

## Important Notes

### Role ARN for Non-AWS Applications

For non-AWS applications like Grafana Cloud, you still need to provide a `role_arn` value because it's part of the DynamoDB composite key (username + role_arn). Use a descriptive identifier:

- `grafana:viewer` - Grafana viewer role
- `grafana:editor` - Grafana editor role
- `grafana:admin` - Grafana admin role
- `app:role_name` - Any custom application with role name

### Backward Compatibility

If no custom attributes are specified but a valid AWS IAM role ARN is provided, the system will automatically include the default AWS attributes for backward compatibility:
- `RoleSessionName`
- `Role`
- `SessionDuration`

### Adding Custom Attributes

You can add any custom attribute by prefixing it with `attr_`:

```json
{
  "username": "user",
  "role_arn": "app:custom",
  "acs_url": "https://app.example.com/saml/acs",
  "attr_custom_field": "custom_value",
  "attr_another_field": "another_value"
}
```

These will be included in the SAML assertion with the attribute name being the key without the `attr_` prefix (e.g., `custom_field` and `another_field`).

## Shell Scripts

You can also use the provided shell scripts to add roles with custom attributes:

```bash
# The add-role.sh script doesn't directly support custom attributes
# Use the Lambda function or AWS CLI to add roles with custom attributes

# Example using AWS CLI to invoke Lambda directly:
aws lambda invoke \
  --function-name simple-saml-idp-manage-users-roles-dev \
  --payload file://examples/lambda-create-role-grafana.json \
  response.json
```

## Updating Existing Roles

To update an existing role with new custom attributes:

```json
{
  "operation": "update_role",
  "data": {
    "username": "john.doe",
    "role_arn": "arn:aws:iam::123456789012:role/AdminRole",
    "attr_aws_session_duration": "28800"
  }
}
```

This will update only the specified attributes, leaving others unchanged.

## Security Considerations

- All attributes are stored in DynamoDB with encryption at rest
- Attributes are only included in SAML assertions for authenticated users
- The `role_arn` is used as part of the composite key for uniqueness
- Custom attributes should not contain sensitive data that shouldn't be shared with the target application
- Always validate that the ACS URL matches your intended application before configuring attributes
