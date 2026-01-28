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

### 1. StackSet IAM Role Module
**File**: `terraform/modules/iam-stackset/main.tf`

```hcl
# Module for deploying IAM role via StackSet to all Organization accounts
variable "management_account_id" {
  description = "AWS Management/Master account ID"
  type        = string
}

variable "lambda_role_name" {
  description = "Name of the Lambda execution role in management account"
  type        = string
  default     = "PerimeterGuardLambdaRole"
}

variable "scan_role_name" {
  description = "Name of the role to create in member accounts"
  type        = string
  default     = "PerimeterGuardScanRole"
}

variable "organization_id" {
  description = "AWS Organization ID (o-xxxxxxxxxx)"
  type        = string
}

# CloudFormation template for the IAM role
resource "aws_cloudformation_stack_set" "scan_role" {
  name             = "perimeter-guard-scan-role"
  description      = "Deploys PerimeterGuardScanRole to all accounts"
  permission_model = "SERVICE_MANAGED"  # Auto-deployment
  
  capabilities = ["CAPABILITY_NAMED_IAM"]
  
  auto_deployment {
    enabled                          = true
    retain_stacks_on_account_removal = false
  }
  
  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description              = "IAM role for AWS Perimeter Guard scanning"
    
    Resources = {
      PerimeterGuardScanRole = {
        Type = "AWS::IAM::Role"
        Properties = {
          RoleName = var.scan_role_name
          Description = "Allows Perimeter Guard Lambda to scan resources and WAF associations"
          
          AssumeRolePolicyDocument = {
            Version = "2012-10-17"
            Statement = [{
              Effect = "Allow"
              Principal = {
                AWS = "arn:aws:iam::${var.management_account_id}:role/${var.lambda_role_name}"
              }
              Action = "sts:AssumeRole"
              Condition = {
                StringEquals = {
                  "sts:ExternalId" = "perimeter-guard-scanner"
                }
              }
            }]
          }
          
          ManagedPolicyArns = [
            "arn:aws:iam::aws:policy/SecurityAudit"  # Read-only access
          ]
          
          Policies = [{
            PolicyName = "PerimeterGuardScanPolicy"
            PolicyDocument = {
              Version = "2012-10-17"
              Statement = [
                {
                  Sid    = "WAFv2ReadAccess"
                  Effect = "Allow"
                  Action = [
                    "wafv2:ListWebACLs",
                    "wafv2:GetWebACLForResource",
                    "wafv2:ListResourcesForWebACL",
                    "wafv2:GetLoggingConfiguration"
                  ]
                  Resource = "*"
                },
                {
                  Sid    = "ResourceDiscovery"
                  Effect = "Allow"
                  Action = [
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
            }
          }]
        }
      }
    }
    
    Outputs = {
      RoleArn = {
        Value = { "Fn::GetAtt" = ["PerimeterGuardScanRole", "Arn"] }
        Export = { Name = "PerimeterGuardScanRoleArn" }
      }
    }
  })
}

# Deploy to all accounts in Organization
resource "aws_cloudformation_stack_set_instance" "all_accounts" {
  stack_set_name = aws_cloudformation_stack_set.scan_role.name
  
  deployment_targets {
    organizational_unit_ids = [var.organization_id]  # Root OU = all accounts
  }
  
  operation_preferences {
    failure_tolerance_count = 1
    max_concurrent_count    = 10
    region_concurrency_type = "PARALLEL"
  }
}

output "stackset_id" {
  value       = aws_cloudformation_stack_set.scan_role.id
  description = "StackSet ID for tracking deployment"
}

output "scan_role_name" {
  value       = var.scan_role_name
  description = "Name of role created in member accounts"
}
```

**Key Points**:
- **SERVICE_MANAGED**: Automatically deploys to new accounts when they join
- **auto_deployment**: No manual intervention for new accounts
- **External ID**: Adds security layer for cross-account assume role
- **SecurityAudit policy**: Provides baseline read-only permissions
- **Parallel deployment**: Deploys to up to 10 accounts simultaneously

---

### 2. Organization Environment
**File**: `terraform/environments/organization/main.tf`

