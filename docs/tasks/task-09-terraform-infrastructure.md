# Task 9: Terraform Infrastructure

## Objective
Create Terraform configuration for deploying AWS Perimeter Guard with a flexible deployment model using a single boolean variable to control whether to deploy full infrastructure (single/central account) or just an IAM role (target accounts).

## Dependencies
- Task 8: Lambda adapter must be implemented

## Architecture Overview

### Single Account Mode
```
AWS Account (123456789012)
├── Lambda Function (perimeter-guard-scanner)
├── EventBridge Schedule (daily trigger)
└── IAM Role (PerimeterGuardLambdaRole)
    └── Permissions: wafv2:*, elbv2:Describe*, cloudfront:List*, etc.
```

### Multi-Account Mode
```
Central Account (123456789012)
├── Lambda Function (perimeter-guard-scanner)
├── EventBridge Schedule (daily trigger)
└── IAM Role (PerimeterGuardLambdaRole)
    ├── Permissions: wafv2:*, elbv2:Describe*, etc.
    └── Can assume role: arn:aws:iam::*:role/PerimeterGuardScanRole

Target Account 1 (111111111111)
└── IAM Role (PerimeterGuardScanRole)
    ├── Trust: arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole
    └── Permissions: wafv2:*, elbv2:Describe*, etc.

Target Account 2 (222222222222)
└── IAM Role (PerimeterGuardScanRole)
    ├── Trust: arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole
    └── Permissions: wafv2:*, elbv2:Describe*, etc.
```

## Deliverables

### 1. Main Terraform Configuration
**File**: `terraform/main.tf`

