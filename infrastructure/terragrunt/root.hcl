# ============================================
# AWS Perimeter Guard - Root Terragrunt Configuration
# ============================================
# This file contains shared configuration for all child modules

locals {
  # Common configuration
  aws_region = "us-east-1"

  # Security configuration - shared across all accounts
  central_account_id = "111111111111" # The account where Lambda runs
  scan_role_name     = "ARMOR-WAF-checker-role"
  external_id        = "AN_EXTERNAL_ID_PLEASE_MODIFY_THIS_AND_SET_SOMETHING_SECURE" # KEEP SECRET

  # Common tags applied to all resources
  common_tags = {
    Project   = "AWS-Perimeter-Guard"
    ManagedBy = "Terragrunt"
  }
}

# ============================================
# Remote State Configuration
# ============================================
remote_state {
  backend = "s3"

  config = {
    bucket         = "armor-perimeter-guard-${get_aws_account_id()}-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = "armor-perimeter-guard-${get_aws_account_id()}-terraform-locks"
  }

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# ============================================
# Provider Configuration
# ============================================
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
  
  default_tags {
    tags = ${jsonencode(local.common_tags)}
  }
}
EOF
}

# ============================================
# Terraform Configuration
# ============================================
generate "versions" {
  path      = "versions_override.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.5"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}
EOF
}
