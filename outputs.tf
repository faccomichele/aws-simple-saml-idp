output "api_gateway_url" {
  description = "API Gateway endpoint URL for SAML endpoints"
  value       = aws_ssm_parameter.api_gateway_url.name
}

output "login_page_url" {
  description = "URL to access the login page (CloudFront recommended for HTTPS access)"
  value       = aws_ssm_parameter.login_page_url.name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_ssm_parameter.cloudfront_distribution_id.name
}

output "website_bucket_name" {
  description = "S3 bucket name for login page"
  value       = aws_ssm_parameter.website_bucket_name.name
}
