# Task 2: Domain Model Implementation

## Objective
Create the core domain entities and value objects that represent AWS resources, WAF configurations, and scan results using Pydantic for validation and type safety.

## Dependencies
- Task 1: Project structure must be in place

## Deliverables

### 1. Resource Type Value Object
**File**: `src/domain/value_objects/resource_type.py`

```python
from enum import Enum

class ResourceType(str, Enum):
    """AWS resource types that support WAF association."""
    
    ALB = "APPLICATION_LOAD_BALANCER"
    CLOUDFRONT = "CLOUDFRONT_DISTRIBUTION"
    API_GATEWAY_REST = "API_GATEWAY_REST_API"
    API_GATEWAY_HTTP = "API_GATEWAY_HTTP_API"
    APPSYNC = "APPSYNC_GRAPHQL_API"
    COGNITO = "COGNITO_USER_POOL"
    APP_RUNNER = "APP_RUNNER_SERVICE"
    VERIFIED_ACCESS = "VERIFIED_ACCESS_INSTANCE"
    
    @property
    def waf_resource_type(self) -> str:
        """Return the WAFv2 API resource type string."""
        return self.value
    
    @property
    def is_cloudfront_scope(self) -> bool:
        """Check if resource uses CLOUDFRONT scope in WAFv2."""
        return self in [ResourceType.CLOUDFRONT]
    
    @property
    def aws_service(self) -> str:
        """Return the AWS service name for this resource."""
        mapping = {
            ResourceType.ALB: "elasticloadbalancing",
            ResourceType.CLOUDFRONT: "cloudfront",
            ResourceType.API_GATEWAY_REST: "apigateway",
            ResourceType.API_GATEWAY_HTTP: "apigateway",
            ResourceType.APPSYNC: "appsync",
            ResourceType.COGNITO: "cognito-idp",
            ResourceType.APP_RUNNER: "apprunner",
            ResourceType.VERIFIED_ACCESS: "ec2"
        }
        return mapping[self]
```

**Key Points**:
- **Enum for type safety**: Prevents invalid resource types
- **WAFv2 scope distinction**: `CLOUDFRONT` vs `REGIONAL` scope
- **Service mapping**: Maps to AWS service names for ARN construction

---

### 2. Resource ARN Value Object
**File**: `src/domain/value_objects/resource_arn.py`

```python
import re
from typing import Optional
from pydantic import BaseModel, field_validator

class ResourceArn(BaseModel):
    """Immutable AWS Resource ARN with validation."""
    
    value: str
    
    @field_validator('value')
    @classmethod
    def validate_arn_format(cls, v: str) -> str:
        """Validate ARN format: arn:partition:service:region:account:resource"""
        arn_pattern = r'^arn:aws:[\w-]+:[\w-]*:\d{12}:.+$'
        if not re.match(arn_pattern, v):
            raise ValueError(f"Invalid ARN format: {v}")
        return v
    
    @property
    def partition(self) -> str:
        return self.value.split(':')[1]
    
    @property
    def service(self) -> str:
        return self.value.split(':')[2]
    
    @property
    def region(self) -> str:
        return self.value.split(':')[3]
    
    @property
    def account_id(self) -> str:
        return self.value.split(':')[4]
    
    @property
    def resource(self) -> str:
        return ':'.join(self.value.split(':')[5:])
    
    def __str__(self) -> str:
        return self.value
    
    def __hash__(self) -> int:
        return hash(self.value)
    
    class Config:
        frozen = True  # Immutable
```

**Key Points**:
- **Immutability**: `frozen = True` prevents modification
- **Validation**: Ensures ARN format correctness at creation
- **Convenience properties**: Extract ARN components without string splitting
- **Hashable**: Can be used in sets and dict keys

---

### 3. WebACL Entity
**File**: `src/domain/entities/web_acl.py`

