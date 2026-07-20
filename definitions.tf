locals {
  environment         = terraform.workspace
  aws_region          = "us-east-1"
  project_name        = var.tags["Project"] != null ? var.tags["Project"] : "unknown"
  project_alias       = "simple-saml-idp"
  log_retention_days  = local.environment == "dev" ? 7 : 30
  python_runtime      = "python3.13"
  tags                = var.tags 
}

locals {
  idp_entity_id       = var.idp_entity_id == "placeholder" ? "https://${aws_cloudfront_distribution.login_page.domain_name}" : var.idp_entity_id
}

# SAML Attribute Mapping Configuration
# Maps short attribute names (stored in DynamoDB) to full SAML attribute names
# This is shared across both Lambda functions to ensure consistency
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
