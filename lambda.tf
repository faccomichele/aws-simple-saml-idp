# Lambda Layer for dependencies
resource "aws_lambda_layer_version" "saml_processor_dependencies" {
  filename                 = "${path.module}/lambda/saml_processor-layer.zip"
  layer_name               = "${local.project_alias}-sp-dependencies-${local.environment}"
  compatible_runtimes      = ["python3.13"]
  source_code_hash         = filebase64sha256("${path.module}/lambda/saml_processor-layer.zip")
  compatible_architectures = ["x86_64", "arm64"]
  description              = "SAML and cryptography dependencies"
}

# Lambda Function for SAML Processing
resource "aws_lambda_function" "saml_processor" {
  filename         = "${path.module}/lambda/saml_processor.zip"
  function_name    = "${local.project_alias}-processor-${local.environment}"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "index.lambda_handler"
  source_code_hash = filebase64sha256("${path.module}/lambda/saml_processor.zip")
  runtime          = "python3.13"
  timeout          = 30
  memory_size      = 512
  architectures    = ["x86_64"]

  layers = [aws_lambda_layer_version.saml_processor_dependencies.arn]

  environment {
    variables = {
      USERS_TABLE          = aws_dynamodb_table.users.name
      ROLES_TABLE          = aws_dynamodb_table.roles.name
      IDP_ENTITY_ID        = local.idp_entity_id
      IDP_BASE_URL         = var.idp_base_url
      SESSION_DURATION     = var.session_duration_seconds
      SSM_PARAMETER_PREFIX = "/${local.project_alias}/${local.environment}"
      ALLOWED_AWS_ACCOUNTS = jsonencode(var.allowed_aws_accounts)
      SAML_PROVIDER_NAME   = "${var.saml_provider_name}-${local.environment}"
      ATTRIBUTE_MAPPING    = jsonencode(local.attribute_mapping)
    }
  }

  tags = {
    Name = "${local.project_alias}-processor-${local.environment}"
  }
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.saml_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.saml.execution_arn}/*/*"
}

# Lambda Layer for dependencies
resource "aws_lambda_layer_version" "manage_users_roles_dependencies" {
  filename                 = "${path.module}/lambda/manage_users_roles-layer.zip"
  layer_name               = "${local.project_alias}-mur-dependencies-${local.environment}"
  compatible_runtimes      = ["python3.13"]
  source_code_hash         = filebase64sha256("${path.module}/lambda/manage_users_roles-layer.zip")
  compatible_architectures = ["x86_64", "arm64"]
  description              = "SAML and cryptography dependencies"
}

# Lambda Function for User and Role Management
resource "aws_lambda_function" "manage_users_roles" {
  filename         = "${path.module}/lambda/manage_users_roles.zip"
  function_name    = "${local.project_alias}-manage-users-roles-${local.environment}"
  role             = aws_iam_role.lambda_execution.arn
  handler          = "index.lambda_handler"
  source_code_hash = filebase64sha256("${path.module}/lambda/manage_users_roles.zip")
  runtime          = "python3.13"
  timeout          = 30
  memory_size      = 256
  architectures    = ["x86_64"]

  layers = [aws_lambda_layer_version.manage_users_roles_dependencies.arn]

  environment {
    variables = {
      USERS_TABLE       = aws_dynamodb_table.users.name
      ROLES_TABLE       = aws_dynamodb_table.roles.name
      ATTRIBUTE_MAPPING = jsonencode(local.attribute_mapping)
    }
  }

  tags = {
    Name = "${local.project_alias}-manage-users-roles-${local.environment}"
  }
}
