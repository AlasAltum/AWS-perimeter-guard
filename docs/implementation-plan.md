# AWS Perimeter Guard - Implementation Plan

## Project Overview

A Python 3.12-based open-source tool that scans a single AWS account for resources supporting WAF and reports their association status (CSV format) using hexagonal architecture. For multi-account scenarios, deploy the infrastructure in each target account with a central Lambda that assumes roles.

## Architecture Decision Records

### Technology Stack
- **Language**: Python 3.12 with type hints (dataclasses for structure)
- **Architecture**: Hexagonal (Ports & Adapters)
- **AWS SDK**: boto3 with type stubs (boto3-stubs)
- **IaC**: Terraform for Lambda + EventBridge deployment
- **Packaging**: uv/pip (requirements.txt) for simplicity
- **Testing**: pytest with moto for AWS mocking

### Deployment Modes

**Single Account Mode** (Default):
- Deploy: Lambda + EventBridge + IAM role in one account
- Scans: Resources in the same account
- Terraform: `allow_multiaccount_through_iam_role = false`

**Multi-Account Mode** (Optional):
- **Central Account**: Deploy Lambda + EventBridge (set `allow_multiaccount_through_iam_role = false`)
- **Target Accounts**: Deploy IAM role only (set `allow_multiaccount_through_iam_role = true`)
- Central Lambda assumes roles in target accounts to scan
- **Manual**: Apply Terraform in each target account

**DevEx Benefits**:
- ✅ Simple pip-based installation (no Poetry/UV)
- ✅ Single account works out-of-box
- ✅ Multi-account via manual Terraform apply per account
- ✅ Flexible `allow_multiaccount_through_iam_role` variable

---

## Task Breakdown

> **Task Status Guide**:
> - `Not Started` - Task has not begun
> - `In Progress` - Currently working on this task
> - `Completed` - Task finished and deliverables verified
> 
> **To track progress**: Update the `**Status**:` field when starting/completing tasks. This allows any LLM to pick up where work left off.

### Task 1: Project Structure & Dependencies Setup
**Status**: Completed  
**Dependencies**: None  
**Estimated Time**: 20 minutes

**Deliverables**:
- `requirements.txt` - Runtime dependencies (boto3, boto3-stubs, click)
- `requirements-dev.txt` - Development dependencies (pytest, moto, mypy, black, ruff)
- `.gitignore` for Python projects
- Directory structure following hexagonal architecture
- `Makefile` for common commands

**Key Files**:
```
├── src/
│   ├── domain/
│   ├── application/
│   ├── ports/
│   ├── adapters/
│   └── main.py
├── terraform/
├── tests/
├── docs/
├── requirements.txt
└── requirements-dev.txt
```

---

### Task 2: Domain Model Implementation
**Status**: Completed  
**Dependencies**: Task 1  
**Estimated Time**: 1 hour

**Deliverables**:
- `src/domain/entities/resource.py` - Resource entity with ARN, type, region
- `src/domain/entities/web_acl.py` - WebACL entity
- `src/domain/entities/scan_result.py` - ScanResult aggregate root
- `src/domain/value_objects/resource_type.py` - Enum for 8 resource types
- `src/domain/value_objects/resource_arn.py` - ARN value object with validation

**Key Concepts**:
- Dataclasses for structure
- Type hints for clarity
- Rich domain behavior (e.g., `resource.has_waf()`, `resource.is_compliant()`)

---

### Task 3: Port Interfaces Definition
**Status**: Completed  
**Dependencies**: Task 2  
**Estimated Time**: 30 minutes

**Deliverables**:
- `src/ports/outbound/aws_client_port.py` - Abstract AWS operations
- `src/ports/outbound/output_port.py` - Export interface (CSV only)
- `src/ports/outbound/logger_port.py` - Logging abstraction

**Key Concepts**:
- Protocol classes (Python 3.12 structural subtyping)
- Clear contracts for adapters
- Dependency inversion principle
- **Note**: No inbound scanner port needed (simplified architecture)

---

### Task 4: AWS Client Adapter (Boto3)
**Status**: Completed  
**Dependencies**: Task 3  
**Estimated Time**: 2 hours

**Deliverables**:
- `src/adapters/outbound/boto3_waf_client.py` - WAFv2 operations
- `src/adapters/outbound/boto3_resource_client.py` - Resource listing (ALB, CloudFront, etc.)
- Multi-region scanning logic
- CloudFront scope vs Regional scope handling
- Pagination support for large result sets