```hcl
terraform {
  required_version = ">= 1.5"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Local variables
locals {
  lambda_name      = "perimeter-guard-scanner"
  scan_role_name   = "PerimeterGuardScanRole"
  lambda_role_name = "PerimeterGuardLambdaRole"
  
  # Build Lambda package path
  lambda_package_path = "${path.module}/lambda-package.zip"
}

# ============================================
# Lambda Function + EventBridge + IAM Role
# (Only created when allow_multiaccount_through_iam_role = false)
# ============================================

# Package Lambda code
resource "null_resource" "build_lambda" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  triggers = {
    always_run = timestamp()
  }
  
  provisioner "local-exec" {
    command = <<EOF
      cd ${path.module}/..
      pip install -r requirements.txt -t /tmp/lambda-package/
      cp -r src /tmp/lambda-package/
      cd /tmp/lambda-package
      zip -r ${local.lambda_package_path} .
      rm -rf /tmp/lambda-package
    EOF
  }
}

# IAM Role for Lambda execution
resource "aws_iam_role" "lambda_role" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  name        = local.lambda_role_name
  description = "Execution role for AWS Perimeter Guard Lambda"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
  
  tags = {
    Name    = local.lambda_role_name
    Project = "aws-perimeter-guard"
  }
}

# IAM Policy for Lambda - Local account scanning
resource "aws_iam_role_policy" "lambda_scan_policy" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  name = "PerimeterGuardScanPolicy"
  role = aws_iam_role.lambda_role[0].id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ScanLocalAccount"
        Effect = "Allow"
        Action = [
          "wafv2:ListWebACLs",
          "wafv2:GetWebACLForResource",
          "wafv2:ListResourcesForWebACL",
          "wafv2:GetLoggingConfiguration",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTags",
          "cloudfront:ListDistributions",
          "cloudfront:GetDistribution",
          "apigateway:GET",
          "appsync:ListGraphqlApis",
          "cognito-idp:ListUserPools",
          "apprunner:ListServices",
          "apprunner:DescribeService",
          "ec2:DescribeVerifiedAccessInstances"
        ]
        Resource = "*"
      },
      {
        Sid      = "AssumeRoleInTargetAccounts"
        Effect   = "Allow"
        Action   = "sts:AssumeRole"
        Resource = "arn:aws:iam::*:role/${local.scan_role_name}"
      }
    ]
  })
}

# Attach AWS managed policy for Lambda basic execution
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  role       = aws_iam_role.lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = var.log_retention_days
  
  tags = {
    Name    = "${local.lambda_name}-logs"
    Project = "aws-perimeter-guard"
  }
}

# Lambda Function
resource "aws_lambda_function" "scanner" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  filename         = local.lambda_package_path
  function_name    = local.lambda_name
  role             = aws_iam_role.lambda_role[0].arn
  handler          = "src.adapters.inbound.lambda_handler.handler"
  source_code_hash = filebase64sha256(local.lambda_package_path)
  runtime          = "python3.12"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size
  
  environment {
    variables = {
      SCAN_REGIONS     = join(",", var.scan_regions)
      ASSUME_ROLE_NAME = local.scan_role_name
      TARGET_ACCOUNTS  = var.target_accounts
      OUTPUT_TYPE      = "cloudwatch"
    }
  }
  
  depends_on = [
    null_resource.build_lambda,
    aws_cloudwatch_log_group.lambda_logs
  ]
  
  tags = {
    Name    = local.lambda_name
    Project = "aws-perimeter-guard"
  }
}

# EventBridge Rule for scheduled execution
resource "aws_cloudwatch_event_rule" "scanner_schedule" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  name                = "${local.lambda_name}-schedule"
  description         = "Trigger AWS Perimeter Guard scanner"
  schedule_expression = var.scan_schedule
  
  tags = {
    Name    = "${local.lambda_name}-schedule"
    Project = "aws-perimeter-guard"
  }
}

# EventBridge Target (Lambda)
resource "aws_cloudwatch_event_target" "lambda_target" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  rule      = aws_cloudwatch_event_rule.scanner_schedule[0].name
  target_id = "PerimeterGuardLambda"
  arn       = aws_lambda_function.scanner[0].arn
  
  input = jsonencode({
    scan_type   = "full"
    regions     = var.scan_regions
    output_type = "cloudwatch"
  })
}

# Lambda permission for EventBridge to invoke
resource "aws_lambda_permission" "allow_eventbridge" {
  count = var.allow_multiaccount_through_iam_role ? 0 : 1
  
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scanner_schedule[0].arn
}

# ============================================
# IAM Role for Target Accounts
# (Only created when allow_multiaccount_through_iam_role = true)
# ============================================

# IAM Role for cross-account scanning
resource "aws_iam_role" "scan_role" {
  count = var.allow_multiaccount_through_iam_role ? 1 : 0
  
  name        = local.scan_role_name
  description = "Allows AWS Perimeter Guard Lambda to scan resources and WAF associations"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = var.central_lambda_role_arn
      }
      Action = "sts:AssumeRole"
    }]
  })
  
  tags = {
    Name    = local.scan_role_name
    Project = "aws-perimeter-guard"
  }
}

# IAM Policy for scan role
resource "aws_iam_role_policy" "scan_role_policy" {
  count = var.allow_multiaccount_through_iam_role ? 1 : 0
  
  name = "PerimeterGuardScanPolicy"
  role = aws_iam_role.scan_role[0].id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "wafv2:ListWebACLs",
          "wafv2:GetWebACLForResource",
          "wafv2:ListResourcesForWebACL",
          "wafv2:GetLoggingConfiguration",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTags",
          "cloudfront:ListDistributions",
          "cloudfront:GetDistribution",
          "apigateway:GET",
          "appsync:ListGraphqlApis",
          "cognito-idp:ListUserPools",
          "apprunner:ListServices",
          "apprunner:DescribeService",
          "ec2:DescribeVerifiedAccessInstances"
        ]
        Resource = "*"
      }
    ]
  })
}
```

**Key Points**:
- **Conditional resources**: Uses `count` based on `allow_multiaccount_through_iam_role`
- **No modules, no StackSets**: Flat Terraform structure for simplicity
- **Lambda packaging**: Automated with `null_resource`
- **EventBridge**: Scheduled daily execution
- **Environment variables**: TARGET_ACCOUNTS for multi-account mode

