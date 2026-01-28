# ============================================
# Central Account - Lambda Deployment
# ============================================
# This deploys the Lambda function that scans multiple AWS accounts

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../modules/scan-lambda-scheduler"
}

locals {
  # Load root configuration
  root_config = read_terragrunt_config(find_in_parent_folders("root.hcl"))

  # Extract shared values
  central_account_id = local.root_config.locals.central_account_id
  scan_role_name     = local.root_config.locals.scan_role_name
  external_id        = local.root_config.locals.external_id
  common_tags        = local.root_config.locals.common_tags
}

inputs = {
  # General Configuration
  aws_region = "us-east-1"

  # Regions to scan (empty list = all enabled regions)
  scan_regions = [
    "us-east-1",
    "us-west-2",
    "eu-west-1"
  ]

  # Schedule: rate(24 hours) or cron(0 8 * * ? *)
  scan_schedule = "rate(24 hours)"

  # Lambda Configuration
  lambda_timeout     = 300 # 5 minutes
  lambda_memory_size = 256 # MB
  log_retention_days = 7   # Days

  # Multi-Account Configuration
  # Specify individual target account IDs to scan
  # Leave empty [] to scan only the central account
  target_accounts = [
    "111111111111",
    "222222222222",
    "333333333333",
  ]

  # Inherited from root configuration
  scan_role_name = local.scan_role_name
  external_id    = local.external_id

  # Source directory for Lambda
  lambda_source_dir = "${get_parent_terragrunt_dir()}/../../src"

  common_tags = merge(local.common_tags,
    {
      Environment = "prod",
      ManagedBy   = "Terragrunt"
    }
  )
}
