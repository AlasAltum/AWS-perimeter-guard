# ============================================
# Central Account Outputs
# ============================================

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.lambda_function.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.lambda_function.lambda_function_name
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.lambda_function.lambda_role_arn
}

output "scheduler_schedule_name" {
  description = "Name of the EventBridge Scheduler schedule"
  value       = aws_scheduler_schedule.scanner_schedule.name
}

output "scheduler_schedule_arn" {
  description = "ARN of the EventBridge Scheduler schedule"
  value       = aws_scheduler_schedule.scanner_schedule.arn
}

output "scheduler_role_arn" {
  description = "ARN of the Scheduler IAM role"
  value       = aws_iam_role.scheduler_role.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group name"
  value       = module.lambda_function.lambda_cloudwatch_log_group_name
}

output "central_account_id" {
  description = "Central account ID where Lambda is deployed"
  value       = local.central_account_id
}

# ============================================
# Multi-Account Configuration
# ============================================

output "scan_role_name" {
  description = "Name of the IAM role that must be created in target accounts"
  value       = var.scan_role_name
}

output "scan_role_external_id" {
  description = "External ID used for assuming scan roles"
  value       = var.external_id
  sensitive   = true
}

# ============================================
# Deployment Summary
# ============================================

output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    central_account = local.central_account_id
    target_accounts = length(var.target_accounts) > 0 ? join(", ", var.target_accounts) : "None configured (single account mode)"
    scan_role_name  = var.scan_role_name
    scan_schedule   = var.scan_schedule
    scan_regions    = join(", ", var.scan_regions)
  }
}

output "manual_deployment_instructions" {
  description = "Instructions for manually deploying scan roles in target accounts"
  value = <<-EOT
    To enable scanning in target accounts, use Terragrunt:
    
    1. Switch to target account credentials
    2. cd infrastructure/terragrunt/scanned_account_<env>
    3. terragrunt init
    4. terragrunt apply
    
    Or deploy the scan role module manually with Terraform:
    
    1. cd infrastructure/modules/scan-role
    2. terraform init
    3. terraform apply -var="central_account_id=${local.central_account_id}" -var="external_id=${var.external_id}"
  EOT
}
