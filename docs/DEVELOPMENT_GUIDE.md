# AWS Perimeter Guard - Development Guide

## Project Context

This is an open-source Python 3.12 tool that scans AWS accounts for resources supporting WAF and reports their association status. The project uses **hexagonal architecture** (Ports & Adapters) for maintainability and extensibility.

**Core Purpose**: "This is a perimetral guard. It shows and lists all resources in AWS that can have a WAF and which WAF they have, in case they do."

---

## How to Work on This Project

### 1. Start with Documentation

**ALWAYS read these files first before implementing anything:**

1. **`docs/IMPLEMENTATION_SUMMARY.md`** - High-level overview of the entire project
   - Architecture decisions
   - Task breakdown with time estimates
   - Usage examples
   - Multi-account deployment patterns

2. **`docs/implementation-plan.md`** - Master plan with 11 tasks
   - Complete technical specifications
   - Deployment workflows
   - Permission models
   - Success criteria

3. **`docs/tasks/task-XX-*.md`** - Individual task documentation
   - Detailed implementation guidance
   - Code examples
   - Key design decisions
   - Testing strategies

**Reading Order**:
```
docs/IMPLEMENTATION_SUMMARY.md
  ↓
docs/implementation-plan.md
  ↓
docs/tasks/task-01-project-setup.md
  ↓
docs/tasks/task-02-domain-model.md
  ↓
... (continue sequentially)
```

### 2. Follow the Task Sequence

Tasks are designed to build incrementally:

**Phase 1: Foundation (Tasks 1-3)**
- Project structure and dependencies
- Domain model with Pydantic entities
- Port interface definitions

**Phase 2: Adapters (Tasks 4-5)**
- AWS boto3 client adapter
- Output adapters (CSV, CloudWatch)

**Phase 3: Core Logic (Task 6)**
- Scanner service orchestration

**Phase 4: Entry Points (Tasks 7-8)**
- CLI adapter for manual execution
- Lambda adapter for automated execution

**Phase 5: Infrastructure (Task 9)**
- Terraform configuration

**Phase 6: Quality (Tasks 10-11)**
- Documentation
- Testing and CI/CD

**Do NOT skip tasks or work out of order** unless there's a specific reason. Each task builds on previous ones.

---

## Key Architecture Decisions

### Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.12 | Type hints, pattern matching, best boto3 support |
| **Package Manager** | uv/pip (requirements.txt) | Simplicity, fast installation |
| **Type Safety** | Type hints + dataclasses | Simple, readable, standard library |
| **Architecture** | Hexagonal (Ports & Adapters) | Testability, extensibility, maintainability |
| **AWS SDK** | boto3 + boto3-stubs | Type hints for IDE support |
| **Testing** | pytest + moto | Unit tests + AWS mocking |
| **IaC** | Terraform | Simple, no StackSets |

### Critical Design Choices

1. **No Inbound Scanner Port**
   - Simplified architecture
   - Only outbound ports (AWS client, output, logger)
   - Reason: No need for abstraction over entry points

2. **CSV Primary Output**
   - CSV for manual execution
   - CloudWatch Logs for Lambda
   - No JSON file output (removed for simplicity)

3. **Multi-Account Pattern**
   - Manual Terraform deployment per account
   - No AWS Organizations/StackSets
   - Uses `allow_multiaccount_through_iam_role` variable
   - Central Lambda assumes roles in target accounts

4. **Supported Resources (8 types)**
   - ALB (Application Load Balancer)
   - CloudFront distributions
   - API Gateway REST APIs
   - API Gateway HTTP APIs
   - AppSync GraphQL APIs
   - Cognito User Pools
   - App Runner services
   - Verified Access instances

---

## Development Practices

### Test-Driven Development (TDD)

**Follow the Red-Green-Refactor cycle:**

```
1. RED: Write a failing test
   ↓
2. GREEN: Write minimal code to pass
   ↓
3. REFACTOR: Improve code quality
   ↓
4. Repeat
```

**Test Structure**:
```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_domain/         # Domain entities and value objects
│   ├── test_application/    # Scanner service logic
│   └── test_adapters/       # Adapter implementations
├── integration/             # AWS integration tests (moto)
│   ├── test_boto3_client.py
│   └── test_scanner_flow.py
└── conftest.py             # Shared fixtures
```

**Testing Guidelines**:

1. **Domain Layer**: 100% coverage, no external dependencies
   ```python
   # tests/unit/test_domain/test_resource.py
   def test_resource_has_waf_returns_true_when_waf_assigned():
       resource = Resource(
           arn="arn:aws:...",
           resource_type="ALB",
           region="us-east-1",
           account_id="123456789012",
           web_acl_arn="arn:aws:wafv2:..."
       )
       assert resource.has_waf() is True
   ```

