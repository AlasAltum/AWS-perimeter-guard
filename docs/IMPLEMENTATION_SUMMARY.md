# AWS Perimeter Guard - Implementation Summary

## Overview

This document provides a high-level summary of the implementation plan for the AWS Perimeter Guard utility - an open-source DevOps tool that scans AWS resources for WAF associations using hexagonal architecture.

## What You'll Get

### Core Functionality
✅ Scans 8 AWS resource types: ALB, CloudFront, API Gateway (REST/HTTP), AppSync, Cognito, App Runner, Verified Access  
✅ Detects WAF associations for each resource  
✅ Compliance reporting (which resources lack WAF protection)  
✅ Multi-region scanning (handles both `REGIONAL` and `CLOUDFRONT` scopes)  
✅ **Single-account** and **multi-account (AWS Organizations)** support

### Execution Modes
✅ **CLI Mode**: Manual execution by DevOps engineers (exports to CSV/JSON)  
✅ **Lambda Mode**: Automated daily scans with CloudWatch Logs output  
✅ Extensible output adapters (CSV, CloudWatch, JSON - easy to add Slack, Loki, etc.)

### Developer Experience
✅ **One-command deployment** for AWS Organizations  
✅ **Automatic role propagation** to new accounts via StackSets  
✅ **Single configuration file** (`terraform.tfvars`)  
✅ Type-safe Python 3.12 with Pydantic  
✅ Comprehensive documentation  

---

## Architecture Highlights

### Hexagonal Architecture (Ports & Adapters)

```
Driving Side              Core                 Driven Side
─────────────            ─────                ─────────────
   CLI                    │                     boto3
  Lambda      ─────►   Scanner   ─────►      CloudWatch
REST API               Service                  CSV
                                               Loki/OTLP
```

**Benefits**:
- Test core logic without AWS (mock adapters)
- Swap outputs without changing scanner logic
- Add new resource types independently
- Clear separation of concerns

### AWS Organizations Setup

```
Management Account
├── Lambda: perimeter-guard-scanner
│   └── EventBridge: Daily trigger
└── StackSet: Deploys role to all accounts
    
Member Accounts (auto-deployed via StackSet)
└── IAM Role: PerimeterGuardScanRole
    └── Permissions: Read-only access to resources + WAFv2
```

**Key Innovation**: StackSet with `SERVICE_MANAGED` deployment automatically:
- Deploys `PerimeterGuardScanRole` to **all existing accounts**
- Deploys role to **new accounts when they join**
- **Zero manual per-account setup**

---

## Task Breakdown

### Phase 1: Foundation (Tasks 1-3)
**Time**: ~2.5 hours

1. **Project Setup**: Poetry, directory structure, Makefile
2. **Domain Model**: Entities (Resource, WebACL, ScanResult), value objects (ResourceType, ResourceArn)
3. **Ports Definition**: Abstract interfaces (AWSClientPort, OutputPort, LoggerPort)

**Outcome**: Type-safe domain model with clear contracts

---

### Phase 2: Adapters (Tasks 4-5)
**Time**: ~3.5 hours

4. **AWS Client Adapter**: boto3 implementation for WAFv2 + resource discovery
5. **Output Adapters**: CSV exporter, CloudWatch logger, JSON exporter

**Outcome**: Working adapters for AWS and output destinations

---

### Phase 3: Core Logic (Task 6)
**Time**: ~2.5 hours

6. **Scanner Service**: Orchestration, multi-region scanning, compliance checks

**Outcome**: Complete business logic for resource scanning

---

### Phase 4: Entry Points (Tasks 7-8)
**Time**: ~2 hours

7. **CLI Adapter**: Click-based CLI with environment variable support
8. **Lambda Adapter**: Lambda handler with EventBridge integration

**Outcome**: Manual and automated execution modes

---

### Phase 5: Infrastructure (Task 9)
**Time**: ~3 hours

9. **Terraform Modules**: StackSet, Lambda, EventBridge, single-account & organization environments

**Outcome**: One-command deployment infrastructure

---

### Phase 6: Quality (Tasks 10-11)
**Time**: ~4 hours

