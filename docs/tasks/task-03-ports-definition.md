# Task 3: Port Interfaces Definition

## Objective
Define abstract interfaces (ports) that separate the application core from external dependencies, enabling hexagonal architecture's dependency inversion principle.

## Dependencies
- Task 2: Domain model entities must exist

## Deliverables

### 1. AWS Client Port (Outbound)
**File**: `src/ports/outbound/aws_client_port.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from src.domain.entities.resource import Resource
from src.domain.entities.web_acl import WebACL
from src.domain.value_objects.resource_type import ResourceType

class AWSClientPort(ABC):
    """
    Port for AWS service interactions.
    Abstracts boto3 operations for WAF and resource discovery.
    """
    
    @abstractmethod
    def list_web_acls(self, region: str, scope: str) -> List[WebACL]:
        """
        List all Web ACLs in a region.
        
        Args:
            region: AWS region (e.g., 'us-east-1')
            scope: 'REGIONAL' or 'CLOUDFRONT'
        
        Returns:
            List of WebACL entities
        """
        pass
    
    @abstractmethod
    def get_web_acl_for_resource(self, resource_arn: str, region: str) -> Optional[WebACL]:
        """
        Get the Web ACL associated with a specific resource.
        
        Args:
            resource_arn: ARN of the resource
            region: AWS region
        
        Returns:
            WebACL if associated, None otherwise
        """
        pass
    
    @abstractmethod
    def list_resources_by_type(
        self, 
        resource_type: ResourceType, 
        region: str,
        account_id: str
    ) -> List[Resource]:
        """
        List all resources of a specific type in a region.
        
        Args:
            resource_type: Type of resource to list
            region: AWS region
            account_id: AWS account ID
        
        Returns:
            List of Resource entities (without WAF info populated)
        """
        pass
    
    @abstractmethod
    def assume_role(self, account_id: str, role_name: str) -> 'AWSClientPort':
        """
        Create a new client with assumed role credentials.
        
        Args:
            account_id: Target account ID
            role_name: IAM role name to assume
        
        Returns:
            New AWSClientPort instance with assumed credentials
        """
        pass
    
    @abstractmethod
    def list_organization_accounts(self) -> List[Dict[str, str]]:
        """
        List all accounts in AWS Organization.
        
        Returns:
            List of dicts with 'id', 'name', 'status' keys
        """
        pass
```

**Key Points**:
- **ABC (Abstract Base Class)**: Enforces implementation contract
- **Domain types**: Uses domain entities (Resource, WebACL) not AWS SDK types
- **Testability**: Easy to create mock implementations for testing
- **Flexibility**: Can swap boto3 for LocalStack, moto, or custom implementation

---

### 2. Output Port (Outbound)
**File**: `src/ports/outbound/output_port.py`

```python
from abc import ABC, abstractmethod
from src.domain.entities.scan_result import ScanResult

class OutputPort(ABC):
    """
    Port for exporting scan results.
    Enables multiple output formats without changing core logic.
    """
    
    @abstractmethod
    def export(self, scan_result: ScanResult) -> None:
        """
        Export scan results to destination.
        
        Args:
            scan_result: Complete scan result to export
        
        Raises:
            ExportError: If export fails
        """
        pass
    
    @abstractmethod
    def get_format_name(self) -> str:
        """
        Get human-readable format name.
        
        Returns:
            Format name (e.g., "CSV", "CloudWatch Logs", "JSON")
        """
        pass
    
    @abstractmethod
    def supports_streaming(self) -> bool:
        """
        Check if adapter supports streaming results.
        
        Returns:
            True if results can be exported incrementally
        """
        pass
```

**Key Points**:
- **Simple interface**: Single responsibility (export)
- **Format agnostic**: Works with any output destination
- **Metadata methods**: Help with adapter selection and logging

---

### 3. Logger Port (Outbound)
**File**: `src/ports/outbound/logger_port.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LoggerPort(ABC):
    """
    Port for logging operations.
    Abstracts logging implementation (console, CloudWatch, file).
    """
    
    @abstractmethod
    def log(
        self, 
        level: LogLevel, 
        message: str, 
        extra: Dict[str, Any] = None
    ) -> None:
        """
        Log a message with optional structured data.
        
        Args:
            level: Log severity level
            message: Log message
            extra: Additional structured data (for CloudWatch structured logs)
        """
        pass
    
    def debug(self, message: str, **kwargs) -> None:
        self.log(LogLevel.DEBUG, message, kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        self.log(LogLevel.INFO, message, kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        self.log(LogLevel.WARNING, message, kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        self.log(LogLevel.ERROR, message, kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        self.log(LogLevel.CRITICAL, message, kwargs)
```

**Key Points**:
- **Structured logging**: Supports key-value pairs for CloudWatch Insights
- **Convenience methods**: `debug()`, `info()`, etc. for cleaner code
- **Adapter flexibility**: Console, CloudWatch, or custom destinations