```python
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class WebACL(BaseModel):
    """Represents an AWS WAFv2 Web ACL."""
    
    arn: str
    id: str
    name: str
    scope: str = Field(..., pattern="^(REGIONAL|CLOUDFRONT)$")
    region: str
    description: Optional[str] = None
    capacity: Optional[int] = None
    managed_by_firewall_manager: bool = False
    logging_enabled: bool = False
    
    created_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    
    def is_global(self) -> bool:
        """Check if this is a global (CloudFront) WAF."""
        return self.scope == "CLOUDFRONT"
    
    def is_managed(self) -> bool:
        """Check if managed by AWS Firewall Manager."""
        return self.managed_by_firewall_manager
    
    def __str__(self) -> str:
        return f"WebACL({self.name}, {self.scope}, {self.region})"
    
    class Config:
        frozen = False  # Mutable (can update logging status)
```

**Key Points**:
- **Scope validation**: Ensures only valid WAF scopes
- **Metadata tracking**: Created/updated timestamps for auditing
- **Business logic**: Domain methods like `is_global()`, `is_managed()`

---

### 4. Resource Entity
**File**: `src/domain/entities/resource.py`

```python
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from src.domain.value_objects.resource_type import ResourceType
from src.domain.value_objects.resource_arn import ResourceArn
from src.domain.entities.web_acl import WebACL

class Resource(BaseModel):
    """Represents an AWS resource that can have WAF protection."""
    
    arn: ResourceArn
    resource_type: ResourceType
    region: str
    account_id: str
    name: Optional[str] = None
    
    # WAF association
    waf_acl: Optional[WebACL] = None
    waf_checked_at: Optional[datetime] = None
    
    # Resource-specific metadata
    is_public: bool = False  # For ALBs
    custom_domain: Optional[str] = None  # For CloudFront, API Gateway
    
    def has_waf(self) -> bool:
        """Check if resource has WAF associated."""
        return self.waf_acl is not None
    
    def is_compliant(self, require_waf: bool = True) -> bool:
        """
        Check compliance based on policy.
        
        Args:
            require_waf: Whether WAF is required for this resource type
        
        Returns:
            True if compliant, False otherwise
        """
        if not require_waf:
            return True
        
        # Public resources must have WAF
        if self.is_public and not self.has_waf():
            return False
        
        # CloudFront should always have WAF
        if self.resource_type == ResourceType.CLOUDFRONT and not self.has_waf():
            return False
        
        return True
    
    def get_compliance_reason(self, require_waf: bool = True) -> Optional[str]:
        """Get reason for non-compliance."""
        if self.is_compliant(require_waf):
            return None
        
        if self.is_public and not self.has_waf():
            return "Public resource without WAF protection"
        
        if self.resource_type == ResourceType.CLOUDFRONT and not self.has_waf():
            return "CloudFront distribution without WAF protection"
        
        if require_waf and not self.has_waf():
            return "WAF protection required but not configured"
        
        return "Unknown compliance issue"
    
    def __str__(self) -> str:
        waf_status = "✓ WAF" if self.has_waf() else "✗ No WAF"
        return f"Resource({self.resource_type.value}, {self.name or 'unnamed'}, {waf_status})"
    
    class Config:
        arbitrary_types_allowed = True  # Allow ResourceArn custom type
```

**Key Points**:
- **Rich domain behavior**: Business rules encoded in entity methods
- **Compliance logic**: Centralized policy enforcement
- **Type safety**: Pydantic validates all fields at creation
- **Extensibility**: Easy to add new compliance rules

---

### 5. ScanResult Aggregate Root
**File**: `src/domain/entities/scan_result.py`

