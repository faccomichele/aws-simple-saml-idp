resource "aws_iam_saml_provider" "central_saml_idp" {
  name                   = "CentralSAMLIdP-${local.environment}"
  saml_metadata_document = data.http.metadata.body
  
  tags = {
    Environment = local.environment
    Application = "SimpleSAMLIdP"
    ManagedBy   = "Terraform"
  }
}
