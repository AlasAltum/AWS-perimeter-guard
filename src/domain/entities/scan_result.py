"""ScanResult aggregate root representing the result of a WAF perimeter scan."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.entities.resource import Resource
from src.domain.value_objects.resource_type import ResourceType


@dataclass
class ScanResult:
    """
    Aggregate root representing the result of a WAF perimeter scan.
    This is the main entity returned by the scanner service.
    """

    account_id: str
    regions_scanned: list[str] = field(default_factory=list)

    scan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    scan_started_at: datetime = field(default_factory=datetime.utcnow)
    scan_completed_at: datetime | None = None

    resources: list[Resource] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def add_resource(self, resource: Resource) -> None:
        """Add a resource to scan results."""
        resource.scanned_at = datetime.utcnow()
        self.resources.append(resource)

    def add_error(self, region: str, error_message: str, resource_type: str | None = None) -> None:
        """Record an error encountered during scanning."""
        self.errors.append({
            "region": region,
            "resource_type": resource_type,
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def complete(self) -> None:
        """Mark scan as completed."""
        self.scan_completed_at = datetime.utcnow()

    # Statistics

    @property
    def total_resources(self) -> int:
        """Total number of resources scanned."""
        return len(self.resources)

    @property
    def resources_with_waf(self) -> int:
        """Number of resources with WAF associated."""
        return sum(1 for r in self.resources if r.has_waf())

    @property
    def resources_without_waf(self) -> int:
        """Number of resources without WAF associated."""
        return sum(1 for r in self.resources if not r.has_waf())

    @property
    def compliant_resources(self) -> int:
        """Number of compliant resources."""
        return sum(1 for r in self.resources if r.is_compliant())

    @property
    def non_compliant_resources(self) -> int:
        """Number of non-compliant resources."""
        return sum(1 for r in self.resources if not r.is_compliant())

    def get_compliance_rate(self) -> float:
        """Calculate compliance percentage."""
        if self.total_resources == 0:
            return 100.0
        return (self.compliant_resources / self.total_resources) * 100

    def get_waf_coverage_rate(self) -> float:
        """Calculate WAF coverage percentage."""
        if self.total_resources == 0:
            return 0.0
        return (self.resources_with_waf / self.total_resources) * 100

    # Query methods

    def get_non_compliant_resources(self) -> list[Resource]:
        """Get list of non-compliant resources."""
        return [r for r in self.resources if not r.is_compliant()]

    def get_resources_without_waf(self) -> list[Resource]:
        """Get list of resources without WAF."""
        return [r for r in self.resources if not r.has_waf()]

    def get_resources_by_type(self, resource_type: ResourceType) -> list[Resource]:
        """Get resources filtered by type."""
        return [r for r in self.resources if r.resource_type == resource_type]

    def get_resources_by_region(self, region: str) -> list[Resource]:
        """Get resources filtered by region."""
        return [r for r in self.resources if r.region == region]

    def has_errors(self) -> bool:
        """Check if any errors occurred during scanning."""
        return len(self.errors) > 0

    def __str__(self) -> str:
        return (
            f"ScanResult(account={self.account_id}, "
            f"resources={self.total_resources}, "
            f"waf_coverage={self.get_waf_coverage_rate():.1f}%)"
        )
