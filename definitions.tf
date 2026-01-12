locals {
  environment         = split("_", terraform.workspace)[0]
  aws_region          = split("_", terraform.workspace)[1]
  project_name        = var.tags["Project"] != null ? var.tags["Project"] : "unknown"
  idp_entity_id       = var.idp_entity_id == "placeholder" ? "UPDATE both idp_entity_id and idp_base_url after initial deployment" : var.idp_entity_id
  log_retention_days  = local.environment == "dev" ? 7 : 30
}
