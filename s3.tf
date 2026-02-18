# S3 Bucket for Login Page
resource "aws_s3_bucket" "login_page" {
  bucket = "${local.project_name}-login-${local.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${local.project_name}-login-${local.environment}"
  }
}

resource "aws_s3_bucket_public_access_block" "login_page" {
  bucket = aws_s3_bucket.login_page.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "login_page" {
  bucket = aws_s3_bucket.login_page.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "login_page" {
  bucket = aws_s3_bucket.login_page.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Policy for CloudFront
resource "aws_s3_bucket_policy" "login_page" {
  bucket = aws_s3_bucket.login_page.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAI"
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.login_page[0].iam_arn
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.login_page.arn}/*"
      }
    ]
  })
}
