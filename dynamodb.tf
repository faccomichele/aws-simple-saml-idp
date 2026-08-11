# DynamoDB Tables
resource "aws_dynamodb_table" "users" {
  name         = "${local.project_alias}-users-${local.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "username"

  attribute {
    name = "username"
    type = "S"
  }

  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name            = "EmailIndex"
    key_schema {
      attribute_name = "email"
      key_type       = "HASH"
    }
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${local.project_alias}-users-${local.environment}"
    RepositoryFile = "dynamodb.tf"
  }
}

resource "aws_dynamodb_table" "roles" {
  name         = "${local.project_alias}-roles-${local.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "username"
  range_key    = "role_arn"

  attribute {
    name = "username"
    type = "S"
  }

  attribute {
    name = "role_arn"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "${local.project_alias}-roles-${local.environment}"
    RepositoryFile = "dynamodb.tf"
  }
}
