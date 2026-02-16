# AWS IAM Policy for Terraform Deployment

This document provides the minimum IAM permissions required to deploy the Simple SAML IdP infrastructure using Terraform.

## Using the CloudFormation Template (Recommended)

For GitHub Actions deployments, use the CloudFormation template at `cloudformation/github-iam-role.yaml`. This template:
- Creates a GitHub Actions IAM role with OIDC authentication
- Includes all necessary permissions scoped to the correct resource names
- Supports both `terraform apply` and `terraform destroy` operations
- Uses the naming pattern: `simple-saml-idp-*-{environment}` for all resources

The CloudFormation template provides a production-ready IAM configuration with:
- Lambda function and layer management
- API Gateway v2 (HTTP API) support
- CloudFront distribution management (conditional)
- DynamoDB table operations
- S3 bucket management
- SSM Parameter Store access
- CloudWatch Logs management

## Manual Deployment Policy

If you prefer to create IAM policies manually instead of using CloudFormation, use the following policy.

## Deployment User Policy

Create an IAM user or role with the following policy for deploying the infrastructure:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaManagement",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:ListVersionsByFunction",
        "lambda:PublishLayerVersion",
        "lambda:DeleteLayerVersion",
        "lambda:GetLayerVersion"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:simple-saml-idp-*",
        "arn:aws:lambda:*:*:layer:simple-saml-idp-*"
      ]
    },
    {
      "Sid": "IAMManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::*:role/simple-saml-idp-*"
    },
    {
      "Sid": "APIGatewayManagement",
      "Effect": "Allow",
      "Action": [
        "apigateway:GET",
        "apigateway:POST",
        "apigateway:PUT",
        "apigateway:DELETE",
        "apigateway:PATCH"
      ],
      "Resource": "arn:aws:apigateway:*::/*"
    },
    {
      "Sid": "DynamoDBManagement",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:DescribeContinuousBackups",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:UpdateTable",
        "dynamodb:UpdateContinuousBackups",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:ListTagsOfResource",
        "dynamodb:TagResource",
        "dynamodb:UntagResource"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/simple-saml-idp-*"
    },
    {
      "Sid": "S3Management",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:GetBucketPolicy",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:GetBucketVersioning",
        "s3:PutBucketVersioning",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetBucketTagging",
        "s3:PutBucketTagging",
        "s3:ListBucket",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::simple-saml-idp-*",
        "arn:aws:s3:::simple-saml-idp-*/*"
      ]
    },
    {
      "Sid": "CloudFrontManagement",
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateDistribution",
        "cloudfront:GetDistribution",
        "cloudfront:GetDistributionConfig",
        "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution",
        "cloudfront:TagResource",
        "cloudfront:ListTagsForResource",
        "cloudfront:CreateCloudFrontOriginAccessIdentity",
        "cloudfront:GetCloudFrontOriginAccessIdentity",
        "cloudfront:GetCloudFrontOriginAccessIdentityConfig",
        "cloudfront:UpdateCloudFrontOriginAccessIdentity",
        "cloudfront:DeleteCloudFrontOriginAccessIdentity",
        "cloudfront:CreateInvalidation"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SSMManagement",
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:DeleteParameter",
        "ssm:DescribeParameters",
        "ssm:AddTagsToResource",
        "ssm:RemoveTagsFromResource",
        "ssm:ListTagsForResource"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/simple-saml-idp/*"
    },
    {
      "Sid": "CloudWatchLogsManagement",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
        "logs:ListTagsLogGroup",
        "logs:TagLogGroup",
        "logs:UntagLogGroup"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/aws/lambda/simple-saml-idp-*",
        "arn:aws:logs:*:*:log-group:/aws/apigateway/simple-saml-idp-*"
      ]
    },
    {
      "Sid": "KMSDecrypt",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:DescribeKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": [
            "ssm.*.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

## Post-Deployment Operations Policy

After deployment, create a separate user/role for managing users and roles:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBOperations",
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/simple-saml-idp-users-*",
        "arn:aws:dynamodb:*:*:table/simple-saml-idp-roles-*"
      ]
    },
    {
      "Sid": "SSMOperations",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:PutParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/simple-saml-idp/*"
    },
    {
      "Sid": "S3Operations",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::simple-saml-idp-*/*"
    },
    {
      "Sid": "CloudFrontInvalidation",
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/aws/lambda/simple-saml-idp-*",
        "arn:aws:logs:*:*:log-group:/aws/apigateway/simple-saml-idp-*"
      ]
    }
  ]
}
```

## SAML Provider Setup Policy (Target Accounts)

In each target AWS account where users will SSO, an administrator needs permissions to create the SAML provider:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SAMLProviderManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateSAMLProvider",
        "iam:GetSAMLProvider",
        "iam:UpdateSAMLProvider",
        "iam:DeleteSAMLProvider"
      ],
      "Resource": "arn:aws:iam::*:saml-provider/SimpleSAMLIdP"
    },
    {
      "Sid": "RoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:UpdateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/SAML*"
    }
  ]
}
```