2. **Application Layer**: Mock ports, test orchestration
   ```python
   # tests/unit/test_application/test_scanner_service.py
   def test_scanner_scans_all_regions(mock_aws_client, mock_output):
       service = ScannerService(mock_aws_client, mock_output)
       result = service.scan_account(regions=["us-east-1", "us-west-2"])
       assert mock_aws_client.list_resources.call_count == 2
   ```

3. **Adapters**: Use moto for AWS, verify behavior
   ```python
   # tests/integration/test_boto3_client.py
   @mock_wafv2
   def test_boto3_client_lists_web_acls():
       client = Boto3WafClient()
       web_acls = client.list_web_acls("us-east-1", Scope.REGIONAL)
       assert isinstance(web_acls, list)
   ```


### Code Quality Standards

**Type Hints Everywhere**:
```python
from typing import List, Optional
import boto3

def scan_resources(
    regions: List[str],
    account_id: str,
    session: Optional[boto3.Session] = None
) -> ScanResult:
    """Scan AWS resources for WAF associations.
    
    Args:
        regions: List of AWS regions to scan
        account_id: Target AWS account ID
        session: Optional boto3 session for cross-account
    
    Returns:
        ScanResult with all discovered resources
    """
    pass
```

**Use Dataclasses for Structure**:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Resource:
    """AWS resource that can have a WAF."""
    arn: str
    resource_type: str
    region: str
    account_id: str
    web_acl_arn: Optional[str] = None
    
    def has_waf(self) -> bool:
        """Check if resource has an associated WAF."""
        return self.web_acl_arn is not None
```

**Keep It Simple**:
- Use standard library dataclasses instead of Pydantic
- Don't over-engineer validation - validate at boundaries (CLI, Lambda input)
- Prefer readable code over complex patterns
- Use type hints for clarity, not enforcement

**Error Handling**:
```python
# Custom exceptions
class PerimeterGuardError(Exception):
    """Base exception for all application errors."""
    pass

class AWSClientError(PerimeterGuardError):
    """Error communicating with AWS services."""
    pass

class ValidationError(PerimeterGuardError):
    """Invalid input or configuration."""
    pass

# Usage
try:
    resources = aws_client.list_albs("us-east-1")
except ClientError as e:
    raise AWSClientError(f"Failed to list ALBs: {e}") from e
```

### Code Organization

**Hexagonal Architecture Layers**:

```
src/
├── domain/                          # Core business logic
│   ├── entities/                    # Rich domain objects
│   │   ├── resource.py             # Resource with behavior
│   │   ├── web_acl.py              # WebACL entity
│   │   └── scan_result.py          # Aggregate root
│   └── value_objects/               # Immutable values
│       ├── resource_type.py        # Enum
│       └── resource_arn.py         # Validated ARN
│
├── application/                     # Use cases
│   ├── scanner_service.py          # Main orchestration
│   └── region_scanner.py           # Per-region logic
│
├── ports/                           # Abstract interfaces
│   └── outbound/                    # Driven ports
│       ├── aws_client_port.py      # AWS operations
│       ├── output_port.py          # Export interface
│       └── logger_port.py          # Logging
│
├── adapters/                        # Concrete implementations
│   ├── inbound/                     # Driving adapters
│   │   ├── cli_adapter.py          # CLI entry point
│   │   └── lambda_handler.py       # Lambda entry point
│   └── outbound/                    # Driven adapters
│       ├── boto3_waf_client.py     # AWS WAFv2
│       ├── boto3_resource_client.py # Resource listing
│       ├── csv_exporter.py         # CSV output
│       ├── cloudwatch_logger.py    # CloudWatch logs
│       └── console_logger.py       # Console output
│
└── main.py                          # Application entry
```

**Dependency Rule**: 
- Dependencies point **inward** (toward domain)
- Domain has **zero** external dependencies
- Application depends on domain + ports
- Adapters depend on ports (implement interfaces)

---

## Configuration Management

### Environment Variables (Lambda)

The Lambda function uses these environment variables:

```bash
SCAN_REGIONS="us-east-1,us-west-2,eu-west-1"
ASSUME_ROLE_NAME="PerimeterGuardScanRole"
TARGET_ACCOUNTS="111111111111,222222222222"
OUTPUT_TYPE="cloudwatch"
```

**Configuration in Code**:
```python
import os
from typing import List

class Config:
    """Application configuration from environment."""
    
    @staticmethod
    def get_scan_regions() -> List[str]:
        regions = os.getenv('SCAN_REGIONS', '')
        return [r.strip() for r in regions.split(',') if r.strip()]
    
    @staticmethod
    def get_target_accounts() -> List[str]:
        accounts = os.getenv('TARGET_ACCOUNTS', '')
        return [a.strip() for a in accounts.split(',') if a.strip()]
    
    @staticmethod
    def get_assume_role_name() -> str:
        return os.getenv('ASSUME_ROLE_NAME', 'PerimeterGuardScanRole')
