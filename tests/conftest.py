"""Test configuration and shared fixtures."""
import pytest


@pytest.fixture
def sample_account_id() -> str:
    """Sample AWS account ID for testing."""
    return "123456789012"


@pytest.fixture
def sample_region() -> str:
    """Sample AWS region for testing."""
    return "us-east-1"