**Key Implementation Details**:
- Parallel region scanning using `concurrent.futures.ThreadPoolExecutor`
- Resource ARN construction for each service
- Error handling for rate limits and permissions

---

### Task 5: Output Adapters (CSV & Logger)
**Status**: Completed  
**Dependencies**: Task 3  
**Estimated Time**: 1 hour

**Deliverables**:
- `src/adapters/outbound/csv_exporter.py` - CSV file generation
- `src/adapters/outbound/cloudwatch_logger.py` - Structured logging for CloudWatch
- `src/adapters/outbound/console_logger.py` - Console logging for CLI

**CSV Format** (Primary Output):
```csv
Account ID,Region,Resource Type,Resource ARN,WAF Name,WAF ARN,Compliant,Scanned At
123456789012,us-east-1,ALB,arn:aws:...,MyWAF,arn:aws:wafv2:...,true,2026-01-17T10:30:00Z
```

**CloudWatch Log Format** (structured JSON for Lambda):
```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "account_id": "123456789012",
  "resource_type": "ALB",
  "resource_arn": "arn:aws:elasticloadbalancing:...",
  "waf_associated": true,
  "waf_name": "MyWAF",
  "compliant": true
}
```

**Note**: JSON file output removed - CSV only for simplicity

---

### Task 6: Scanner Service (Core Logic)
**Status**: Completed  
**Dependencies**: Tasks 2, 3, 4  
**Estimated Time**: 2 hours

**Deliverables**:
- `src/application/scanner_service.py` - Orchestration logic
- `src/application/region_scanner.py` - Per-region scanning
- Compliance rules (e.g., "all public ALBs must have WAF")

**Key Flow**:
1. Scan CloudFront resources (us-east-1, CLOUDFRONT scope)
2. Scan regional resources (all regions, REGIONAL scope)
3. Build ScanResult aggregate
4. Export via CSV or CloudWatch logs

**Note**: Single account per execution (multi-account handled by deploying per-account and central Lambda assumes roles)

---

### Task 6.5: Resource Relationship Detection (Fronted-By Resources)
**Status**: Not Started  
**Dependencies**: Task 6  
**Estimated Time**: 2-3 hours

**Deliverables**:
- Enhanced `Resource` entity with `fronted_by_*` fields
- New `COMPLIANT_FRONTED_BY_WAF` compliance status
- `get_cloudfront_origins_map()` method in AWS client adapter
- `_enrich_fronted_by_relationships()` method in scanner service
- Updated CSV export with fronted-by columns
- Tests for relationship detection

**Problem**: Some resources (HTTP API Gateways, REST APIs, ALBs) cannot have direct WAF but may be protected by CloudFront distributions with WAF. This task detects these "fronted by" relationships.

**Key Features**:
1. Build CloudFront origins map (domain → distributions with WAF)
2. Match HTTP API Gateway, REST API, and ALB endpoints to CloudFront origins
3. Enrich resources with fronted-by information
4. New compliance status: `COMPLIANT_FRONTED_BY_WAF`
5. CSV columns: "Fronted By Resource", "Fronted By WAF", "Notes"

**Example Output**:
```csv
Resource Type,Resource Name,Has WAF,Compliance Status,Fronted By Resource,Fronted By WAF,Notes
API Gateway HTTP API,api-exam,No,COMPLIANT_FRONTED_BY_WAF,arn:aws:cloudfront::...:distribution/E3T3BYVBS5ILLA,http_api_webacl_exam,"Fronted by CloudFront Distribution ... with WAF http_api_webacl_exam"
```

See `docs/tasks/task-06.5-resource-relationships.md` for full implementation details.

---

### Task 7: CLI Adapter (Manual Execution)
**Status**: Completed  
**Dependencies**: Task 6  
**Estimated Time**: 1 hour

**Deliverables**:
- `src/adapters/inbound/cli_adapter.py` - Click-based CLI
- `src/main.py` - Entry point with argument parsing
- Environment variable support for AWS credentials

**CLI Usage Examples**:
```bash
# Single account scan with CSV output
export AWS_PROFILE=my-account
python -m src.main scan --output csv --file results.csv

# Specific regions only
python -m src.main scan --regions us-east-1,eu-west-1 --output csv --file results.csv

# Output to stdout
python -m src.main scan --output csv
```

---

### Task 8: Lambda Adapter (Automated Execution)
**Status**: Not Started  
**Dependencies**: Task 6  
**Estimated Time**: 1 hour