```hcl
terraform {
  required_version = ">= 1.5"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Optional: S3 backend for state
  # backend "s3" {
  #   bucket = "my-terraform-state"
  #   key    = "perimeter-guard/organization.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
  
  # Must be run from management account
  assume_role {
    role_arn = var.management_role_arn  # Optional if running with mgmt creds
  }
}

# Local variables
locals {
  lambda_name = "perimeter-guard-scanner"
  scan_role_name = "PerimeterGuardScanRole"
  
  # Build Lambda package
  lambda_package_path = "${path.module}/../../lambda-package.zip"
}

# Package Lambda code
resource "null_resource" "build_lambda" {
  triggers = {
    always_run = timestamp()
  }
  
  provisioner "local-exec" {
    command = <<EOF
      cd ${path.module}/../../../
      pip install -r requirements.txt -t /tmp/lambda-package/
      cp -r src /tmp/lambda-package/
      cd /tmp/lambda-package
      zip -r ${local.lambda_package_path} .
    EOF
  }
}

# Deploy StackSet for cross-account roles
module "iam_stackset" {
  source = "../../modules/iam-stackset"
  
  management_account_id = var.management_account_id
  organization_id       = var.organization_id
  lambda_role_name      = "${local.lambda_name}-role"
  scan_role_name        = local.scan_role_name
}

# Lambda function module
module "scanner_lambda" {
  source = "../../modules/scanner-lambda"
  
  function_name         = local.lambda_name
  lambda_package_path   = local.lambda_package_path
  scan_role_name        = local.scan_role_name
  organization_scan     = true
  scan_regions          = var.scan_regions
  
  depends_on = [
    null_resource.build_lambda,
    module.iam_stackset
  ]
}

# EventBridge schedule
module "eventbridge_schedule" {
  source = "../../modules/eventbridge-schedule"
  
  schedule_name         = "${local.lambda_name}-schedule"
  schedule_expression   = var.scan_schedule
  lambda_function_arn   = module.scanner_lambda.function_arn
  lambda_function_name  = module.scanner_lambda.function_name
  
  event_payload = jsonencode({
    scan_type          = "full"
    organization_scan  = true
    regions            = var.scan_regions
    output_type        = "cloudwatch"
  })
}

# Outputs
output "lambda_function_arn" {
  value       = module.scanner_lambda.function_arn
  description = "ARN of the scanner Lambda function"
}

output "lambda_function_name" {
  value       = module.scanner_lambda.function_name
  description = "Name of the scanner Lambda function"
}

output "stackset_deployment_status" {
  value       = "Check AWS Console CloudFormation StackSets"
  description = "StackSet deployment status"
}
```

---

### 3. Centralized Configuration
**File**: `terraform/environments/organization/terraform.tfvars.example`

```hcl
# ============================================
# AWS Perimeter Guard - Organization Config
# ============================================
#
# Copy this file to terraform.tfvars and update values
# This is the ONLY file you need to configure!

# Required: Your AWS Organization details
management_account_id = "123456789012"         # Management account ID
organization_id       = "o-abc123xyz"          # Organization ID (starts with o-)

# Optional: AWS region for Lambda deployment
aws_region = "us-east-1"

# Optional: Regions to scan (empty = all enabled regions)
scan_regions = [
  "us-east-1",
  "us-west-2",
  "eu-west-1"
]

# Optional: Scan schedule (EventBridge expression)
# Examples:
#   "rate(24 hours)"          - Daily
#   "rate(12 hours)"          - Twice daily
#   "cron(0 8 * * ? *)"       - Daily at 8:00 AM UTC
scan_schedule = "rate(24 hours)"

# Optional: Notifications (future enhancement)
# slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
# sns_topic_arn     = "arn:aws:sns:us-east-1:123456789012:perimeter-alerts"
```

**Key Points**:
- **Single file configuration**: All settings in one place
- **Commented examples**: Clear guidance for users
- **Sensible defaults**: Works out-of-box for most cases
- **Optional overrides**: Advanced users can customize

---

### 4. Variables Definition
**File**: `terraform/environments/organization/variables.tf`

```hcl
variable "management_account_id" {
  description = "AWS Management/Master account ID where Lambda will run"
  type        = string
  
  validation {
    condition     = can(regex("^\\d{12}$", var.management_account_id))
    error_message = "Management account ID must be a 12-digit number"
  }
}

variable "organization_id" {
  description = "AWS Organization ID (format: o-xxxxxxxxxx)"
  type        = string
  
  validation {
    condition     = can(regex("^o-[a-z0-9]{10,32}$", var.organization_id))
    error_message = "Organization ID must start with 'o-' followed by alphanumeric characters"
  }
}

variable "aws_region" {
  description = "AWS region for Lambda deployment"
  type        = string
  default     = "us-east-1"
}

variable "scan_regions" {
  description = "List of regions to scan (empty = all enabled regions)"
  type        = list(string)
  default     = []
}

variable "scan_schedule" {
  description = "EventBridge schedule expression"
  type        = string
  default     = "rate(24 hours)"
  
  validation {
    condition     = can(regex("^(rate\\(.*\\)|cron\\(.*\\))$", var.scan_schedule))
    error_message = "Schedule must be a valid EventBridge rate() or cron() expression"
  }
}

variable "management_role_arn" {
  description = "Optional IAM role ARN to assume in management account"
  type        = string
  default     = null
}
```

**Key Points**:
- **Input validation**: Prevents common configuration errors
- **Type safety**: Terraform validates types at plan time
- **Defaults**: Minimizes required configuration

---

## Deployment Workflow

### Step 1: Prerequisites
```bash
# Ensure you're authenticated to management account
aws sts get-caller-identity

# Verify Organizations access
aws organizations describe-organization
```

