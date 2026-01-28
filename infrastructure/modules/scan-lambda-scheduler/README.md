# AWS Perimeter Guard - Terraform Infrastructure

This Terraform configuration deploys the AWS Perimeter Guard scanner with multi-account support.

## Architecture

```
Central Account (where Lambda is deployed)
├── Lambda Function (perimeter-guard-scanner)
├── EventBridge Schedule (daily trigger)
└── IAM Role (PerimeterGuardLambdaRole)
    ├── Permissions: WAF scanning in local account
    └── Can assume: Scan roles in target accounts

Target Accounts (manually deployed)
└── IAM Role (configurable name)
    ├── Trust: Central account root + External ID
    └── Permissions: WAF scanning (read-only)
```

## Prerequisites

### 1. Central Account Setup

You need AWS credentials for the **central account** where Lambda will be deployed.

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."

# Option 2: AWS CLI profile
export AWS_PROFILE=my-central-account

# Option 3: AWS SSO
aws sso login --profile my-central-account
```

### 2. Target Account List

Collect the 12-digit account IDs for all accounts you want to scan.

## Deployment

### Step 1: Configure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars
```

**Required configuration:**
```hcl
# Target accounts to scan
target_accounts = [
  "111111111111",
  "222222222222",
  "333333333333"
]

# Security: Use a random value (generate with: uuidgen or openssl rand -base64 32)
external_id = "your-random-external-id-min-16-chars"

# Name of the role to assume in target accounts
scan_role_name = "YourScanRoleName"
```

### Step 2: Deploy Central Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

**This creates:**
- Lambda function: `perimeter-guard-scanner`
- IAM role: `PerimeterGuardLambdaRole`
- EventBridge rule: Daily trigger
- CloudWatch Log Group

### Step 3: Note the Outputs

```bash
terraform output central_account_id
terraform output scan_role_external_id
terraform output scan_role_name
```

## Target Account Setup

After deploying the central account, deploy the scan role to each target account.

### Option 1: Using the Terraform Module

**In each target account:**

```bash
cd terraform/modules/scan-role

cat > terraform.tfvars <<EOF
central_account_id = "123456789012"  # From central account output
external_id        = "your-external-id"  # Must match central account
role_name          = "YourScanRoleName"
EOF

terraform init
terraform apply
```

### Option 2: Using AWS CLI

```bash
# Create trust policy
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::CENTRAL_ACCOUNT_ID:root"
    },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "sts:ExternalId": "YOUR_EXTERNAL_ID"
      }
    }
  }]
}
EOF

# Create the role
aws iam create-role \
  --role-name YourScanRoleName \
  --assume-role-policy-document file://trust-policy.json

# Attach SecurityAudit policy for scanning permissions
aws iam attach-role-policy \
  --role-name YourScanRoleName \
  --policy-arn arn:aws:iam::aws:policy/SecurityAudit
```

## Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `target_accounts` | List of AWS account IDs to scan | `["111111111111", "222222222222"]` |
| `external_id` | Security token (min 16 chars) | `"abc123xyz..."` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region for Lambda | `us-east-1` |
| `scan_regions` | Regions to scan | `["us-east-1", "us-west-2", "eu-west-1"]` |
| `scan_schedule` | EventBridge schedule | `rate(24 hours)` |
| `scan_role_name` | Role name in target accounts | `PerimeterGuardScanRole` |
| `lambda_timeout` | Lambda timeout (seconds) | `300` |
| `lambda_memory_size` | Lambda memory (MB) | `256` |
| `log_retention_days` | CloudWatch log retention | `7` |

## How It Works

1. **EventBridge** triggers the Lambda function on schedule
2. **Lambda** reads `TARGET_ACCOUNTS` environment variable
3. For each account, Lambda **assumes** the scan role using External ID
4. Lambda **scans** WAF associations in that account
5. Results are logged to **CloudWatch**

### Security

- **External ID**: Prevents confused deputy attacks
- **Least privilege**: Scan roles only have read permissions
- **Audit logging**: All assume role operations logged in CloudTrail

## Troubleshooting

### Lambda can't assume role

```
AccessDenied: User is not authorized to perform: sts:AssumeRole
```

**Check:**
1. Role exists in target account
2. External ID matches exactly
3. Role name matches exactly
4. Trust policy allows central account

**Test manually:**
```bash
aws sts assume-role \
  --role-arn arn:aws:iam::TARGET_ACCOUNT:role/YourScanRoleName \
  --role-session-name test \
  --external-id YOUR_EXTERNAL_ID
```

### Lambda timeout

Increase timeout in `terraform.tfvars`:
```hcl
lambda_timeout = 600  # 10 minutes
```

## Cleanup

### Central Account
```bash
cd terraform
terraform destroy
```

### Target Accounts
```bash
cd terraform/modules/scan-role
terraform destroy
```

Or via AWS CLI:
```bash
aws iam detach-role-policy --role-name YourScanRoleName --policy-arn arn:aws:iam::aws:policy/SecurityAudit
aws iam delete-role --role-name YourScanRoleName
```