**Deliverables**:
- `src/adapters/inbound/lambda_handler.py` - Lambda entry point
- EventBridge event parsing
- CloudWatch Logs integration
- Error handling and retry logic

**Lambda Event Schema**:
```json
{
  "scan_type": "full",
  "regions": ["us-east-1", "us-west-2"],
  "output_type": "cloudwatch"
}
```

---

### Task 9: Terraform Infrastructure
**Status**: Not Started  
**Dependencies**: Task 8  
**Estimated Time**: 2 hours

**Deliverables**:
- `terraform/main.tf` - Lambda + EventBridge + IAM role
- `terraform/variables.tf` - Configuration variables
- `terraform/outputs.tf` - Deployment outputs
- `terraform/terraform.tfvars.example` - Configuration template

**Key Variable** - `allow_multiaccount_through_iam_role`:
```hcl
variable "allow_multiaccount_through_iam_role" {
  description = "If true, only creates IAM role (for target accounts). If false, creates Lambda + EventBridge + IAM role (for central/single account)"
  type        = bool
  default     = false
}
```

**Single Account Deployment** (`allow_multiaccount_through_iam_role = false`):
- Creates: Lambda function + EventBridge schedule + IAM role
- Lambda scans resources in same account
- Use case: Standalone account monitoring

**Target Account Deployment** (`allow_multiaccount_through_iam_role = true`):
- Creates: IAM role only with trust policy for central Lambda
- Central Lambda assumes this role to scan
- Use case: Target account in multi-account setup

**Example Configuration** (`terraform.tfvars`):
```hcl
# Single account mode
allow_multiaccount_through_iam_role = false
scan_schedule                       = "rate(24 hours)"
scan_regions                        = ["us-east-1", "us-west-2"]

# OR for target account in multi-account setup
allow_multiaccount_through_iam_role = true
central_lambda_role_arn            = "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"
```

**Deployment**:
```bash
# Single account
cd terraform
terraform init
terraform apply

# Multi-account: Apply in central account first (allow_multiaccount_through_iam_role = false)
# Then apply in each target account (allow_multiaccount_through_iam_role = true)
```

---

### Task 10: Documentation
**Status**: Not Started  
**Dependencies**: All tasks  
**Estimated Time**: 2 hours

**Deliverables**:
- `README.md` - Quick start guide, features, installation with pip
- `docs/architecture.md` - Hexagonal architecture explanation with diagrams
- `docs/multi-account-setup.md` - Multi-account deployment guide (manual Terraform per account)
- `docs/adding-output-adapters.md` - How to extend with new exporters
- `docs/supported-resources.md` - Complete list of WAF-compatible resources (8 types)
- `docs/troubleshooting.md` - Common issues and solutions

**Key Documentation Points**:
- Emphasize simple pip installation (no Poetry)
- Explain `allow_multiaccount_through_iam_role` variable clearly
- CSV as primary output format
- Multi-account requires manual Terraform apply in each account

---

### Task 11: Testing Setup
**Status**: Not Started  
**Dependencies**: Tasks 2-8  
**Estimated Time**: 2 hours

**Deliverables**:
- `tests/unit/` - Unit tests for domain and application logic
- `tests/integration/` - Integration tests with moto (AWS mocking)
- `tests/conftest.py` - Pytest fixtures
- GitHub Actions workflow for CI/CD
- Test coverage reporting (target: >80%)

---

## Total Estimated Time: 15-18 hours

## Execution Order
1. Tasks 1, 2 (Foundation)
2. Tasks 3, 4, 5 (Adapters)
3. Task 6 (Core logic)
4. Task 6.5 (Resource relationships - fronted-by detection)
5. Tasks 7, 8 (Inbound adapters)
6. Task 9 (Infrastructure)
7. Tasks 10, 11 (Documentation & Testing)

---

## Multi-Account Implementation Details

### Architecture for Multi-Account Scanning

**Pattern**: Central Lambda with IAM Roles in Target Accounts