### Step 2: Configure
```bash
cd terraform/environments/organization
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
vim terraform.tfvars
```

### Step 3: Deploy
```bash
# Initialize Terraform
terraform init

# Review plan
terraform plan

# Apply infrastructure
terraform apply
```

**What gets created:**
1. ✅ StackSet: `perimeter-guard-scan-role` (deploys to all accounts)
2. ✅ Lambda: `perimeter-guard-scanner` (management account)
3. ✅ IAM Role: `PerimeterGuardLambdaRole` (management account)
4. ✅ EventBridge Rule: Daily trigger
5. ✅ CloudWatch Log Group: `/aws/lambda/perimeter-guard-scanner`
6. ✅ IAM Role: `PerimeterGuardScanRole` (all member accounts via StackSet)

### Step 4: Verify
```bash
# Check StackSet deployment status
aws cloudformation describe-stack-set \
  --stack-set-name perimeter-guard-scan-role

# Check StackSet instances (per-account deployments)
aws cloudformation list-stack-instances \
  --stack-set-name perimeter-guard-scan-role

# Trigger manual scan
aws lambda invoke \
  --function-name perimeter-guard-scanner \
  --payload '{"scan_type":"full"}' \
  /tmp/response.json

# View logs
aws logs tail /aws/lambda/perimeter-guard-scanner --follow
```

---

## Multi-Account Scanning Flow

```python
# Pseudocode of what Lambda does
def lambda_handler(event, context):
    # 1. Get AWS Organizations client (management account)
    org_client = boto3.client('organizations')
    
    # 2. List all accounts
    accounts = org_client.list_accounts()['Accounts']
    
    # 3. For each account
    for account in accounts:
        if account['Status'] != 'ACTIVE':
            continue
        
        # 4. Assume role in member account
        sts_client = boto3.client('sts')
        assumed_role = sts_client.assume_role(
            RoleArn=f"arn:aws:iam::{account['Id']}:role/PerimeterGuardScanRole",
            RoleSessionName="PerimeterGuardScan",
            ExternalId="perimeter-guard-scanner"
        )
        
        # 5. Create session with assumed credentials
        session = boto3.Session(
            aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
            aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
            aws_session_token=assumed_role['Credentials']['SessionToken']
        )
        
        # 6. Scan resources in this account
        scan_result = scanner_service.scan_account(
            account_id=account['Id'],
            session=session,
            regions=scan_regions
        )
        
        # 7. Export results (CloudWatch Logs)
        logger.info("Scan complete", extra={
            "account_id": account['Id'],
            "total_resources": scan_result.total_resources,
            "compliant": scan_result.compliant_resources
        })
```

---

## Advanced Configuration

### Enable Specific OUs Only
```hcl
# In iam-stackset module, replace organization_id with:
deployment_targets {
  organizational_unit_ids = [
    "ou-xxxx-11111111",  # Production OU
    "ou-xxxx-22222222"   # Development OU
  ]
}
```

### Add SNS Notifications
```hcl
# Add to scanner-lambda module
resource "aws_sns_topic" "alerts" {
  name = "perimeter-guard-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# Update Lambda environment
environment {
  variables = {
    SNS_TOPIC_ARN = aws_sns_topic.alerts.arn
  }
}
```

### Multi-Region Lambda Deployment
```hcl
# Deploy Lambda in multiple regions for lower latency
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

provider "aws" {
  alias  = "eu_west_1"
  region = "eu-west-1"
}

module "scanner_us" {
  providers = { aws = aws.us_east_1 }
  source    = "../../modules/scanner-lambda"
  # ...
}

module "scanner_eu" {
  providers = { aws = aws.eu_west_1 }
  source    = "../../modules/scanner-lambda"
  # ...
}
```

---

## Troubleshooting

### StackSet Deployment Failures
```bash
# Check failed instances
aws cloudformation list-stack-instances \
  --stack-set-name perimeter-guard-scan-role \
  --stack-instance-filters Key=STATUS,Values=OUTDATED

# View failure reason
aws cloudformation describe-stack-instance \
  --stack-set-name perimeter-guard-scan-role \
  --stack-instance-account 123456789012 \
  --stack-instance-region us-east-1
```

### Assume Role Issues
```bash
# Test assume role manually
aws sts assume-role \
  --role-arn arn:aws:iam::MEMBER_ACCOUNT:role/PerimeterGuardScanRole \
  --role-session-name test \
  --external-id perimeter-guard-scanner
```

---

## Cost Estimation

**For 50 accounts, scanning daily:**
- Lambda: ~$0.20/month (128MB, 2min/scan)
- CloudWatch Logs: ~$5/month (assuming 1GB/month)
- StackSets: $0 (no charge)
- **Total: ~$5-10/month**

---

## Next Steps
After deployment, proceed to Task 10 for documentation refinement and user guides.
