"""WebACL entity representing an AWS WAFv2 Web ACL."""
from dataclasses import dataclass


@dataclass
class WebACL:
    """Represents an AWS WAFv2 Web ACL."""

    arn: str
    name: str
    id: str
    scope: str  # "REGIONAL" or "CLOUDFRONT"
    region: str

    description: str | None = None
    managed_by_firewall_manager: bool = False

    def is_global(self) -> bool:
        """Check if this is a global (CloudFront) WAF."""
        return self.scope == "CLOUDFRONT"

    def is_regional(self) -> bool:
        """Check if this is a regional WAF."""
        return self.scope == "REGIONAL"

    def __str__(self) -> str:
        return f"WebACL({self.name}, {self.scope})"
