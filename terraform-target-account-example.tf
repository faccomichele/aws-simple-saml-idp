# # This is an example configuration to start using the Simple SAML IdP in a TARGET account.
# # You would apply this Terraform configuration in the AWS account that you want to log INTO.

# variable "environment_name" {
#   description = "Environment name to append to the provider name (e.g., dev, prod)"
#   type        = string
#   default     = "dev"
# }

# variable "saml_metadata_content" {
#   description = "The raw XML content of the SAML metadata"
#   type        = string
#   # In a real setup, you might load this from a file: file("${path.module}/saml-metadata.xml")
# }

# resource "aws_iam_saml_provider" "central_saml_idp" {
#   name                   = "CentralSAMLIdP-${var.environment_name}"
#   saml_metadata_document = var.saml_metadata_content
  
#   tags = {
#     Environment = var.environment_name
#     Application = "SimpleSAMLIdP"
#     ManagedBy   = "Terraform"
#   }
# }

# # Output the ARN to be used in IAM Role trust relationships
# output "saml_provider_arn" {
#   value       = aws_iam_saml_provider.central_saml_idp.arn
#   description = "The ARN of the SAML Provider to use in IAM Role trust policies"
# }
