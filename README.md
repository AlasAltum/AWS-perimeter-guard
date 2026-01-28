# AWS Perimeter Guard

Open-source security audit tool that scans AWS accounts to identify WAF coverage gaps across your infrastructure perimeter.

## Features

**Check the following Resources:**
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
- Hexagonal (Ports & Adapters) architecture
- Type-safe Python 3.12+ with full type hints


## Installation

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
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure

# Or configure a specific profile
aws configure --profile my-profile
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

### CLI Usage

#### Basic Usage

```bash
# Activate virtual environment
source .venv/bin/activate

# Quick scan of all resources in default regions
python -m src.main scan

# Scan with custom output file
python -m src.main scan --output waf-audit-$(date +%Y%m%d).csv
```

#### Advanced CLI Usage

##### Scan Specific Regions
```bash
# Scan multiple specific regions
python -m src.main scan --regions us-east-1,eu-west-1,ap-southeast-1

# Scan all regions (use with caution - may take time)
python -m src.main scan --regions all
```

#### Scan Specific Resource Types
```bash
# Scan only load balancers and CloudFront distributions
python -m src.main scan --resource-types ALB,CLOUDFRONT

# Scan API-related resources
python -m src.main scan --resource-types API_GATEWAY_REST,API_GATEWAY_HTTP,APPSYNC
```

##### Cross-Account Scanning
```bash
# Use a specific AWS profile
AWS_PROFILE=my-profile python -m src.main scan

# Assume a role in another account
python -m src.main scan --role-arn arn:aws:iam::123456789012:role/WAFScannerRole
```

##### Output Options
```bash
# Save to specific file
python -m src.main scan --output my-security-audit.csv

# Output to stdout (for piping or scripting)
python -m src.main scan --stdout | grep NON_COMPLIANT

# Quiet mode (less verbose output)
python -m src.main scan --quiet --output results.csv
```

#### Utility Commands

```bash
# List all supported resource types
python -m src.main list-resource-types

# List default regions that will be scanned
python -m src.main list-regions

# Check AWS identity and permissions
python -m src.main whoami

# Show detailed help
python -m src.main --help
python -m src.main scan --help
```

#### Examples for Common CLI Use Cases

##### Security Audit
```bash
# Comprehensive security audit across multiple regions
python -m src.main scan \
  --regions us-east-1,eu-west-1,ap-southeast-1 \
  --output security-audit-$(date +%Y%m%d).csv \
  --verbose
```

##### Quick Compliance Check
```bash
# Fast check of critical resources
python -m src.main scan \
  --resource-types ALB,CLOUDFRONT,API_GATEWAY_REST \
  --regions us-east-1 \
  --output compliance-check.csv
```

##### CI/CD Integration
```bash
# Automated scanning in CI/CD pipeline
python -m src.main scan \
  --stdout \
  --quiet \
  | grep -c NON_COMPLIANT || exit 1
```

### Lambda Deployment

For automated multi-account scanning, deploy AWS Perimeter Guard as a Lambda function.

See the [Terraform deployment guide](terraform/README.md) for complete setup instructions.

**Quick Overview:**
```bash
cd terraform
terraform init
terraform apply

# Configure:
# - target_accounts: List of AWS account IDs to scan
# - scan_regions: Regions to scan in each account
# - scan_schedule: EventBridge schedule expression
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