10. **Documentation**: README, architecture docs, AWS Organizations setup guide
11. **Testing**: Unit tests, integration tests with moto, CI/CD pipeline

**Outcome**: Production-ready, well-documented project

---

## AWS Organizations Implementation: The DevEx Advantage

### Traditional Multi-Account Approach (❌ Complex)
```bash
# For each of 50 accounts:
1. Switch AWS profile/credentials
2. Run CloudFormation template
3. Manually verify role creation
4. Update central config with account ID
5. Test assume role permissions

# Result: 2-4 hours of manual work
```

### Our Approach (✅ Simple)
```bash
# One-time setup:
cd terraform/environments/organization
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars (2 required values: account ID, org ID)
terraform init
terraform apply

# Result: 5 minutes, fully automated
```

**What Terraform Does**:
1. Creates `PerimeterGuardLambdaRole` in management account
2. Creates StackSet with `PerimeterGuardScanRole` CloudFormation template
3. **Automatically deploys StackSet to all accounts** in Organization
4. Deploys Lambda with EventBridge schedule
5. Configures CloudWatch Logs

**For New Accounts**:
- StackSet automatically deploys role when account joins
- Scanner picks up new account on next run
- **Zero manual intervention**

---

## Configuration Centralization

### Single Source of Truth: `terraform.tfvars`

```hcl
# Only 2 values required:
management_account_id = "123456789012"
organization_id       = "o-abc123xyz"

# Everything else has sensible defaults:
aws_region       = "us-east-1"              # Optional
scan_regions     = ["us-east-1", "us-west-2"]  # Optional (empty = all)
scan_schedule    = "rate(24 hours)"         # Optional
```

### Runtime Configuration (Lambda Environment Variables)

```python
# All config automatically available to Lambda
config = {
    'organization_id': os.getenv('ORGANIZATION_ID'),
    'scan_regions': os.getenv('SCAN_REGIONS', '').split(','),
    'assume_role_name': os.getenv('ASSUME_ROLE_NAME'),
    'output_type': os.getenv('OUTPUT_TYPE', 'cloudwatch')
}
```

**No manual Lambda environment variable configuration needed** - Terraform injects everything from `terraform.tfvars`.

---

## Key Design Decisions

### 1. Python 3.12 with Pydantic
**Why**: Type safety, validation, modern features (pattern matching)

```python
# Example: Automatic validation
resource = Resource(
    arn=ResourceArn(value="arn:aws:..."),  # Validated format
    resource_type=ResourceType.ALB,        # Enum (type-safe)
    region="us-east-1",
    account_id="123456789012"
)
```

### 2. Hexagonal Architecture
**Why**: Testable, extensible, maintainable

```python
# Add Slack output without touching core logic
class SlackAdapter(OutputPort):
    def export(self, scan_result: ScanResult):
        # Slack-specific logic
        pass

# Use it
scanner.scan_account(request, outputs=[CsvExporter(), SlackAdapter()])
```

### 3. StackSets for Multi-Account
**Why**: Automatic propagation, no per-account manual work

**Alternatives Considered**:
- ❌ Manual CloudFormation per account (tedious)
- ❌ Config Rules (limited functionality)
- ✅ StackSets with SERVICE_MANAGED (winner)

---

## Usage Examples

### Single Account - CLI
```bash
# Export AWS credentials
export AWS_PROFILE=my-account

# Run scan, export to CSV
python -m src.main scan \
  --regions us-east-1 us-west-2 \
  --output csv \
  --file results.csv

# View results
cat results.csv
```

### Multi-Account - Lambda (Automated)
```bash
# One-time deployment
terraform apply

# Lambda runs daily automatically via EventBridge

# View logs
aws logs tail /aws/lambda/perimeter-guard-scanner --follow

# Manual trigger
aws lambda invoke \
  --function-name perimeter-guard-scanner \
  --payload '{"scan_type":"full"}' \
  response.json
```

### Multi-Account - CLI (On-Demand)
```bash
export AWS_PROFILE=org-management

python -m src.main scan \
  --organization \
  --organization-id o-abc123xyz \
  --assume-role-name PerimeterGuardScanRole \
  --output csv \
  --file org-wide-scan.csv
```

