# Data Sources
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "http" "metadata" {
  url = "${aws_apigatewayv2_stage.saml.invoke_url}/metadata"
  depends_on = [
    aws_apigatewayv2_api.saml,
    aws_lambda_function.saml_processor,
    aws_lambda_permission.api_gateway
  ]
}
