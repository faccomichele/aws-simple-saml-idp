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
    attr_role                    = "role"
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
| `attr_role` | `role` |

You can also add custom attributes not in this table - they will be included with their name (without the `attr_` prefix).

## Role Groups Field

Role records support an optional `groups` field: a comma-separated string of group names
(e.g., `"Grafana"` or `"AWS Production, Billing"`).

It is used for **portal grouping only**: the first value is used as the section header in the
Unified SSO Portal role panel (roles without a group fall under "Other").

Groups are **never emitted via SAML** - no `groups` attribute is added to assertions for AWS,
Grafana or any other application. The legacy `attr_groups` custom attribute is stripped as well,
so neither field can leak into an assertion. Assign Grafana roles inside Grafana (or via its own
`org_mapping` fed by other attributes) instead.

**DynamoDB / Lambda payload example:**
```json
{
  "username": "jane.smith",
  "role_arn": "grafana:viewer",
  "groups": "Grafana"
}
```

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

For Grafana Cloud, you don't need AWS-specific attributes. Keep `role_arn` as the non-empty role-record identifier, and the IdP automatically emits the final segment of that value as the SAML `role` attribute. For example, `grafana:viewer` remains the DynamoDB and portal identifier but emits `role=viewer` to Grafana. Configure the role-level SP settings and user profile attributes below:

- `acs_url`: Grafana's Assertion Consumer Service URL (`https://<stack>.grafana.net/saml/acs`)
- `audience`: must equal Grafana's **SP Entity ID** exactly. Grafana Cloud defaults its Entity ID to its metadata URL (`https://<stack>.grafana.net/saml/metadata` — shown as "SP metadata URL / SP Entity ID" in the SAML settings), so use that full string, not the bare stack domain. A mismatch here causes "Login provider denied login request". Omit to keep `urn:amazon:webservices` for AWS roles
- `nameid_format`: NameID format URI. Use `urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress` so users are identified by email; when set, the user's `email` from the Users table is used as NameID value
- `relay_state`: RelayState echoed in the auto-submit form on IdP-initiated logins. Grafana Cloud requires this field and compares it **byte-for-byte** with its own Relay State setting (including trailing spaces). SP-initiated logins always echo the RelayState from the AuthnRequest instead; store the DynamoDB value verbatim (beware editors/scripts trimming whitespace)
- `role_arn`: required non-empty internal identifier, such as `grafana:viewer`; it is not emitted as a `role_arn` SAML attribute
- `attr_role`: optional explicit SAML role override. If omitted, the final segment of `role_arn` is used automatically

**DynamoDB Role Record:**
```json
{
  "username": "jane.smith",
  "role_arn": "grafana:viewer",
  "account_name": "Grafana Cloud",
  "account_id": "",
  "description": "Grafana Cloud monitoring access",
  "acs_url": "https://mystack.grafana.net/saml/acs",
  "audience": "https://mystack.grafana.net/saml/metadata",
  "nameid_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
  "groups": "Grafana",
  "relay_state": "unified-sso-portal",
  "attr_email": "jane.smith@example.com",
  "attr_display_name": "Jane Smith",
  "attr_name": "Jane Smith",
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
    "audience": "https://mystack.grafana.net/saml/metadata",
    "nameid_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
    "description": "Grafana Cloud monitoring access",
    "groups": "Grafana",
    "relay_state": "unified-sso-portal",
    "attr_email": "jane.smith@example.com",
    "attr_display_name": "Jane Smith",
    "attr_name": "Jane Smith"
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
<saml:Attribute Name="role">
  <saml:AttributeValue>viewer</saml:AttributeValue>
</saml:Attribute>
```

Note: the `groups` field is deliberately absent from assertions - it is used for portal
grouping only.

## Important Notes

### Role ARN for Non-AWS Applications

For non-AWS applications like Grafana Cloud, you still need to provide a `role_arn` value because it's part of the DynamoDB composite key (username + role_arn). Use a descriptive identifier:

- `grafana:viewer` - Grafana viewer role
- `grafana:editor` - Grafana editor role
- `grafana:admin` - Grafana admin role
- `app:role_name` - Any custom application with role name

For non-AWS role identifiers, the final colon-separated segment is emitted as the SAML `role` attribute. For example, `grafana:viewer` emits `role=viewer`. Add `attr_role` only when the SAML role value should differ from that derived value.

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