---

### 4. Scanner Port (Inbound)
**File**: `src/ports/inbound/scanner_port.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.entities.scan_result import ScanResult

class ScanRequest:
    """Request object for scanner operations."""
    
    def __init__(
        self,
        account_id: Optional[str] = None,
        regions: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        organization_scan: bool = False,
        organization_id: Optional[str] = None,
        assume_role_name: Optional[str] = None
    ):
        self.account_id = account_id
        self.regions = regions or []
        self.resource_types = resource_types or []
        self.organization_scan = organization_scan
        self.organization_id = organization_id
        self.assume_role_name = assume_role_name

class ScannerPort(ABC):
    """
    Port for scanner operations (use cases).
    Defines the application's external API.
    """
    
    @abstractmethod
    def scan_account(self, request: ScanRequest) -> ScanResult:
        """
        Scan a single AWS account for resources and WAF associations.
        
        Args:
            request: Scan configuration
        
        Returns:
            Complete scan results
        """
        pass
    
    @abstractmethod
    def scan_organization(self, request: ScanRequest) -> List[ScanResult]:
        """
        Scan all accounts in AWS Organization.
        
        Args:
            request: Scan configuration
        
        Returns:
            List of scan results (one per account)
        """
        pass
```

**Key Points**:
- **Inbound port**: Defines how external actors use the application
- **Use case oriented**: Methods represent business operations
- **DTO pattern**: `ScanRequest` encapsulates parameters (prevents parameter explosion)

---

## Port Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    External Actors                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │   CLI    │  │  Lambda  │  │ REST API │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                 │
└───────┼────────────┼────────────┼─────────────────────────┘
        │            │            │
        └────────────┴────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │    ScannerPort         │  ◄─── Inbound Port
        │  (scanner_port.py)     │
        └────────────┬───────────┘
                     │
┌────────────────────┼───────────────────────────────────────┐
│                    ▼                                        │
│       ┌────────────────────────┐                           │
│       │   Scanner Service      │  Application Core         │
│       │  (Business Logic)      │                           │
│       └───┬────────────────┬───┘                           │
│           │                │                                │
│           ▼                ▼                                │
│  ┌─────────────┐  ┌──────────────┐                        │
│  │ OutputPort  │  │AWSClientPort │  ◄─── Outbound Ports   │
│  └──────┬──────┘  └──────┬───────┘                        │
└─────────┼────────────────┼────────────────────────────────┘
          │                │
          ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│               External Infrastructure                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │   CSV    │  │CloudWatch│  │  boto3   │                 │
│  │ Adapter  │  │  Adapter │  │ Adapter  │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Benefits of Port Abstraction

### 1. Testability
```python
# tests/unit/application/test_scanner_service.py
class MockAWSClient(AWSClientPort):
    """Test double for AWS operations"""
    def list_web_acls(self, region: str, scope: str) -> List[WebACL]:
        return [WebACL(name="test-waf", ...)]  # No real AWS calls

# Test with mock
scanner = ScannerService(
    aws_client=MockAWSClient(),  # ← Inject mock
    logger=MockLogger()
)
result = scanner.scan_account(request)
assert result.total_resources == expected_count
```

### 2. Flexibility
```python
# Easy to swap implementations
if env == "local":
    aws_client = LocalStackAdapter()  # Points to LocalStack
elif env == "test":
    aws_client = MockAWSClient()  # In-memory mock
else:
    aws_client = Boto3Adapter()  # Real AWS
```

### 3. Parallel Development
- Backend team implements adapters (boto3)
- Core team implements scanner service
- Both work independently using port contracts
- Integration happens at composition root

### 4. Output Format Addition (Example)
```python
# Add Slack adapter without touching core
class SlackOutputAdapter(OutputPort):
    def export(self, scan_result: ScanResult) -> None:
        webhook_url = os.getenv("SLACK_WEBHOOK")
        payload = self._build_slack_message(scan_result)
        requests.post(webhook_url, json=payload)
    
    def get_format_name(self) -> str:
        return "Slack"

# Use it
scanner_service.scan_account(
    request,
    output_adapters=[CsvExporter(), SlackOutputAdapter()]  # ← Add new adapter
)
```

## Dependency Inversion in Action

**Traditional Approach** (tight coupling):
```python
# ❌ Application depends on boto3 directly
class ScannerService:
    def __init__(self):
        self.waf_client = boto3.client('wafv2')  # Hard dependency
```

**Hexagonal Approach** (decoupled):
```python
# ✅ Application depends on abstraction
class ScannerService:
    def __init__(self, aws_client: AWSClientPort):  # Depends on interface
        self.aws_client = aws_client
```

## Next Steps
Proceed to Task 4: Implement the Boto3 adapter that fulfills the `AWSClientPort` contract.
