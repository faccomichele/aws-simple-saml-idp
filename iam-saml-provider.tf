# resource "aws_iam_saml_provider" "central_saml_idp" {
#   name                   = "${var.saml_provider_name}-${local.environment}"
#   saml_metadata_document = data.http.metadata.body
  
#   tags = {
#     Environment = local.environment
#     Application = local.project_name
#     ManagedBy   = "Terraform"
#   }
# }