```
┌──────────────────────────────────────────────────────────┐
│                Central Account (123456789012)            │
│  ┌────────────────────────────────────────────────────┐ │
│  │  PerimeterGuardLambda (EventBridge scheduled)     │ │
│  │  - sts:AssumeRole to target accounts              │ │
│  └─────────────┬──────────────────────────────────────┘ │
└────────────────┼─────────────────────────────────────────┘
                 │
                 │ STS AssumeRole
                 │
    ┌────────────┼────────────┬────────────────────┐
    │            │            │                    │
    ▼            ▼            ▼                    ▼
┌────────┐  ┌────────┐  ┌────────┐          ┌────────┐
│ Acct 1 │  │ Acct 2 │  │ Acct 3 │   ...    │ Acct N │
│  Role  │  │  Role  │  │  Role  │          │  Role  │
└────────┘  └────────┘  └────────┘          └────────┘
 (IAM only)  (IAM only)  (IAM only)         (IAM only)
     │            │            │                  │
     └────────────┴────────────┴──────────────────┘
                        │
                        ▼
              Scan WAF Resources
              (ALB, CloudFront, API GW, etc.)
```

### Deployment Flow

**1. Central Account Setup**:
```bash
cd terraform
# Edit terraform.tfvars
allow_multiaccount_through_iam_role = false  # Full deployment
scan_schedule = "rate(24 hours)"

terraform init
terraform apply
```

**2. Target Account Setup** (repeat for each account):
```bash
cd terraform
# Edit terraform.tfvars
allow_multiaccount_through_iam_role = true   # IAM role only
central_lambda_role_arn = "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"

terraform init
terraform apply
```

**3. Configure Central Lambda**:
```bash
# Update Lambda environment variables with target account IDs
aws lambda update-function-configuration \
  --function-name perimeter-guard-scanner \
  --environment Variables="{TARGET_ACCOUNTS='111111111111,222222222222,333333333333'}"
```

### Lambda Configuration

**Environment Variables**:
```hcl
# terraform/main.tf (when allow_multiaccount_through_iam_role = false)
resource "aws_lambda_function" "scanner" {
  # ...
  environment {
    variables = {
      SCAN_REGIONS         = join(",", var.scan_regions)
      ASSUME_ROLE_NAME     = "PerimeterGuardScanRole"
      TARGET_ACCOUNTS      = var.target_accounts  # Comma-separated account IDs
      OUTPUT_TYPE          = "cloudwatch"
    }
  }
}
```

### Permission Model

**Central Account Lambda Role** (created when `allow_multiaccount_through_iam_role = false`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ScanLocalAccount",
      "Effect": "Allow",
      "Action": [
        "wafv2:ListWebACLs",
        "wafv2:GetWebACLForResource",
        "wafv2:ListResourcesForWebACL",
        "elasticloadbalancing:DescribeLoadBalancers",
        "cloudfront:ListDistributions",
        "apigateway:GET",
        "appsync:ListGraphqlApis",
        "cognito-idp:ListUserPools",
        "apprunner:ListServices",
        "ec2:DescribeVerifiedAccessInstances"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AssumeRoleInTargetAccounts",
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::*:role/PerimeterGuardScanRole"
    }
  ]
}
```

**Target Account IAM Role** (created when `allow_multiaccount_through_iam_role = true`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "wafv2:ListWebACLs",
        "wafv2:GetWebACLForResource",
        "wafv2:ListResourcesForWebACL",
        "elasticloadbalancing:DescribeLoadBalancers",
        "cloudfront:ListDistributions",
        "apigateway:GET",
        "appsync:ListGraphqlApis",
        "cognito-idp:ListUserPools",
        "apprunner:ListServices",
        "ec2:DescribeVerifiedAccessInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust Policy** (for target account role):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

### Developer Experience

**Single-Account Mode**:
```bash
# Install dependencies
uv pip install -r requirements.txt

# Set AWS credentials
export AWS_PROFILE=my-account

# Run CLI scan
python -m src.main scan --output csv --file results.csv

# Or deploy Lambda
cd terraform
terraform init
terraform apply  # Lambda runs daily automatically
```

**Multi-Account Mode**:
```bash
# 1. Deploy in central account
cd terraform
# Edit terraform.tfvars: allow_multiaccount_through_iam_role = false
terraform apply

# 2. Deploy IAM role in each target account
# Switch to target account credentials
export AWS_PROFILE=target-account-1
# Edit terraform.tfvars: allow_multiaccount_through_iam_role = true
terraform apply

# Repeat step 2 for each target account

# 3. Lambda in central account runs automatically and assumes roles
```

---

## Success Criteria

- ✅ Simple uv/pip-based installation (no Poetry)
- ✅ Single account mode works out-of-box
- ✅ Multi-account via manual Terraform apply per account
- ✅ CSV as primary output format
- ✅ Clear `allow_multiaccount_through_iam_role` variable documentation
- ✅ Type-safe Python code with >80% test coverage
- ✅ CLI and Lambda execution modes
- ✅ Extensible hexagonal architecture
