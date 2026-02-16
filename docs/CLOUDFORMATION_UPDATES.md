# CloudFormation IAM Policy Updates

This document details the updates made to `cloudformation/github-iam-role.yaml` to align with the actual Terraform resource naming patterns and required permissions.

## Problem Statement

The CloudFormation template previously used resource naming patterns from a different project (`oidc-provider-*`), which did not match the actual resources created by the Terraform configuration in this repository. This mismatch would have caused permission errors during `terraform apply` and `terraform destroy` operations.

## Summary of Changes

### Resource Naming Pattern Updates

| Service | Old Pattern | New Pattern |
|---------|------------|-------------|
| Lambda Functions | `oidc-provider-${Environment}-*` | `simple-saml-idp-*-${Environment}` |
| Lambda Layers | (missing) | `simple-saml-idp-*-${Environment}` |
| DynamoDB Tables | `oidc-provider-${Environment}-*` | `simple-saml-idp-*-${Environment}` |
| S3 Buckets | `oidc-provider-${Environment}-*` | `simple-saml-idp-login-${Environment}-*` |
| SSM Parameters | `/oidc-provider/${Environment}/*` | `/simple-saml-idp/${Environment}/*` |
| IAM Roles | `oidc-provider-${Environment}-lambda-exec` | `simple-saml-idp-lambda-${Environment}` |
| CloudWatch Logs | `/aws/lambda/oidc-provider-${Environment}-*` | `/aws/lambda/simple-saml-idp-*-${Environment}` |

### API Gateway Changes

**Before:**
- Supported REST API (`/restapis`)
- Included API Gateway account settings permissions

**After:**
- Supports HTTP API v2 (`/apis`) - matches actual Terraform configuration
- Removed unnecessary account settings permissions
- Added tag management permissions (TagResource, UntagResource)

### Added Permissions

#### Lambda Layer Management
- `lambda:PublishLayerVersion` - Required for creating Lambda layers
- `lambda:DeleteLayerVersion` - Required for destroying Lambda layers
- `lambda:GetLayerVersion` - Required for reading layer details
- Layer ARN patterns for both unversioned and versioned layers

#### CloudFront Support
Added complete CloudFront management permissions (new section):
- `cloudfront:CreateDistribution`
- `cloudfront:GetDistribution`
- `cloudfront:GetDistributionConfig`
- `cloudfront:UpdateDistribution`
- `cloudfront:DeleteDistribution`
- `cloudfront:TagResource`
- `cloudfront:ListTagsForResource`
- `cloudfront:CreateCloudFrontOriginAccessIdentity`
- `cloudfront:GetCloudFrontOriginAccessIdentity`
- `cloudfront:DeleteCloudFrontOriginAccessIdentity`
- `cloudfront:ListDistributions` (in ResourceDiscovery)
- `cloudfront:ListCloudFrontOriginAccessIdentities` (in ResourceDiscovery)

#### API Gateway Tagging
- `apigateway:TagResource` - For tagging API Gateway resources
- `apigateway:UntagResource` - For removing tags

### Removed Permissions

1. **API Gateway Account Settings** (entire section removed):
   - `apigateway:UpdateAccount`
   - `apigateway:PATCH` (for account)
   - `apigateway:GET` (for account)
   - Not needed for HTTP API v2 (only required for REST API)

2. **Lambda Version Management**:
   - `lambda:PublishVersion` - Not used in this Terraform configuration

3. **CloudWatch Logs Wildcard Permissions**:
   - Removed overly broad wildcard log group permissions
   - Consolidated into single statement with specific resource patterns

### Consolidated Changes

#### CloudWatch Logs
**Before:** 
- Separate statements for Lambda and API Gateway
- Wildcard permissions for API Gateway logs

**After:**
- Single consolidated statement
- Specific resource patterns for both Lambda and API Gateway logs

#### IAM Role Management
**Before:**
- Referenced two roles: Lambda execution and API Gateway CloudWatch role

**After:**
- Single Lambda execution role reference (API Gateway CloudWatch role not needed for HTTP API)

### Other Updates

1. **Default ProjectName Parameter**: Changed from `terraform-core-oidc` to `simple-saml-idp`
2. **Comments**: Updated comments to accurately reflect the supported API Gateway version and resource types

## Validation

The updated template has been validated using:
- `cfn-lint` - CloudFormation linter
- YAML syntax validation
- Manual review of all resource ARN patterns against Terraform configuration

### Known Warnings

The following cfn-lint warnings are acceptable:
- `W2001`: OIDCProviderStackName parameter not used (kept for potential future use)
- `W3037`: TagResource/UntagResource warnings are false positives (valid API Gateway v2 actions)
- `W1020`: !Sub used for consistency even when no variables present

## Testing Recommendations

After deploying the updated CloudFormation stack:

1. **Test terraform apply**: Verify all resources can be created
2. **Test terraform destroy**: Verify all resources can be destroyed
3. **Check CloudWatch Logs**: Ensure Lambda and API Gateway can write logs
4. **Verify Tags**: Ensure tags are properly applied to all resources

## Terraform Resources Covered

The updated permissions support all resources defined in `main.tf`:

- ✅ DynamoDB tables (users, roles)
- ✅ S3 bucket (login page)
- ✅ S3 bucket policies and configurations
- ✅ Lambda function and execution role
- ✅ Lambda layer
- ✅ API Gateway HTTP API v2
- ✅ API Gateway routes and stages
- ✅ CloudWatch Log Groups
- ✅ SSM Parameters
- ✅ CloudFront Distribution (conditional)
- ✅ CloudFront Origin Access Identity (conditional)

## Impact Assessment

### Breaking Changes
None - This is a fix to align permissions with actual resource names

### Required Actions
1. Update or redeploy CloudFormation stack with new template
2. No changes required to Terraform configuration
3. No changes required to existing deployed resources

### Benefits
1. ✅ Permissions now match actual Terraform resources
2. ✅ Supports both apply and destroy operations
3. ✅ Includes all necessary permissions for optional CloudFront resources
4. ✅ More precise permission scoping (follows least privilege principle)
5. ✅ Removes unnecessary permissions (reduced attack surface)

## References

- Terraform Configuration: `main.tf`, `variables.tf`, `outputs.tf`
- CloudFormation Template: `cloudformation/github-iam-role.yaml`
- IAM Policy Documentation: `IAM_POLICY.md`
- AWS API Gateway v2 API Reference: https://docs.aws.amazon.com/apigatewayv2/latest/api-reference/
- AWS Lambda API Reference: https://docs.aws.amazon.com/lambda/latest/dg/API_Reference.html
- AWS CloudFront API Reference: https://docs.aws.amazon.com/cloudfront/latest/APIReference/
