output "api_gateway_url" {
  description = "API Gateway endpoint URL for SAML endpoints"
  value       = aws_apigatewayv2_stage.saml.invoke_url
}

output "login_page_url" {
  description = "URL to access the login page (CloudFront recommended for HTTPS access)"
  value       = "https://${aws_cloudfront_distribution.login_page.domain_name}/index.html"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.login_page.id
}

output "website_bucket_name" {
  description = "S3 bucket name for login page"
  value       = aws_s3_bucket.login_page.id
}

output "oidc_discovery_url" {
  description = "OIDC Discovery URL (OpenID Configuration)"
  value       = "${aws_apigatewayv2_stage.saml.invoke_url}/.well-known/openid-configuration"
}

output "oidc_authorization_endpoint" {
  description = "OIDC Authorization Endpoint"
  value       = "${aws_apigatewayv2_stage.saml.invoke_url}/oauth2/authorize"
}

output "oidc_token_endpoint" {
  description = "OIDC Token Endpoint"
  value       = "${aws_apigatewayv2_stage.saml.invoke_url}/oauth2/token"
}

output "oidc_userinfo_endpoint" {
  description = "OIDC UserInfo Endpoint"
  value       = "${aws_apigatewayv2_stage.saml.invoke_url}/oauth2/userinfo"
}

output "oidc_jwks_uri" {
  description = "OIDC JWKS URI (JSON Web Key Set)"
  value       = "${aws_apigatewayv2_stage.saml.invoke_url}/oauth2/jwks"
}
