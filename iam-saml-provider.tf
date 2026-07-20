resource "aws_iam_saml_provider" "central_saml_idp" {
  name                   = "${var.saml_provider_name}-${local.environment}"
  saml_metadata_document = data.http.metadata.response_body
  
  tags = merge(local.tags,
    {
      Name = "${local.project_alias}-saml-provider-${local.environment}"
      File = "iam-saml-provider.tf"
    }
  )
}