---

### 2. Variables Definition
**File**: `terraform/variables.tf`

```hcl
# ============================================
# Deployment Mode
# ============================================

variable "allow_multiaccount_through_iam_role" {
  description = "If true, only creates IAM role (for target accounts). If false, creates Lambda + EventBridge + IAM role (for central/single account)"
  type        = bool
  default     = false
}

# ============================================
# General Configuration
# ============================================

variable "aws_region" {
  description = "AWS region for Lambda deployment"
  type        = string
  default     = "us-east-1"
}

variable "scan_regions" {
  description = "List of AWS regions to scan (empty list = all enabled regions)"
  type        = list(string)
  default     = ["us-east-1", "us-west-2", "eu-west-1"]
}

variable "scan_schedule" {
  description = "EventBridge schedule expression (rate or cron)"
  type        = string
  default     = "rate(24 hours)"
  
  validation {
    condition     = can(regex("^(rate\\(.*\\)|cron\\(.*\\))$", var.scan_schedule))
    error_message = "Schedule must be a valid EventBridge rate() or cron() expression"
  }
}

# ============================================
# Lambda Configuration
# ============================================

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
  
  validation {
    condition     = var.lambda_timeout >= 60 && var.lambda_timeout <= 900
    error_message = "Timeout must be between 60 and 900 seconds"
  }
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 512
  
  validation {
    condition     = var.lambda_memory_size >= 128 && var.lambda_memory_size <= 10240
    error_message = "Memory size must be between 128 and 10240 MB"
  }
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention period in days"
  type        = number
  default     = 7
  
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Must be a valid CloudWatch Logs retention period"
  }
}

# ============================================
# Multi-Account Configuration
# ============================================

variable "target_accounts" {
  description = "Comma-separated list of target account IDs for multi-account scanning (only used when allow_multiaccount_through_iam_role = false)"
  type        = string
  default     = ""
}

variable "central_lambda_role_arn" {
  description = "ARN of the central Lambda role (required when allow_multiaccount_through_iam_role = true)"
  type        = string
  default     = ""
  
  validation {
    condition     = var.allow_multiaccount_through_iam_role == false || (var.allow_multiaccount_through_iam_role == true && length(var.central_lambda_role_arn) > 0)
    error_message = "central_lambda_role_arn is required when allow_multiaccount_through_iam_role is true"
  }
}
```

---

### 3. Outputs
**File**: `terraform/outputs.tf`

```hcl
# ============================================
# Lambda Outputs (when allow_multiaccount_through_iam_role = false)
# ============================================

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = var.allow_multiaccount_through_iam_role ? null : aws_lambda_function.scanner[0].arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = var.allow_multiaccount_through_iam_role ? null : aws_lambda_function.scanner[0].function_name
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = var.allow_multiaccount_through_iam_role ? null : aws_iam_role.lambda_role[0].arn
}

output "eventbridge_rule_name" {
  description = "Name of the EventBridge rule"
  value       = var.allow_multiaccount_through_iam_role ? null : aws_cloudwatch_event_rule.scanner_schedule[0].name
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group name"
  value       = var.allow_multiaccount_through_iam_role ? null : aws_cloudwatch_log_group.lambda_logs[0].name
}

# ============================================
# IAM Role Outputs (when allow_multiaccount_through_iam_role = true)
# ============================================

output "scan_role_arn" {
  description = "ARN of the scan role (for multi-account target accounts)"
  value       = var.allow_multiaccount_through_iam_role ? aws_iam_role.scan_role[0].arn : null
}

output "scan_role_name" {
  description = "Name of the scan role"
  value       = var.allow_multiaccount_through_iam_role ? aws_iam_role.scan_role[0].name : null
}

# ============================================
# Deployment Mode
# ============================================

output "deployment_mode" {
  description = "Current deployment mode"
  value       = var.allow_multiaccount_through_iam_role ? "target-account" : "central-account"
}
```

