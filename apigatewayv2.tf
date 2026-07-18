# API Gateway HTTP API
resource "aws_apigatewayv2_api" "saml" {
  name          = "${local.project_alias}-api-${local.environment}"
  protocol_type = "HTTP"
  description   = "SAML IdP API for AWS Console SSO"

  cors_configuration {
    allow_origins = var.allowed_cors_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }

  tags = {
    Name = "${local.project_alias}-api-${local.environment}"
  }
}

# Lambda Integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.saml.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.saml_processor.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# API Routes
resource "aws_apigatewayv2_route" "metadata" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "GET /metadata"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "sso" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /sso"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "login" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /login"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "acs" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /acs"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "mfa_setup" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /mfa/setup"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "mfa_verify" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /mfa/verify"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# API Stage
resource "aws_apigatewayv2_stage" "saml" {
  api_id      = aws_apigatewayv2_api.saml.id
  name        = local.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = {
    Name = "${local.project_alias}-api-stage-${local.environment}"
  }
}
