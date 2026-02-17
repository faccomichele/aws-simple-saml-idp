terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
    http = {
      source = "hashicorp/http"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = local.aws_region

  default_tags {
    tags = var.tags
  }
}
