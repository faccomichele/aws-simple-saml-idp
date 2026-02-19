# API Gateway HTTP API
resource "aws_apigatewayv2_api" "saml" {
  name          = "${local.project_name}-api-${local.environment}"
  protocol_type = "HTTP"
  description   = "SAML IdP API for AWS Console SSO"

  cors_configuration {
    allow_origins = var.allowed_cors_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }

  tags = {
    Name = "${local.project_name}-api-${local.environment}"
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
    Name = "${local.project_name}-api-stage-${local.environment}"
  }
}

# Lambda Integration for OIDC
resource "aws_apigatewayv2_integration" "lambda_oidc" {
  api_id                 = aws_apigatewayv2_api.saml.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.oidc_processor.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

# OIDC Routes
resource "aws_apigatewayv2_route" "oidc_discovery" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "GET /.well-known/openid-configuration"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_oidc.id}"
}

resource "aws_apigatewayv2_route" "oidc_jwks" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "GET /oauth2/jwks"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_oidc.id}"
}

resource "aws_apigatewayv2_route" "oidc_authorize_get" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "GET /oauth2/authorize"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_oidc.id}"
}

resource "aws_apigatewayv2_route" "oidc_authorize_post" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /oauth2/authorize"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_oidc.id}"
}

resource "aws_apigatewayv2_route" "oidc_token" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "POST /oauth2/token"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_oidc.id}"
}

resource "aws_apigatewayv2_route" "oidc_userinfo" {
  api_id    = aws_apigatewayv2_api.saml.id
  route_key = "GET /oauth2/userinfo"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_oidc.id}"
}
