# AWS Perimeter Guard

Open-source security audit tool that scans AWS accounts to identify WAF coverage gaps across your infrastructure perimeter.
Can be used manually as a script (instruction on how to use this as script below) or it can be deployed as a lambda function in AWS, executed by a scheduler periodically to generate automatic reports on security.


## Features

**Check "WAFable" Resources:**
- Application Load Balancers (ALB)
- CloudFront Distributions
- API Gateway REST APIs (with stage-level WAF detection)
- API Gateway HTTP APIs
- AppSync GraphQL APIs
- Cognito User Pools
- App Runner Services
- Verified Access Instances

**Advanced Detection Capabilities**
- Direct WAF associations
- REST API stage-level WAF mapping
- CloudFront-fronted resources (detects HTTP APIs, REST APIs, and ALBs protected via CloudFront)
- Compliance status reporting

**Multi-Region Support**
- Scan across all AWS commercial regions
- Automatic CloudFront global distribution detection

**Easily extensible for new resources or cloud providers**
- Hexagonal (Ports & Adapters) architecture, so new adapters can be easily created with LLMs
- Type-safe Python 3.12+ with full type hints


## Installation (Script)

### Using uv (recommended)
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Using pip
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## AWS Credentials Setup

Before using AWS Perimeter Guard, ensure you have AWS credentials configured. The tool uses boto3, which supports multiple authentication methods:

### Option 1: AWS CLI Configuration (Recommended)
```bash
pip install awscli
aws configure
```

### Option 2: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-east-1
```

## Usage

AWS Perimeter Guard can be used in two ways:
1. **As a CLI tool** - Run scans directly from your terminal
2. **As an AWS Lambda function** - Automated scheduled scans across multiple accounts

### 1) Basic Usage (CLI)

For quick tests and validation:

```bash
# Activate virtual environment
source .venv/bin/activate

# Quick scan of all resources in default regions
python -m src.main scan

# Scan with custom output file
python -m src.main scan --output waf-audit-$(date +%Y%m%d).csv
```


### 2) Lambda Deployment (Automated scanning on AWS)

For automated multi-account scanning, deploy AWS Perimeter Guard as a Lambda function.

There are two ways to deploy the infrastructure:

1. **Terragrunt (Recommended)** - Provides unified variable management and easier multi-account deployment
2. **Terraform** - Direct module usage for simpler setups

See the [Infrastructure deployment guide](infrastructure/README.md) for complete setup instructions.

**Quick Overview (Terragrunt - Recommended):**
```bash
cd infrastructure/terragrunt/central_account

# Configure root.hcl with your account IDs and settings
vim ../root.hcl

# Deploy
terragrunt init
terragrunt plan
terragrunt apply

# Configure:
# - target_accounts: List of AWS account IDs to scan
# - scan_regions: Regions to scan in each account
# - scan_schedule: EventBridge schedule expression
```

**Alternative: Terraform Direct**
```bash
cd infrastructure/modules/scan-lambda-scheduler

# Configure terraform.tfvars and adjust variables
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars

terraform init
terraform apply
```

The Lambda function will:
- Run on a schedule (default: daily)
- Scan all configured accounts and regions
- Log results to CloudWatch Logs (JSON format)
- Automatically handle cross-account role assumption

**Note:** Requires deploying IAM roles in target accounts. See terraform documentation for details.


## Output Format

The tool generates a CSV report with the following columns:

- Account ID
- Region
- Resource Type
- Resource Name
- Resource ARN
- Has WAF (Yes/No)
- WAF Name
- WAF ARN
- Is Public
- Compliance Status
- Scanned At
- Fronted By Resource (ARN of CloudFront distribution)
- Fronted By WAF (WAF protecting the CloudFront distribution)
- Notes

### Compliance Statuses

- `COMPLIANT` - Resource has direct WAF protection
- `COMPLIANT_FRONTED_BY_WAF` - Resource is fronted by CloudFront with WAF
- `COMPLIANT_NO_WAF_REQUIRED` - Resource doesn't require WAF (non-public or HTTP API)
- `NON_COMPLIANT` - Public resource without WAF protection


## Architecture

Built using Hexagonal Architecture (Ports & Adapters) for maintainability and testability:

```
src/
├── domain/          # Core business logic (entities, value objects)
├── application/     # Use cases and orchestration
├── ports/           # Interface definitions
└── adapters/        # External integrations (AWS, CLI, logging)
```

## Development

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Type checking
mypy src/

# Code formatting
black src/ tests/

# Linting
ruff check src/ tests/
```

Developed primarily using AI-augmented coding. I also documented the best practices I followed in the docs folder, creating implementation plans, summaries, and keeping documentation updated so LLMs can work better with extensive context.


## License

MIT License - See LICENSE file for details 