---

### 4. Configuration Example
**File**: `terraform/terraform.tfvars.example`

```hcl
# ============================================
# AWS Perimeter Guard - Terraform Configuration
# ============================================
#
# Copy this file to terraform.tfvars and update values
#

# ============================================
# Deployment Mode
# ============================================
# false = Deploy Lambda + EventBridge + IAM role (single account or central account)
# true  = Deploy IAM role only (target account in multi-account setup)
allow_multiaccount_through_iam_role = false

# ============================================
# General Configuration
# ============================================
aws_region = "us-east-1"

# Regions to scan (empty list = all enabled regions)
scan_regions = [
  "us-east-1",
  "us-west-2",
  "eu-west-1"
]

# Schedule: rate(24 hours) or cron(0 8 * * ? *)
scan_schedule = "rate(24 hours)"

# ============================================
# Lambda Configuration (only for central/single account)
# ============================================
lambda_timeout     = 300 # 5 minutes
lambda_memory_size = 512 # MB
log_retention_days = 7   # Days

# ============================================
# Multi-Account Configuration
# ============================================

# For central account: Comma-separated target account IDs
# target_accounts = "111111111111,222222222222,333333333333"

# For target account: ARN of central Lambda role
# central_lambda_role_arn = "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"
```

---

## Deployment Workflows

### Single Account Deployment

**Step 1: Configure**
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
# Set: allow_multiaccount_through_iam_role = false
vim terraform.tfvars
```

**Step 2: Deploy**
```bash
terraform init
terraform plan
terraform apply
```

**What gets created:**
- ✅ Lambda function: `perimeter-guard-scanner`
- ✅ IAM role: `PerimeterGuardLambdaRole`
- ✅ EventBridge rule: Daily trigger
- ✅ CloudWatch Log Group: `/aws/lambda/perimeter-guard-scanner`

**Step 3: Verify**
```bash
# Check Lambda
aws lambda get-function --function-name perimeter-guard-scanner

# Trigger manually
aws lambda invoke \
  --function-name perimeter-guard-scanner \
  --payload '{"scan_type":"full"}' \
  /tmp/response.json

# View logs
aws logs tail /aws/lambda/perimeter-guard-scanner --follow
```

---

### Multi-Account Deployment

**Step 1: Deploy in Central Account**
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
cat > terraform.tfvars <<EOF
allow_multiaccount_through_iam_role = false
aws_region                          = "us-east-1"
scan_schedule                       = "rate(24 hours)"
target_accounts                     = "111111111111,222222222222"
scan_regions                        = ["us-east-1", "us-west-2"]
EOF

terraform init
terraform apply
```

**Capture Output:**
```bash
# Note the Lambda role ARN for next step
terraform output lambda_role_arn
# Output: arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole
```

---

**Step 2: Deploy in Target Account 1**
```bash
# Switch to target account credentials
export AWS_PROFILE=target-account-1

cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars
cat > terraform.tfvars <<EOF
allow_multiaccount_through_iam_role = true
central_lambda_role_arn             = "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"
EOF

terraform init
terraform apply
```

**What gets created:**
- ✅ IAM role: `PerimeterGuardScanRole`
- ✅ Trust policy: Trusts central Lambda role

---

**Step 3: Repeat for Each Target Account**
```bash
# Switch to target account 2
export AWS_PROFILE=target-account-2

# Edit terraform.tfvars (same as Step 2)
terraform init
terraform apply

# Repeat for additional accounts...
```

---

**Step 4: Verify Multi-Account Setup**
```bash
# Switch back to central account
export AWS_PROFILE=central-account

# Test manual invocation
aws lambda invoke \
  --function-name perimeter-guard-scanner \
  --payload '{"scan_type":"full"}' \
  /tmp/response.json

# Check logs for all accounts scanned
aws logs tail /aws/lambda/perimeter-guard-scanner --follow
```

