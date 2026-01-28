"""AWS Perimeter Guard - WAF Association Scanner.

A DevOps utility to scan AWS resources and report on their WAF associations.
"""

__version__ = "0.1.0"

# Domain layer
# Application layer
from src.application import ScannerService, create_scanner
from src.domain import Resource, ResourceType, ScanResult, WebACL

# Re-export for convenience
__all__ = [
    "__version__",
    # Domain
    "WebACL",
    "Resource",
    "ScanResult",
    "ResourceType",
    # Application
    "ScannerService",
    "create_scanner",
]