```

### CLI Configuration

Use Click for CLI with environment variable fallbacks:

```python
import click

@click.command()
@click.option('--regions', '-r', 
              multiple=True,
              envvar='AWS_REGIONS',
              help='Regions to scan (can specify multiple)')
@click.option('--output', '-o',
              type=click.Choice(['csv', 'stdout']),
              default='csv',
              help='Output format')
@click.option('--file', '-f',
              type=click.Path(),
              help='Output file path (for CSV)')
def scan(regions, output, file):
    """Scan AWS resources for WAF associations."""
    pass
```

---

## Multi-Account Implementation

### Terraform Variable Pattern

**Key variable**: `allow_multiaccount_through_iam_role` (boolean)

- `false` = Deploy Lambda + EventBridge + IAM role (central/single account)
- `true` = Deploy IAM role only (target account)

**Example Deployment**:

```bash
# Central account
cd terraform
cat > terraform.tfvars <<EOF
allow_multiaccount_through_iam_role = false
target_accounts = "111111111111,222222222222"
EOF
terraform apply

# Target account 1
export AWS_PROFILE=target-account-1
cat > terraform.tfvars <<EOF
allow_multiaccount_through_iam_role = true
central_lambda_role_arn = "arn:aws:iam::123456789012:role/PerimeterGuardLambdaRole"
EOF
terraform apply
```

### Cross-Account Scanning Logic

```python
def scan_multiple_accounts(
    target_accounts: List[str],
    assume_role_name: str,
    regions: List[str]
) -> List[ScanResult]:
    """Scan multiple AWS accounts via role assumption."""
    results = []
    
    for account_id in target_accounts:
        try:
            # Assume role
            session = assume_role(account_id, assume_role_name)
            
            # Scan with assumed credentials
            result = scan_account(
                account_id=account_id,
                regions=regions,
                session=session
            )
            results.append(result)
            
        except Exception as e:
            logger.error(f"Failed to scan account {account_id}: {e}")
            # Continue with other accounts
    
    return results
```

---

## Testing Strategy

### Unit Tests (Fast, Isolated)

```python
# tests/unit/test_domain/test_scan_result.py
from src.domain.entities.scan_result import ScanResult
from src.domain.entities.resource import Resource

def test_scan_result_calculates_compliance_rate():
    resources = [
        Resource(has_waf=True),
        Resource(has_waf=False),
        Resource(has_waf=True),
    ]
    
    result = ScanResult(resources=resources)
    
    assert result.compliance_rate == 66.67
    assert result.compliant_count == 2
    assert result.non_compliant_count == 1
```

### Integration Tests (With Moto)

```python
# tests/integration/test_waf_scanning.py
import boto3
from moto import mock_wafv2, mock_elbv2
from src.adapters.outbound.boto3_waf_client import Boto3WafClient

@mock_wafv2
@mock_elbv2
def test_full_waf_scanning_flow():
    # Setup mock AWS resources
    wafv2 = boto3.client('wafv2', region_name='us-east-1')
    wafv2.create_web_acl(Name='TestWAF', Scope='REGIONAL', ...)
    
    elbv2 = boto3.client('elbv2', region_name='us-east-1')
    elbv2.create_load_balancer(Name='test-alb', ...)
    
    # Test scanning
    client = Boto3WafClient()
    resources = client.list_albs('us-east-1')
    waf_associations = client.check_waf_associations(resources)
    
    assert len(resources) == 1
    assert resources[0].has_waf is True
```

### Test Fixtures

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_aws_client():
    """Mock AWS client port."""
    client = Mock()
    client.list_web_acls.return_value = []
    client.list_albs.return_value = []
    return client

@pytest.fixture
def sample_resource():
    """Sample resource for testing."""
    return Resource(
        arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/abc123",
        resource_type=ResourceType.ALB,
        region="us-east-1",
        account_id="123456789012"
    )
```

---

## Development Workflow

### Step-by-Step Process

1. **Read Task Documentation**
   ```bash
   cat docs/tasks/task-XX-*.md
   ```

2. **Write Test First (TDD)**
   ```python
   # tests/unit/test_feature.py
   def test_new_feature():
       # Arrange
       input_data = ...
       
       # Act
       result = my_function(input_data)
       
       # Assert
       assert result == expected_output
   ```

3. **Run Test (Should Fail)**
   ```bash
   pytest tests/unit/test_feature.py -v
   ```

