# ============================================
# Scanned Account - IAM Role Deployment
# ============================================
# This deploys the IAM role that allows the central Lambda to scan this account

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../modules/scan-role"
}

locals {
  # Load root configuration
  root_config = read_terragrunt_config(find_in_parent_folders("root.hcl"))

  # Extract shared values from root
  central_account_id = local.root_config.locals.central_account_id
  scan_role_name     = local.root_config.locals.scan_role_name
  external_id        = local.root_config.locals.external_id
  common_tags        = local.root_config.locals.common_tags
}

inputs = {
  # Inherited from root configuration
  central_account_id = local.central_account_id
  role_name          = local.scan_role_name
  external_id        = local.external_id
  common_tags = merge(local.common_tags,
    {
      Environment = "prod",
    }
  )
}