## Notes

1. **Resource Naming**: The policies above assume the default project name `simple-saml-idp`. Adjust if you use a different project name.

2. **Least Privilege**: These policies provide the minimum permissions needed. In production, consider further restrictions based on your environment.

3. **Region Specific**: Replace `*` in region fields with specific regions if needed.

4. **Account Specific**: Replace account IDs (`*`) with specific account IDs for better security.

5. **CloudFront Global**: CloudFront is a global service and requires `"Resource": "*"` for some operations.

## CloudFormation Template Details

The `cloudformation/github-iam-role.yaml` template creates IAM policies that match the exact resource naming patterns used by the Terraform configuration:

### Resource Naming Patterns

| Resource Type | Pattern | Example |
|--------------|---------|---------|
| Lambda Function | `simple-saml-idp-processor-{env}` | `simple-saml-idp-processor-dev` |
| Lambda Layer | `simple-saml-idp-dependencies-{env}` | `simple-saml-idp-dependencies-dev` |
| DynamoDB Tables | `simple-saml-idp-{table}-{env}` | `simple-saml-idp-users-dev` |
| S3 Bucket | `simple-saml-idp-login-{env}-{account_id}` | `simple-saml-idp-login-dev-123456789012` |
| IAM Role | `simple-saml-idp-lambda-{env}` | `simple-saml-idp-lambda-dev` |
| SSM Parameters | `/simple-saml-idp/{env}/*` | `/simple-saml-idp/dev/saml/certificate` |
| CloudWatch Logs | `/aws/lambda/simple-saml-idp-processor-{env}` | `/aws/lambda/simple-saml-idp-processor-dev` |
| API Gateway | `simple-saml-idp-api-{env}` | `simple-saml-idp-api-dev` |

### Key Features

1. **API Gateway v2 Support**: The template uses HTTP API v2 endpoints (`/apis`) instead of REST API (`/restapis`)
2. **Lambda Layers**: Includes permissions for Lambda layer management (PublishLayerVersion, DeleteLayerVersion)
3. **CloudFront**: Full support for CloudFront distributions and Origin Access Identities
4. **Scoped Permissions**: All resources are scoped to the project name and environment
5. **Tag Management**: Includes permissions for managing tags on all supported resources

### Usage

Deploy the CloudFormation stack with:

```bash
aws cloudformation create-stack \
  --stack-name github-role-simple-saml-idp-dev \
  --template-body file://cloudformation/github-iam-role.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=simple-saml-idp \
    ParameterKey=TerraformAccessPolicyAccountID,ParameterValue=YOUR_ACCOUNT_ID \
  --capabilities CAPABILITY_IAM
```

## Creating the IAM User

```bash
# Create user
aws iam create-user --user-name terraform-saml-idp-deployer

# Create policy
aws iam create-policy \
  --policy-name TerraformSAMLIdPDeployment \
  --policy-document file://deployment-policy.json

# Attach policy to user
aws iam attach-user-policy \
  --user-name terraform-saml-idp-deployer \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/TerraformSAMLIdPDeployment

# Create access key
aws iam create-access-key --user-name terraform-saml-idp-deployer
```

Store the access key securely and configure AWS CLI:

```bash
aws configure --profile saml-idp-deployer
```

Then use this profile for deployment:

```bash
export AWS_PROFILE=saml-idp-deployer
terraform apply
```
