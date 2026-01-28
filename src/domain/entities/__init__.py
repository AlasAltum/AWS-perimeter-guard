"""Domain entities for the AWS Perimeter Guard."""
from src.domain.entities.resource import Resource
from src.domain.entities.scan_result import ScanResult
from src.domain.entities.web_acl import WebACL

__all__ = ["WebACL", "Resource", "ScanResult"]
