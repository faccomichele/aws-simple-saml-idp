variable "tags" {
  description = "Map of tags to assign to resources"
  type        = map(string)
}

variable "idp_entity_id" {
  description = "SAML Identity Provider Entity ID (must be a valid URL)"
  type        = string
  default     = "placeholder"
}

variable "idp_base_url" {
  description = "Base URL for the IdP (used for ACS URL and SSO endpoints)"
  type        = string
  default     = "placeholder"
}

variable "session_duration_seconds" {
  description = "AWS session duration in seconds (900-43200)"
  type        = number
  default     = 3600
}

variable "allowed_aws_accounts" {
  description = "List of AWS account IDs allowed for SSO"
  type        = list(string)
  default     = []
}

variable "saml_provider_name" {
  description = "Name of the SAML provider in target AWS accounts"
  type        = string
  default     = "CentralSAMLIdP"
}

variable "allowed_cors_origins" {
  description = "List of allowed CORS origins for API Gateway. Use ['*'] to allow all origins (not recommended for production)"
  type        = list(string)
  default     = ["*"]
}

variable "allowed_oidc_redirect_uris" {
  description = "List of allowed OIDC redirect URIs for security. If empty, only localhost and https URLs are allowed (development mode)"
  type        = list(string)
  default     = []
}
