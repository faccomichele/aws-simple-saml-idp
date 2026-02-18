output "api_gateway_url" {
  description = "API Gateway endpoint URL for SAML endpoints"
  value       = aws_apigatewayv2_stage.saml.invoke_url
}

output "login_page_url" {
  description = "URL to access the login page (CloudFront recommended for HTTPS access)"
  value       = "https://${aws_cloudfront_distribution.login_page.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.login_page.id
}

output "website_bucket_name" {
  description = "S3 bucket name for login page"
  value       = aws_s3_bucket.login_page.id
}
