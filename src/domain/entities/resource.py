"""Resource entity representing an AWS resource that can have WAF protection."""
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.entities.web_acl import WebACL
from src.domain.value_objects.resource_type import ResourceType


@dataclass
class Resource:
    """Represents an AWS resource that can have WAF protection."""

    arn: str
    resource_type: ResourceType
    region: str
    account_id: str
    name: str | None = None

    # WAF association
    web_acl: WebACL | None = None

    # Fronted-by relationship (for resources behind CloudFront)
    fronted_by_resource_arn: str | None = None
    fronted_by_waf: WebACL | None = None
    fronted_by_notes: str | None = None

    # Metadata
    is_public: bool = False
    tags: dict = field(default_factory=dict)
    scanned_at: datetime | None = None

    def has_waf(self) -> bool:
        """Check if resource has WAF associated."""
        return self.web_acl is not None

    def get_waf_arn(self) -> str | None:
        """Get the ARN of the associated WAF, if any."""
        return self.web_acl.arn if self.web_acl else None

    def get_waf_name(self) -> str | None:
        """Get the name of the associated WAF, if any."""
        return self.web_acl.name if self.web_acl else None

    def is_compliant(self) -> bool:
        """
        Check if resource is compliant with WAF policy.

        Rules:
        - Public resources should have WAF (direct or via CloudFront fronting)
        - CloudFront distributions should have WAF
        - Resources fronted by CloudFront with WAF are compliant
        """
        if self.has_waf():
            return True

        if self.fronted_by_waf:
            return True

        if self.resource_type == ResourceType.CLOUDFRONT:
            return False

        if self.resource_type == ResourceType.ALB and self.is_public:
            return False

        if self.resource_type == ResourceType.API_GATEWAY_REST and self.is_public:
            return False

        if self.resource_type == ResourceType.API_GATEWAY_HTTP:
            return True

        return True

    def get_compliance_status(self) -> str:
        """Get a human-readable compliance status."""
        if self.has_waf():
            return "COMPLIANT"

        if self.fronted_by_waf:
            return "COMPLIANT_FRONTED_BY_WAF"

        if not self.is_compliant():
            return "NON_COMPLIANT"

        return "COMPLIANT_NO_WAF_REQUIRED"

    def __str__(self) -> str:
        waf_status = "✓ WAF" if self.has_waf() else "✗ No WAF"
        name_str = self.name or "unnamed"
        return f"Resource({self.resource_type.value}, {name_str}, {waf_status})"