---

## Output Formats

### CSV
```csv
Account ID,Region,Resource Type,Resource ARN,WAF Name,WAF ARN,Compliant,Scanned At
123456789012,us-east-1,ALB,arn:aws:...,MyWAF,arn:aws:wafv2:...,true,2026-01-17T10:30:00Z
123456789012,us-west-2,CLOUDFRONT,arn:aws:...,,No WAF,false,2026-01-17T10:31:00Z
```

### CloudWatch Logs (Structured JSON)
```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "account_id": "123456789012",
  "resource_type": "ALB",
  "resource_arn": "arn:aws:elasticloadbalancing:...",
  "waf_associated": true,
  "waf_name": "MyWAF",
  "compliant": true,
  "region": "us-east-1"
}
```

### JSON File
```json
{
  "scan_id": "scan-20260117-103000",
  "account_id": "123456789012",
  "total_resources": 45,
  "resources_with_waf": 38,
  "compliance_rate": 84.4,
  "resources": [ /* ... */ ]
}
```

---

## Cost Estimate

**For 50 accounts scanning daily**:

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Lambda | 50 accounts × 2 min × 128MB × 30 days | $0.20 |
| CloudWatch Logs | ~1GB/month | $5.00 |
| StackSets | Deployment only | $0.00 |
| **Total** | | **$5-10/month** |

---

## Next Steps

1. **Review the plan**: Read `docs/implementation-plan.md` for full details
2. **Review tasks**: Check `docs/tasks/task-*.md` for implementation guidance
3. **Start implementation**: Begin with Task 1 (project structure)
4. **Iterate**: Build incrementally, test each component

---

## Questions Answered

### Q: How do permissions work across accounts?
**A**: StackSet deploys `PerimeterGuardScanRole` to all accounts. Lambda in management account assumes this role to scan each account.

### Q: What if I add a new account?
**A**: StackSet automatically deploys the role. Scanner picks it up on the next run. Zero config needed.

### Q: Can I exclude certain accounts?
**A**: Yes, configure StackSet to target specific OUs instead of root OU.

### Q: How do I add a new output format?
**A**: Implement `OutputPort` interface in a new adapter class. No core logic changes needed.

### Q: Can I use this without AWS Organizations?
**A**: Yes! Single-account mode works standalone via CLI or Lambda deployment.

---

## Success Criteria

- ✅ Single `terraform apply` deploys entire solution
- ✅ New accounts automatically included
- ✅ CLI works without infrastructure deployment
- ✅ Output adapters are pluggable
- ✅ >80% test coverage
- ✅ Clear documentation for all use cases

---

## Repository Structure (Final)

```
AWS-perimeter-guard/
├── README.md                    # Quick start, features, installation
├── LICENSE                      # Open source license
├── pyproject.toml              # Poetry dependencies
├── requirements.txt            # Lambda packaging
├── Makefile                    # Development commands
│
├── src/
│   ├── domain/                 # Entities & value objects
│   ├── application/            # Scanner service (business logic)
│   ├── ports/                  # Abstract interfaces
│   ├── adapters/               # Concrete implementations
│   └── main.py                 # CLI entry point
│
├── terraform/
│   ├── modules/
│   │   ├── scanner-lambda/
│   │   ├── eventbridge-schedule/
│   │   └── iam-stackset/
│   └── environments/
│       ├── single-account/
│       └── organization/
│           ├── main.tf
│           ├── variables.tf
│           └── terraform.tfvars.example  # ← Only file users edit!
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
└── docs/
    ├── implementation-plan.md   # This file
    ├── architecture.md          # Hexagonal architecture explanation
    ├── aws-organizations-setup.md
    ├── adding-output-adapters.md
    └── tasks/                   # Task-by-task implementation guide
        ├── task-01-project-setup.md
        ├── task-02-domain-model.md
        ├── task-03-ports-definition.md
        └── task-09-terraform-infrastructure.md
```

---

## Ready to Build?

The plan is complete and ready for implementation. Each task has detailed documentation including:
- Code examples
- Key design decisions
- Benefits and trade-offs
- Testing strategies

Start with Task 1 and build incrementally! 🚀
