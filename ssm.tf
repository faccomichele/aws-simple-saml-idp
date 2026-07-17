# SSM Parameters for SAML Configuration
# These are created with placeholder values and must be updated manually after deployment
# The lifecycle ignore_changes prevents Terraform from overwriting the actual values
resource "aws_ssm_parameter" "saml_private_key" {
  name        = "/${local.project_alias}/${local.environment}/saml/private_key"
  description = "SAML signing private key (RSA) - MUST be replaced with actual key after deployment"
  type        = "SecureString"
  value       = "PLACEHOLDER_REPLACE_WITH_ACTUAL_KEY"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "${local.project_alias}-saml-private-key-${local.environment}"
  }
}

resource "aws_ssm_parameter" "saml_certificate" {
  name        = "/${local.project_alias}/${local.environment}/saml/certificate"
  description = "SAML signing certificate (X.509) - MUST be replaced with actual cert after deployment"
  type        = "String"
  value       = "PLACEHOLDER_REPLACE_WITH_ACTUAL_CERT"

  lifecycle {
    ignore_changes = [value]
  }

  tags = {
    Name = "${local.project_alias}-saml-certificate-${local.environment}"
  }
}

resource "aws_ssm_parameter" "idp_base_url" {
  name        = "/${local.project_alias}/${local.environment}/idp/base/url"
  description = "Base URL for the IdP (used for ACS URL and SSO endpoints) - Only used when a custom domain is not configured"
  type        = "String"
  value       = aws_apigatewayv2_stage.saml.invoke_url
  count       = var.idp_base_url != "placeholder" ? 0 : 1

  tags = {
    Name = "${local.project_alias}-idp-base-url-${local.environment}"
  }
}