4. **Implement Feature**
   ```python
   # src/module/feature.py
   def my_function(input_data):
       # Implementation
       return output
   ```

5. **Run Test (Should Pass)**
   ```bash
   pytest tests/unit/test_feature.py -v
   ```

6. **Refactor**
   - Improve code quality
   - Add type hints
   - Extract functions
   - Update docstrings

7. **Run All Tests**
   ```bash
   pytest tests/ -v --cov=src --cov-report=term-missing
   ```

8. **Check Types**
   ```bash
   mypy src/
   ```

9. **Format Code**
   ```bash
   black src/ tests/
   ```

10. **Commit**
    ```bash
    git add .
    git commit -m "feat: implement feature X (task-Y)"
    ```

### Makefile Commands

```makefile
.PHONY: test
test:
	pytest tests/ -v

.PHONY: test-cov
test-cov:
	pytest tests/ -v --cov=src --cov-report=html

.PHONY: type-check
type-check:
	mypy src/

.PHONY: format
format:
	black src/ tests/
	isort src/ tests/

.PHONY: lint
lint:
	pylint src/
	flake8 src/

.PHONY: all-checks
all-checks: format type-check lint test-cov
```

---

## Best Practices Checklist

### Before Writing Code
- [ ] Read relevant task documentation
- [ ] Understand the interface/contract
- [ ] Write test cases first (TDD)
- [ ] Consider edge cases

### While Writing Code
- [ ] Add type hints to all functions
- [ ] Write docstrings (Google style)
- [ ] Validate input at boundaries (CLI, Lambda)
- [ ] Handle errors gracefully
- [ ] Keep functions small and focused
- [ ] Favor simplicity over patterns

### After Writing Code
- [ ] All tests pass
- [ ] Type checking passes (mypy)
- [ ] Code is formatted (black)
- [ ] Coverage >80% for new code
- [ ] Documentation updated
- [ ] Commit with descriptive message

### Code Review Checklist
- [ ] Follows hexagonal architecture
- [ ] Proper dependency direction (inward)
- [ ] No business logic in adapters
- [ ] Tests are isolated and fast
- [ ] Error messages are clear
- [ ] No hardcoded values

---

## Common Patterns

### Dependency Injection

```python
# Good: Dependencies injected
class ScannerService:
    def __init__(
        self,
        aws_client: AWSClientPort,
        output: OutputPort,
        logger: LoggerPort
    ):
        self.aws_client = aws_client
        self.output = output
        self.logger = logger

# Usage
service = ScannerService(
    aws_client=Boto3WafClient(),
    output=CsvExporter(),
    logger=ConsoleLogger()
)
```

### Error Handling

```python
from typing import Union, List
from dataclasses import dataclass

@dataclass
class Success:
    data: List[Resource]

@dataclass
class Failure:
    error: str

Result = Union[Success, Failure]

def scan_region(region: str) -> Result:
    try:
        resources = aws_client.list_resources(region)
        return Success(data=resources)
    except ClientError as e:
        return Failure(error=f"Failed to scan {region}: {e}")
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

def scan_account(account_id: str):
    logger.info("Starting scan", extra={
        "account_id": account_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    try:
        # Scan logic
        logger.info("Scan complete", extra={
            "account_id": account_id,
            "resources_found": len(resources)
        })
    except Exception as e:
        logger.error("Scan failed", extra={
            "account_id": account_id,
            "error": str(e)
        }, exc_info=True)
```

---

## Quick Reference

### File Locations
- **Implementation Plan**: `docs/implementation-plan.md`
- **Summary**: `docs/IMPLEMENTATION_SUMMARY.md`
- **Tasks**: `docs/tasks/task-*.md`
- **Updates Log**: `docs/UPDATES_SUMMARY.md`
- **This Guide**: `docs/DEVELOPMENT_GUIDE.md`

### Key Decisions
- **Package Manager**: uv/pip (requirements.txt)
- **Output Format**: CSV primary, CloudWatch for Lambda
- **Multi-Account**: Manual Terraform per account
- **No StackSets**: Simple Terraform with boolean variable
- **Supported Resources**: 8 types (ALB, CloudFront, API GW, AppSync, Cognito, App Runner, Verified Access, Amplify)

### Next Steps
1. Read `docs/IMPLEMENTATION_SUMMARY.md`
2. Review `docs/implementation-plan.md`
3. Start with Task 1: Project setup
4. Follow TDD process
5. Build incrementally, test continuously

---

## Getting Help

When stuck:
1. Re-read the task documentation
2. Check `docs/implementation-plan.md` for context
3. Review similar implementations in other tasks
4. Test assumptions with small experiments
5. Ask specific questions with context

Remember: **The documentation is your source of truth. Always start there.**
