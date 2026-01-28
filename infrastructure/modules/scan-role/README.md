# Scan Role Module

This Terraform module creates an IAM role in target accounts that allows the central account's Lambda function to scan for WAF associations.

## Usage

```hcl
module "scan_role" {
  source = "./modules/scan-role"
  
  central_account_id = "123456789012"  # Central account where Lambda runs
  role_name          = "PerimeterGuardScanRole"
  external_id        = "perimeter-guard-scanner"
}
```

## Security Features

- **Restricted trust policy**: Only the central account can assume this role
- **External ID**: Prevents confused deputy attacks
- **Least privilege**: Only permissions needed for WAF scanning
- **Read-only**: No write permissions granted

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| central_account_id | AWS account ID of central account | string | - | yes |
| role_name | Name of IAM role | string | PerimeterGuardScanRole | no |
| external_id | External ID for security | string | perimeter-guard-scanner | no |

## Outputs

| Name | Description |
|------|-------------|
| role_arn | ARN of the created IAM role |
| role_name | Name of the IAM role |
| external_id | External ID for assuming role |
