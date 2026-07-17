# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.saml_processor.function_name}"
  retention_in_days = local.log_retention_days

  tags = {
    Name = "${local.project_alias}-lambda-logs-${local.environment}"
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${local.project_alias}-${local.environment}"
  retention_in_days = local.log_retention_days

  tags = {
    Name = "${local.project_alias}-api-logs-${local.environment}"
  }
}