```python
from typing import List, Dict
from datetime import datetime
from pydantic import BaseModel, Field

from src.domain.entities.resource import Resource

class ScanResult(BaseModel):
    """
    Aggregate root representing the result of a WAF perimeter scan.
    This is the main entity returned by the scanner service.
    """
    
    scan_id: str = Field(..., description="Unique identifier for this scan")
    scan_started_at: datetime
    scan_completed_at: Optional[datetime] = None
    
    # Account information
    account_id: str
    organization_id: Optional[str] = None
    
    # Scan scope
    regions_scanned: List[str] = Field(default_factory=list)
    resource_types_scanned: List[str] = Field(default_factory=list)
    
    # Results
    resources: List[Resource] = Field(default_factory=list)
    
    # Summary statistics
    total_resources: int = 0
    resources_with_waf: int = 0
    resources_without_waf: int = 0
    compliant_resources: int = 0
    non_compliant_resources: int = 0
    
    # Errors encountered
    errors: List[Dict[str, str]] = Field(default_factory=list)
    
    def add_resource(self, resource: Resource) -> None:
        """Add a resource to scan results and update statistics."""
        self.resources.append(resource)
        self.total_resources += 1
        
        if resource.has_waf():
            self.resources_with_waf += 1
        else:
            self.resources_without_waf += 1
        
        if resource.is_compliant():
            self.compliant_resources += 1
        else:
            self.non_compliant_resources += 1
    
    def add_error(self, region: str, error_message: str) -> None:
        """Record an error encountered during scanning."""
        self.errors.append({
            "region": region,
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
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
    
    def get_non_compliant_resources(self) -> List[Resource]:
        """Get list of non-compliant resources."""
        return [r for r in self.resources if not r.is_compliant()]
    
    def get_resources_by_type(self, resource_type: str) -> List[Resource]:
        """Get resources filtered by type."""
        return [r for r in self.resources if r.resource_type.value == resource_type]
    
    def complete_scan(self) -> None:
        """Mark scan as completed."""
        self.scan_completed_at = datetime.utcnow()
    
    def __str__(self) -> str:
        return (
            f"ScanResult(account={self.account_id}, "
            f"resources={self.total_resources}, "
            f"compliance={self.get_compliance_rate():.1f}%)"
        )
```

**Key Points**:
- **Aggregate root**: Owns the Resource entities lifecycle
- **Encapsulation**: Statistics updated automatically via `add_resource()`
- **Rich queries**: Methods to analyze scan results
- **Domain invariants**: Guarantees consistency of statistics

---

## Domain Model Benefits

### 1. Type Safety
```python
# This will raise a validation error
resource = Resource(
    arn="invalid-arn",  # ❌ Pydantic validates ARN format
    resource_type="UNKNOWN",  # ❌ Must be valid ResourceType enum
)
```

### 2. Business Logic Centralization
```python
# Compliance logic lives in the domain
if resource.is_compliant():
    print(f"{resource.name} is compliant")
else:
    print(f"Issue: {resource.get_compliance_reason()}")
```

### 3. Immutability Where Needed
```python
arn = ResourceArn(value="arn:aws:elasticloadbalancing:...")
arn.value = "different"  # ❌ Raises error (frozen=True)
```

### 4. Clear Contracts
```python
# Type hints ensure compile-time checking
def process_results(results: ScanResult) -> Dict[str, float]:
    return {
        "compliance_rate": results.get_compliance_rate(),
        "waf_coverage": results.get_waf_coverage_rate()
    }
```

## Testing the Domain Model

```python
# tests/unit/domain/test_resource.py
import pytest
from src.domain.entities.resource import Resource
from src.domain.value_objects.resource_type import ResourceType
from src.domain.value_objects.resource_arn import ResourceArn

def test_resource_without_waf_is_non_compliant():
    resource = Resource(
        arn=ResourceArn(value="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-alb/1234"),
        resource_type=ResourceType.ALB,
        region="us-east-1",
        account_id="123456789012",
        is_public=True,
        waf_acl=None
    )
    
    assert not resource.has_waf()
    assert not resource.is_compliant()
    assert "without WAF" in resource.get_compliance_reason()

def test_resource_with_waf_is_compliant():
    # ... test implementation
```

**Key Points**:
- Domain tests don't need AWS mocking
- Pure Python logic testing
- Fast execution (no I/O)

## Next Steps
Proceed to Task 3: Define port interfaces that will use these domain entities.
