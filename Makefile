.PHONY: help install install-dev test test-cov type-check format lint clean all-checks

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install runtime dependencies
	uv pip install -r requirements.txt

install-dev: ## Install development dependencies
	uv pip install -r requirements-dev.txt

test: ## Run tests
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

type-check: ## Run type checking with mypy
	mypy src/ --strict

format: ## Format code with black and ruff
	black src/ tests/
	ruff check --fix src/ tests/

lint: ## Run linting
	ruff check src/ tests/
	pylint src/

clean: ## Clean up generated files
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf build/ dist/ *.egg-info/

all-checks: format type-check lint test-cov ## Run all checks (format, type-check, lint, test)
