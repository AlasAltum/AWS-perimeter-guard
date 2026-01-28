# Task 1: Project Structure & Dependencies Setup

## Objective
Establish the foundational project structure following hexagonal architecture principles and configure Python dependency management using uv/pip (simple requirements.txt).

## Dependencies
None (initial task)

## Deliverables

### 1. Directory Structure
```
AWS-perimeter-guard/
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities/
│   │   └── value_objects/
│   ├── application/
│   │   └── __init__.py
│   ├── ports/
│   │   ├── __init__.py
│   │   └── outbound/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── inbound/
│   │   └── outbound/
│   └── main.py
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── tests/
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── docs/
│   ├── tasks/
│   ├── architecture.md
│   └── multi-account-setup.md
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── Makefile
├── README.md
└── LICENSE
```

## Key Components

### requirements.txt
```txt
boto3>=1.34.0
pydantic>=2.5.0
click>=8.1.7
```

**Key Points**:
- **boto3**: AWS SDK for Python
- **pydantic**: Data validation and settings management with type safety
- **click**: CLI framework with decorator-based commands
- **Simple dependencies**: Easy `pip install -r requirements.txt`

### requirements-dev.txt
```txt
pytest>=7.4.3
pytest-cov>=4.1.0
moto[all]>=4.2.0
black>=23.12.0
mypy>=1.7.0
boto3-stubs[wafv2,elbv2,cloudfront,apigateway]>=1.34.0
ruff>=0.1.8
```

**Key Points**:
- **pytest**: Testing framework
- **moto**: AWS service mocking for testing without real AWS calls
- **black + ruff**: Code formatting and linting
- **mypy**: Type checking
- **boto3-stubs**: Type hints for boto3 (IDE autocomplete)

### .gitignore
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv
pip-log.txt
pip-delete-this-directory.txt
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Terraform
.terraform/
*.tfstate
*.tfstate.backup
.terraform.lock.hcl
terraform.tfvars

# OS
.DS_Store
Thumbs.db

# Project specific
results.csv
scan-results/
*.log
.env
```

### Makefile
```makefile
.PHONY: help install test lint format clean

help:
	@echo "Available targets:"
	@echo "  install    - Install dependencies using uv/pip"
	@echo "  test       - Run tests with coverage"
	@echo "  lint       - Run linters (mypy, ruff)"
	@echo "  format     - Format code with black"
	@echo "  clean      - Remove generated files"

install:
	uv pip install -r requirements.txt
	uv pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	mypy src/
	ruff check src/ tests/

format:
	black src/ tests/
	ruff check --fix src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov/ dist/ build/

run-cli:
	python -m src.main scan --help
```

**Key Points**:
- **Consistent commands**: Developers use the same commands across environments
- **Test coverage**: Ensures quality gate of >80% coverage
- **Type checking**: mypy enforces strict typing
- **Code formatting**: black + ruff for consistent style
- **Simple uv/pip**: No Poetry-specific commands

### requirements.txt (for Lambda packaging)
Same as the main requirements.txt since we're using pip:
```txt
boto3>=1.34.0
pydantic>=2.5.0
click>=8.1.7
```

**Why this works for Lambda?**
- Lambda requires a flat dependency list
- With pip, we use the same file for development and production
- Package with: `uv pip install -r requirements.txt -t lambda-package/`

## Hexagonal Architecture Layers

### Domain Layer (`src/domain/`)
- **Purpose**: Core business entities and rules
- **Dependencies**: None (pure Python)
- **Example**: `Resource`, `WebACL`, `ScanResult` entities

### Application Layer (`src/application/`)
- **Purpose**: Use cases and orchestration logic
- **Dependencies**: Domain layer + Port interfaces
- **Example**: `ScannerService`, `MultiAccountScanner`

### Ports Layer (`src/ports/`)
- **Purpose**: Abstract interfaces (contracts)
- **Dependencies**: Domain layer only
- **Example**: `AWSClientPort`, `OutputPort`, `LoggerPort`

### Adapters Layer (`src/adapters/`)
- **Purpose**: Concrete implementations of ports
- **Dependencies**: Ports + external libraries (boto3, csv, etc.)
- **Example**: `Boto3WafClient`, `CsvExporter`, `CliAdapter`

## Code Structure Benefits

1. **Testability**: Domain logic tested without AWS dependencies (mocked ports)
2. **Flexibility**: Swap output formats (CSV → JSON → CloudWatch) without touching core logic
3. **Maintainability**: Clear boundaries between layers
4. **Extensibility**: Add new resource types or output adapters independently

## Next Steps
Proceed to Task 2: Domain Model Implementation once this structure is in place.
