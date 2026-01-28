# Implementation Plan Updates Summary

## Changes Made

I've updated the implementation plan based on your requirements. Here's what changed:

### 1. ✅ Packaging: Pip instead of Poetry
**Before**: Poetry with pyproject.toml  
**After**: Simple pip with requirements.txt + requirements-dev.txt

**Benefits**:
- Lower friction for users
- No need to install Poetry/UV
- Same file works for development and Lambda packaging
- Standard Python practice

**Files Updated**:
- `docs/implementation-plan.md` - Technology stack section
- `docs/tasks/task-01-project-setup.md` - Complete rewrite for pip

---

### 2. ✅ Removed Multi-Account/Organizations Complexity
**Before**: AWS Organizations with CloudFormation StackSets (automatic deployment)  
**After**: Manual Terraform apply per account (simple and explicit)

**Key Changes**:
- Removed StackSet modules
- Removed `organizations:ListAccounts` permission requirements
- Simplified architecture diagrams
- Manual deployment per account (more control, easier to understand)

**Files Updated**:
- `docs/implementation-plan.md` - Deployment modes section
- All task descriptions simplified

---

### 3. ✅ CSV Only (No JSON Output)
**Before**: CSV + JSON + CloudWatch Logs  
**After**: CSV + CloudWatch Logs only

**Benefits**:
- Simpler output adapter interface
- CSV for file export (CLI)
- CloudWatch Logs for Lambda (structured JSON format)
- Fewer adapters to maintain

**Files Updated**:
- Task 5 deliverables
- Output port interface (simplified)

---

### 4. ✅ Terraform Variable: `allow_multiaccount_through_iam_role`
**New flexible deployment pattern**:

```hcl
variable "allow_multiaccount_through_iam_role" {
  description = "If true, only creates IAM role (for target accounts). If false, creates Lambda + EventBridge + IAM role (for central/single account)"
  type        = bool
  default     = false
}
```

**Usage Patterns**:

**Single Account** (most common):
```hcl
# terraform.tfvars
allow_multiaccount_through_iam_role = false
scan_schedule = "rate(24 hours)"
scan_regions  = ["us-east-1", "us-west-2"]
```
Result: Lambda + EventBridge + IAM role created

**Multi-Account - Central Account**:
```hcl
# terraform.tfvars (in central account)
allow_multiaccount_through_iam_role = false
scan_schedule = "rate(24 hours)"
target_accounts = "111111111111,222222222222"
```
Result: Lambda + EventBridge + IAM role with sts:AssumeRole permission

**Multi-Account - Target Account**:
```hcl
# terraform.tfvars (in each target account)
allow_multiaccount_through_iam_role = true
central_lambda_role_arn = "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"
```
Result: Only IAM role with trust policy

**Files Updated**:
- `docs/implementation-plan.md` - Task 9 completely rewritten
- `docs/tasks/task-09-terraform-infrastructure.md` - Will need update

---

### 5. ✅ Removed `scanner_port` (Inbound Port)
**Before**: Inbound and outbound ports  
**After**: Only outbound ports (simpler)

**Rationale**:
- Scanner service is called directly by CLI/Lambda adapters
- No need for abstraction at the inbound side
- Reduces unnecessary complexity
- Hexagonal architecture still intact (outbound ports remain)

**Files Updated**:
- Task 3 deliverables (removed scanner_port)
- Architecture remains clean with proper dependency inversion on outbound side

---

## Updated Architecture

### Directory Structure (Simplified)
```
AWS-perimeter-guard/
├── src/
│   ├── domain/               # Entities & value objects
│   ├── application/          # Scanner service
│   ├── ports/outbound/       # AWS client, output, logger ports
│   ├── adapters/
│   │   ├── inbound/          # CLI, Lambda (call scanner directly)
│   │   └── outbound/         # boto3, CSV, CloudWatch
│   └── main.py
├── terraform/                # Flat structure (no modules)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── tests/
├── docs/
├── requirements.txt          # Simple pip
└── requirements-dev.txt
```

### Multi-Account Pattern (Simplified)

```
Central Account (123456789012)
├── Lambda Function (deployed with allow_multiaccount_through_iam_role = false)
├── EventBridge Schedule
└── IAM Role (can sts:AssumeRole to target accounts)

Target Account 1 (111111111111)
└── IAM Role only (deployed with allow_multiaccount_through_iam_role = true)
    └── Trust: Central Lambda Role

Target Account 2 (222222222222)
└── IAM Role only (deployed with allow_multiaccount_through_iam_role = true)
    └── Trust: Central Lambda Role
```

**Deployment Steps**:
1. Apply Terraform in central account
2. Apply Terraform in each target account (repeat manually)
3. Update central Lambda env var with target account IDs

**No StackSets, no automatic propagation - simple and explicit!**

---

## Time Estimate Changes

**Before**: 16-18 hours  
**After**: 13-15 hours

**Reduced by**:
- Simpler packaging setup (-10 min)
- No StackSet complexity (-1 hour)
- Fewer output adapters (-30 min)
- No inbound port (-15 min)

---

## Key Documentation Points

The updated plan emphasizes:
1. **Simple onboarding**: `pip install -r requirements.txt` and you're ready
2. **CSV primary output**: Easy for DevOps to analyze
3. **Multi-account pattern**: Clear, explicit, manual deployment (no magic)
4. **Terraform variable**: One variable controls deployment mode

---

## Next Steps

All planning documents are updated. Ready to proceed with implementation when you approve the plan!

The implementation will follow this simplified approach while maintaining the benefits of hexagonal architecture (testability, extensibility, clear boundaries).