---

## Lambda Implementation Details

### Multi-Account Scanning Logic

```python
# src/adapters/inbound/lambda_handler.py

import os
import boto3
from typing import List

def handler(event, context):
    """Lambda handler for AWS Perimeter Guard scanner."""
    
    # Get configuration from environment
    scan_regions = os.getenv('SCAN_REGIONS', '').split(',')
    assume_role_name = os.getenv('ASSUME_ROLE_NAME', 'PerimeterGuardScanRole')
    target_accounts = os.getenv('TARGET_ACCOUNTS', '').split(',')
    
    results = []
    
    # Scan local account
    local_result = scan_account(
        account_id=context.invoked_function_arn.split(':')[4],
        regions=scan_regions
    )
    results.append(local_result)
    
    # Scan target accounts (if configured)
    if target_accounts and target_accounts[0]:
        for account_id in target_accounts:
            account_id = account_id.strip()
            if not account_id:
                continue
            
            # Assume role in target account
            try:
                session = assume_role(account_id, assume_role_name)
                result = scan_account(
                    account_id=account_id,
                    regions=scan_regions,
                    session=session
                )
                results.append(result)
            except Exception as e:
                print(f"Error scanning account {account_id}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': {
            'accounts_scanned': len(results),
            'results': results
        }
    }

def assume_role(account_id: str, role_name: str):
    """Assume role in target account."""
    sts = boto3.client('sts')
    response = sts.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{role_name}",
        RoleSessionName="PerimeterGuardScan"
    )
    
    return boto3.Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken']
    )
```

---

## Troubleshooting

### Lambda Package Build Fails
```bash
# Manual build
cd /path/to/project
pip install -r requirements.txt -t /tmp/lambda-package/
cp -r src /tmp/lambda-package/
cd /tmp/lambda-package
zip -r ../lambda-package.zip .

# Copy to terraform directory
mv ../lambda-package.zip terraform/

# Then run terraform
cd terraform
terraform apply
```

### Assume Role Access Denied
```bash
# Test assume role manually
aws sts assume-role \
  --role-arn arn:aws:iam::TARGET_ACCOUNT:role/PerimeterGuardScanRole \
  --role-session-name test

# Check trust policy
aws iam get-role \
  --role-name PerimeterGuardScanRole \
  --query 'Role.AssumeRolePolicyDocument'
```

### Lambda Timeout
```bash
# Increase timeout in terraform.tfvars
lambda_timeout = 600  # 10 minutes

# Apply changes
terraform apply
```

### Terraform State Issues
```bash
# View current state
terraform show

# List resources
terraform state list

# Remove resource from state (if needed)
terraform state rm aws_lambda_function.scanner[0]
```

---

## Cost Estimation

**Single Account**:
- Lambda: ~$0.10/month (512MB, 2min/day)
- CloudWatch Logs: ~$1/month
- **Total: ~$1-2/month**

**Multi-Account (10 accounts)**:
- Lambda: ~$0.50/month (512MB, 20min/day)
- CloudWatch Logs: ~$3/month
- **Total: ~$3-5/month**

---

## Deployment Patterns Comparison

| Feature | Single Account | Multi-Account |
|---------|---------------|---------------|
| Lambda Deployment | Central account | Central account |
| IAM Role Deployment | Same as Lambda | Each target account |
| Account Discovery | N/A | Manual via TARGET_ACCOUNTS |
| Terraform Applies | 1 | 1 + N (N = number of target accounts) |
| Complexity | Low | Medium |
| Setup Time | 5 minutes | 10-15 minutes |

---

## Next Steps

After deployment:
1. Monitor CloudWatch Logs for scan results
2. Set up CloudWatch Insights queries for compliance reporting
3. Optionally add SNS notifications for non-compliant resources
4. Review Task 10 for comprehensive documentation
5. Consider adding CloudWatch Dashboard for visualization
