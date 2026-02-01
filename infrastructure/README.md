# AWS Perimeter Guard - Infrastructure

This directory contains Terraform modules and Terragrunt configurations for deploying AWS Perimeter Guard across multiple AWS accounts using a lambda triggered by a scheduler periodically.

## Directory Structure

```
infrastructure/
├── modules/                          # Terraform modules
│   ├── scan-lambda-scheduler/        # Central account: Lambda + EventBridge
│   └── scan-role/                    # Scanned accounts: IAM role
└── terragrunt/                       # Terragrunt configurations
    ├── root.hcl                      # Shared configuration
    ├── central_account/              # Deploy Lambda here
    ├── scanned_account_dev1/         # Example: dev account
    └── scanned_account_prod1/        # Example: prod account
```

## Prerequisites

- Terraform >= 1.5
- Terragrunt >= 0.50
- AWS CLI configured with appropriate credentials
- S3 bucket and DynamoDB table for remote state (created automatically per account)

## State Management

**Each AWS account gets its own isolated state.** The remote state configuration uses:

- **S3 Bucket**: `armor-perimeter-guard-<ACCOUNT_ID>-terraform-state`
- **DynamoDB Table**: `armor-perimeter-guard-<ACCOUNT_ID>-terraform-locks`
- **State Key**: `<environment_folder>/terraform.tfstate`

This means:
- Central account state: `armor-perimeter-guard-111111111111-terraform-state/central_account/terraform.tfstate`
- Dev account state: `armor-perimeter-guard-222222222222-terraform-state/scanned_account_dev1/terraform.tfstate`
- Prod account state: `armor-perimeter-guard-333333333333-terraform-state/scanned_account_prod1/terraform.tfstate`

**No cross-account state access is required.** Each account manages its own state independently.

## Deployment Order

Deploy in this order:

1. **Central Account** - Deploy Lambda function and EventBridge scheduler
2. **Scanned Accounts** - Deploy IAM roles in each account to be scanned

The Lambda in the central account assumes roles in scanned accounts. The roles must exist before the Lambda can scan those accounts.

## Step-by-Step Deployment

### 1. Configure Root Settings

Edit `terragrunt/root.hcl` and set:

```hcl
locals {
  central_account_id = "YOUR_CENTRAL_ACCOUNT_ID"  # Where Lambda runs
  scan_role_name     = "ARMOR-WAF-checker-role"   # Role name (same in all accounts)
  external_id        = "GENERATE_A_SECURE_VALUE"  # uuidgen or openssl rand -base64 32. Important to avoid confused deputy attacks
}
```

**IMPORTANT:** The `external_id` must be kept secret and must match in all accounts.

### 2. Deploy Central Account

1) Edit terragrunt.hcl to set target_accounts list

```bash
# Set credentials for the CENTRAL account
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-east-1
# Or use: aws configure / environment variables / SSO
# Navigate to central account config
cd infrastructure/terragrunt/central_account

# Deploy
terragrunt init
terragrunt plan
terragrunt apply
```

### 3. Deploy Scanned Accounts

In this case, most probably you will not need to modify any terragrunt file. 
For **each** account you want to scan:

```bash
# Set credentials for the TARGET account (not central!)
export AWS_PROFILE=dev-account-01
# Or use: aws configure / environment variables / SSO

# Navigate to the scanned account config
cd infrastructure/terragrunt/scanned_account_dev1

# Deploy IAM role
terragrunt init
terragrunt plan
terragrunt apply
```

Repeat for each scanned account (dev, prod, etc.).

### 4. Verify Deployment

```bash
# Back in central account credentials
export AWS_PROFILE=central-account

# Test Lambda manually
aws lambda invoke \
  --function-name perimeter-guard-scanner \
  --payload '{}' \
  output.json

cat output.json
```

## Adding New Accounts to Scan

1. **Create a new Terragrunt folder:**
   ```bash
   cp -r terragrunt/scanned_account_dev1 terragrunt/scanned_account_newaccount
   ```

2. **Edit the new `terragrunt.hcl`** to set appropriate Environment tag

3. **Update central account** `target_accounts` list to include the new account ID

4. **Deploy in order:**
   - First: new scanned account (with new account credentials)
   - Then: central account (to update Lambda with new target)

## Security Notes

- **External ID**: Prevents confused deputy attacks. Generate with `uuidgen` or `openssl rand -base64 32`. Never commit real values to version control.
- **IAM Roles**: Scanned account roles only trust the specific central account and require the external ID.
- **Permissions**: All permissions are read-only. The Lambda cannot modify any resources.

## Troubleshooting

### "AccessDenied when assuming role"
- IAM role not deployed in target account
- Wrong `external_id` in central vs scanned account
- Central account ID mismatch

### "S3 bucket does not exist"
Terragrunt creates the state bucket automatically on first `init`. If it fails:
```bash
aws s3 mb s3://armor-perimeter-guard-<ACCOUNT_ID>-terraform-state --region us-east-1
```

### "DynamoDB table does not exist"
```bash
aws dynamodb create-table \
  --table-name armor-perimeter-guard-<ACCOUNT_ID>-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```
