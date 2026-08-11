# CloudFront Origin Access Identity
resource "aws_cloudfront_origin_access_identity" "login_page" {
  comment = "OAI for ${local.project_alias} login page"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "login_page" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name = aws_s3_bucket.login_page.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.login_page.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.login_page.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.login_page.id}"

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "${local.project_alias}-login-${local.environment}"
    RepositoryFile = "cloudfrfont.tf"
  }
}
