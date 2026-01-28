# Task 6.5: Resource Relationship Detection (Fronted-By Resources)

**Status**: Not Started  
**Dependencies**: Task 6 (Scanner Service)  
**Estimated Time**: 2-3 hours

## Overview

Some AWS resources cannot directly have WAF associations (e.g., HTTP API Gateways) but may be protected by being "fronted by" other resources that do have WAF (e.g., CloudFront distributions). This task adds detection and reporting of these indirect WAF protections.

## Problem Statement

**Current Behavior**:
```csv
# HTTP API Gateway shows no WAF (technically correct but incomplete)
00011123456,us-east-1,API Gateway HTTP API,api-<REDACTED>,arn:...,No,,,Yes,COMPLIANT_NO_WAF_REQUIRED,...

# CloudFront distribution fronting the API Gateway shows WAF
00011123456,global,CloudFront Distribution,dssysuper6thkx.cloudfront.net,arn:...,Yes,SOME_RANDOM_WAF,...,COMPLIANT,...
```

**Desired Behavior**:
```csv
# HTTP API Gateway shows it's fronted by CloudFront with WAF
00011123456,us-east-1,API Gateway HTTP API,api-exam,arn:...,No,,,Yes,COMPLIANT_FRONTED_BY_WAF,...,Fronted by CloudFront Distribution arn:aws:cloudfront::00011123456:distribution/E3T3M3NN0S4B6A with WAF SOME_RANDOM_WAF
```

## Scope

### Relationships to Detect

1. **HTTP API Gateways** fronted by CloudFront distributions
2. **REST API Gateways** fronted by CloudFront distributions
3. **Application Load Balancers (ALBs)** fronted by CloudFront distributions

### Origin Domain Patterns

CloudFront distributions can have various origin types. We need to match:

| Resource Type | Origin Domain Pattern | Example |
|---------------|----------------------|---------|
| HTTP API Gateway | `{api-id}.execute-api.{region}.amazonaws.com` | `joyanec4c4s.execute-api.us-east-1.amazonaws.com` |
| REST API Gateway | `{api-id}.execute-api.{region}.amazonaws.com` | `muit0brig4.execute-api.us-east-1.amazonaws.com` |
| ALB | `{name}-{hash}.elb.{region}.amazonaws.com` | `k8s-ingressn-example.elb.us-east-1.amazonaws.com` |

## Implementation Details

### 1. Data Structure Changes

#### Domain Model (`src/domain/entities/resource.py`)

Add new fields to `Resource` dataclass:

```python
@dataclass
class Resource:
    """AWS resource that can have a WAF."""
    arn: str
    resource_type: ResourceType
    name: str
    region: str
    account_id: str
    web_acl: Optional[WebACL] = None
    is_public: bool = True
    scanned_at: Optional[datetime] = None
    
    # NEW FIELDS for fronted-by detection
    fronted_by_resource_arn: Optional[str] = None
    fronted_by_waf: Optional[WebACL] = None
    fronted_by_notes: Optional[str] = None
```

#### Compliance Status (`src/domain/value_objects/compliance_status.py`)

Add new compliance status enum value:

```python
class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    COMPLIANT_NO_WAF_REQUIRED = "COMPLIANT_NO_WAF_REQUIRED"
    COMPLIANT_FRONTED_BY_WAF = "COMPLIANT_FRONTED_BY_WAF"  # NEW
```

### 2. AWS Client Adapter Enhancement

#### New Method: `get_cloudfront_origins_map()`

Add to `src/adapters/outbound/boto3_aws_client.py`:

```python
def get_cloudfront_origins_map(self) -> dict[str, List[dict]]:
    """
    Build a map of CloudFront origin domains to CloudFront distributions.
    
    Returns:
        Dict mapping origin domain → list of dicts with:
        - cloudfront_arn: ARN of the CloudFront distribution
        - cloudfront_id: Distribution ID
        - cloudfront_domain: Distribution domain name
        - web_acl: WebACL object if distribution has WAF
    
    Example:
        {
            "joyanec4c4s.execute-api.us-east-1.amazonaws.com": [
                {
                    "cloudfront_arn": "arn:aws:cloudfront::...:distribution/E3T3M3NN0S4B6A",
                    "cloudfront_id": "E3T3M3NN0S4B6A",
                    "cloudfront_domain": "dssysuper6thkx.cloudfront.net",
                    "web_acl": WebACL(...)
                }
            ]
        }
    """
    origins_map = {}
    
    # Get all CloudFront distributions (already scanned in _list_cloudfront_distributions)
    cloudfront = self.session.client('cloudfront')
    paginator = cloudfront.get_paginator('list_distributions')
    
    for page in paginator.paginate():
        if 'Items' not in page.get('DistributionList', {}):
            continue
            
        for dist_summary in page['DistributionList']['Items']:
            dist_id = dist_summary['Id']
            
            # Get full distribution config (includes origins and WebACLId)
            full_dist = cloudfront.get_distribution(Id=dist_id)
            config = full_dist['Distribution']['DistributionConfig']
            
            # Parse WebACL if present
            web_acl = None
            web_acl_id = config.get('WebACLId', '')
            if web_acl_id:
                # Parse ARN: arn:aws:wafv2:region:account:global/webacl/name/id
                web_acl = self._parse_waf_arn(web_acl_id)
            
            # Extract all origins
            origins = config.get('Origins', {}).get('Items', [])
            for origin in origins:
                domain = origin['DomainName']
                
                if domain not in origins_map:
                    origins_map[domain] = []
                
                origins_map[domain].append({
                    'cloudfront_arn': f"arn:aws:cloudfront::{self.account_id}:distribution/{dist_id}",
                    'cloudfront_id': dist_id,
                    'cloudfront_domain': dist_summary['DomainName'],
                    'web_acl': web_acl
                })
    
    return origins_map
```

#### Helper Method: Match Resources to Origins

```python
def _match_resource_to_origin(self, resource: Resource) -> Optional[str]:
    """
    Extract the origin domain from a resource.
    
    Args:
        resource: Resource to extract origin domain from
    
    Returns:
        Origin domain string if matchable, None otherwise
    
    Examples:
        HTTP API: "joyanec4c4s.execute-api.us-east-1.amazonaws.com"
        REST API: "muit0brig4.execute-api.us-east-1.amazonaws.com"
        ALB: "k8s-name-hash.elb.us-east-1.amazonaws.com"
    """
    if resource.resource_type == ResourceType.API_GATEWAY_HTTP:
        # Extract API ID from ARN: arn:aws:apigateway:us-east-1::/apis/joyanec4c4s
        api_id = resource.arn.split('/apis/')[-1]
        return f"{api_id}.execute-api.{resource.region}.amazonaws.com"
    
    elif resource.resource_type == ResourceType.API_GATEWAY_REST:
        # Extract API ID from ARN: arn:aws:apigateway:us-east-1::/restapis/muit0brig4
        api_id = resource.arn.split('/restapis/')[-1]
        return f"{api_id}.execute-api.{resource.region}.amazonaws.com"
    
    elif resource.resource_type == ResourceType.ALB:
        # ALB resources already have DNS name stored in 'name' field
        # Format: k8s-ingressn-ingressn-b9ceae230a
        # But we need the full DNS: {name}-{hash}.elb.{region}.amazonaws.com
        # We need to get this from the ALB describe call
        # For now, we'll fetch it on demand
        return self._get_alb_dns_name(resource.arn, resource.region)
    
    return None

def _get_alb_dns_name(self, alb_arn: str, region: str) -> Optional[str]:
    """Get ALB DNS name from its ARN."""
    try:
        elbv2 = self.session.client('elbv2', region_name=region)
        response = elbv2.describe_load_balancers(LoadBalancerArns=[alb_arn])
        if response['LoadBalancers']:
            return response['LoadBalancers'][0]['DNSName']
    except ClientError as e:
        logger.debug(f"Could not get ALB DNS name for {alb_arn}: {e}")
    return None
```

### 3. Scanner Service Enhancement

#### Updated Scan Flow

Modify `src/application/scanner_service.py`:

```python
def scan(self, regions: Optional[List[str]] = None) -> ScanResult:
    """
    Scan AWS account for resources and WAF associations.
    
    Enhanced flow:
    1. Build WAF associations map (for regional resources)
    2. Scan all resources (CloudFront includes WAF in listing)
    3. Build CloudFront origins map
    4. Enrich resources with fronted-by relationships
    5. Build and return ScanResult
    """
    if regions is None:
        regions = self.default_regions
    
    logger.info(f"Starting scan for account {self.aws_client.account_id}")
    logger.info(f"Scanning regions: {regions}")
    
    # Step 1: Build WAF associations map (for regional resources)
    waf_map = self.aws_client.get_waf_associations_map(regions)
    logger.info(f"Found {len(waf_map)} WAF associations")
    
    # Step 2: Scan all resources
    all_resources = []
    for resource_type in ResourceType:
        resources = self._scan_resource_type(resource_type, regions, waf_map)
        all_resources.extend(resources)
    
    # Step 3: Build CloudFront origins map
    origins_map = self.aws_client.get_cloudfront_origins_map()
    logger.info(f"Found {len(origins_map)} CloudFront origin mappings")
    
    # Step 4: Enrich resources with fronted-by relationships
    self._enrich_fronted_by_relationships(all_resources, origins_map)
    
    # Step 5: Build and return ScanResult
    scan_result = ScanResult(
        account_id=self.aws_client.account_id,
        scan_id=f"scan-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        scanned_at=datetime.now(UTC),
        resources=all_resources
    )
    
    logger.info(f"Scan complete: {len(all_resources)} resources scanned")
    return scan_result

def _enrich_fronted_by_relationships(
    self, 
    resources: List[Resource], 
    origins_map: dict[str, List[dict]]
):
    """
    Enrich resources with fronted-by CloudFront information.
    
    Args:
        resources: List of scanned resources to enrich
        origins_map: Map of origin domains to CloudFront distributions
    """
    for resource in resources:
        # Only check resources that can be fronted by CloudFront
        if resource.resource_type not in [
            ResourceType.API_GATEWAY_HTTP,
            ResourceType.API_GATEWAY_REST,
            ResourceType.ALB
        ]:
            continue
        
        # Skip if resource already has direct WAF
        if resource.web_acl:
            continue
        
        # Extract origin domain from resource
        origin_domain = self.aws_client._match_resource_to_origin(resource)
        if not origin_domain:
            continue
        
        # Check if this origin is used by any CloudFront distribution
        cloudfront_dists = origins_map.get(origin_domain, [])
        if not cloudfront_dists:
            continue
        
        # Find CloudFront distributions with WAF
        for cf_dist in cloudfront_dists:
            if cf_dist['web_acl']:
                # Resource is fronted by CloudFront with WAF!
                resource.fronted_by_resource_arn = cf_dist['cloudfront_arn']
                resource.fronted_by_waf = cf_dist['web_acl']
                resource.fronted_by_notes = (
                    f"Fronted by CloudFront Distribution {cf_dist['cloudfront_arn']} "
                    f"with WAF {cf_dist['web_acl'].name}"
                )
                logger.info(
                    f"Resource {resource.arn} is fronted by CloudFront "
                    f"{cf_dist['cloudfront_id']} with WAF {cf_dist['web_acl'].name}"
                )
                break  # Use first CloudFront with WAF
```

### 4. Compliance Logic Update

Update `Resource.compliance_status` property:

```python
@property
def compliance_status(self) -> ComplianceStatus:
    """
    Determine compliance status based on WAF association and resource type.
    
    Rules:
    1. Resource with direct WAF → COMPLIANT
    2. Resource fronted by CloudFront with WAF → COMPLIANT_FRONTED_BY_WAF
    3. Non-public resource → COMPLIANT_NO_WAF_REQUIRED
    4. HTTP API Gateway without WAF or fronting → COMPLIANT_NO_WAF_REQUIRED (cannot have direct WAF)
    5. Public resource without WAF or fronting → NON_COMPLIANT
    """
    # Direct WAF association
    if self.web_acl:
        return ComplianceStatus.COMPLIANT
    
    # Fronted by CloudFront with WAF
    if self.fronted_by_waf:
        return ComplianceStatus.COMPLIANT_FRONTED_BY_WAF
    
    # Non-public resources don't require WAF
    if not self.is_public:
        return ComplianceStatus.COMPLIANT_NO_WAF_REQUIRED
    
    # HTTP API Gateways cannot have direct WAF (but could be fronted)
    if self.resource_type == ResourceType.API_GATEWAY_HTTP:
        return ComplianceStatus.COMPLIANT_NO_WAF_REQUIRED
    
    # REST APIs and other resources without WAF → non-compliant
    return ComplianceStatus.NON_COMPLIANT
```

### 5. CSV Export Enhancement

Update `src/adapters/outbound/csv_exporter.py`:

```python
def export(self, scan_result: ScanResult, output_path: Optional[str] = None):
    """Export scan result to CSV with fronted-by information."""
    
    headers = [
        "Account ID",
        "Region",
        "Resource Type",
        "Resource Name",
        "Resource ARN",
        "Has WAF",
        "WAF Name",
        "WAF ARN",
        "Is Public",
        "Compliance Status",
        "Scanned At",
        "Fronted By Resource",      # NEW
        "Fronted By WAF",            # NEW
        "Notes"                      # NEW
    ]
    
    rows = []
    for resource in scan_result.resources:
        row = [
            resource.account_id,
            resource.region,
            resource.resource_type.value,
            resource.name,
            resource.arn,
            "Yes" if resource.web_acl else "No",
            resource.web_acl.name if resource.web_acl else "",
            resource.web_acl.arn if resource.web_acl else "",
            "Yes" if resource.is_public else "No",
            resource.compliance_status.value,
            resource.scanned_at.isoformat() if resource.scanned_at else "",
            resource.fronted_by_resource_arn or "",      # NEW
            resource.fronted_by_waf.name if resource.fronted_by_waf else "",  # NEW
            resource.fronted_by_notes or ""              # NEW
        ]
        rows.append(row)
    
    # Write CSV...
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_resource_relationships.py

def test_match_http_api_to_origin():
    """Test matching HTTP API Gateway to CloudFront origin."""
    resource = Resource(
        arn="arn:aws:apigateway:us-east-1::/apis/joyanec4c4s",
        resource_type=ResourceType.API_GATEWAY_HTTP,
        name="api-exam",
        region="us-east-1",
        account_id="123456789012"
    )
    
    origin = aws_client._match_resource_to_origin(resource)
    assert origin == "joyanec4c4s.execute-api.us-east-1.amazonaws.com"

def test_enrich_fronted_by_relationships():
    """Test enriching resources with fronted-by CloudFront info."""
    # Setup
    http_api = Resource(
        arn="arn:aws:apigateway:us-east-1::/apis/joyanec4c4s",
        resource_type=ResourceType.API_GATEWAY_HTTP,
        name="api-exam",
        region="us-east-1",
        account_id="123456789012"
    )
    
    origins_map = {
        "joyanec4c4s.execute-api.us-east-1.amazonaws.com": [
            {
                "cloudfront_arn": "arn:aws:cloudfront::123456789012:distribution/E3T3M3NN0S4B6A",
                "cloudfront_id": "E3T3M3NN0S4B6A",
                "cloudfront_domain": "dssysuper6thkx.cloudfront.net",
                "web_acl": WebACL(
                    name="SOME_RANDOM_WAF",
                    arn="arn:aws:wafv2:us-east-1:123456789012:global/webacl/SOME_RANDOM_WAF/123",
                    scope="CLOUDFRONT"
                )
            }
        ]
    }
    
    # Execute
    scanner_service._enrich_fronted_by_relationships([http_api], origins_map)
    
    # Assert
    assert http_api.fronted_by_resource_arn == "arn:aws:cloudfront::123456789012:distribution/E3T3M3NN0S4B6A"
    assert http_api.fronted_by_waf.name == "SOME_RANDOM_WAF"
    assert http_api.compliance_status == ComplianceStatus.COMPLIANT_FRONTED_BY_WAF
```

### Integration Tests (with moto)

```python
@mock_cloudfront
@mock_apigatewayv2
@mock_wafv2
def test_full_fronted_by_detection():
    """Test full flow of detecting CloudFront fronting HTTP API with WAF."""
    # Create WAFv2 WebACL
    wafv2 = boto3.client('wafv2', region_name='us-east-1')
    web_acl = wafv2.create_web_acl(
        Name='SOME_RANDOM_WAF',
        Scope='CLOUDFRONT',
        DefaultAction={'Allow': {}},
        VisibilityConfig={
            'SampledRequestsEnabled': True,
            'CloudWatchMetricsEnabled': True,
            'MetricName': 'SOME_RANDOM_WAF'
        }
    )
    
    # Create HTTP API Gateway
    apigw = boto3.client('apigatewayv2', region_name='us-east-1')
    api = apigw.create_api(Name='api-exam', ProtocolType='HTTP')
    api_id = api['ApiId']
    
    # Create CloudFront distribution with API as origin
    cloudfront = boto3.client('cloudfront')
    dist = cloudfront.create_distribution(
        DistributionConfig={
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': 'http_api_origin',
                    'DomainName': f"{api_id}.execute-api.us-east-1.amazonaws.com",
                    'CustomOriginConfig': {
                        'HTTPPort': 80,
                        'HTTPSPort': 443,
                        'OriginProtocolPolicy': 'https-only'
                    }
                }]
            },
            'WebACLId': web_acl['Summary']['ARN'],
            # ... other required config
        }
    )
    
    # Run scan
    scanner = ScannerService(aws_client, csv_exporter, logger)
    result = scanner.scan(['us-east-1'])
    
    # Find HTTP API resource
    http_api_resource = [r for r in result.resources 
                         if r.resource_type == ResourceType.API_GATEWAY_HTTP][0]
    
    # Assert fronted-by detection
    assert http_api_resource.fronted_by_resource_arn is not None
    assert http_api_resource.fronted_by_waf.name == 'SOME_RANDOM_WAF'
    assert http_api_resource.compliance_status == ComplianceStatus.COMPLIANT_FRONTED_BY_WAF
```

## Success Criteria

- ✅ CloudFront origins map built correctly
- ✅ HTTP API Gateways matched to CloudFront origins
- ✅ REST API Gateways matched to CloudFront origins
- ✅ ALBs matched to CloudFront origins
- ✅ `COMPLIANT_FRONTED_BY_WAF` status assigned correctly
- ✅ CSV export includes fronted-by columns
- ✅ Unit tests pass (>80% coverage)
- ✅ Integration tests with moto pass
- ✅ Real-world scan shows fronted-by relationships

## Expected Output

### Before Implementation
```csv
Account ID,Region,Resource Type,Resource Name,Has WAF,Compliance Status
00011123456,us-east-1,API Gateway HTTP API,api-exam,No,COMPLIANT_NO_WAF_REQUIRED
```

### After Implementation
```csv
Account ID,Region,Resource Type,Resource Name,Has WAF,Compliance Status,Fronted By Resource,Fronted By WAF,Notes
00011123456,us-east-1,API Gateway HTTP API,api-exam,No,COMPLIANT_FRONTED_BY_WAF,arn:aws:cloudfront::00011123456:distribution/E3T3M3NN0S4B6A,SOME_RANDOM_WAF,"Fronted by CloudFront Distribution arn:aws:cloudfront::00011123456:distribution/E3T3M3NN0S4B6A with WAF SOME_RANDOM_WAF"
```

## Implementation Order

1. ✅ CLI exploration (completed above)
2. Add `fronted_by_*` fields to `Resource` dataclass
3. Add `COMPLIANT_FRONTED_BY_WAF` to `ComplianceStatus` enum
4. Implement `get_cloudfront_origins_map()` in AWS client adapter
5. Implement `_match_resource_to_origin()` helper
6. Implement `_enrich_fronted_by_relationships()` in scanner service
7. Update `Resource.compliance_status` property
8. Update CSV exporter with new columns
9. Write unit tests
10. Write integration tests (with moto)
11. Run real-world scan and validate output
12. Update documentation

## Notes

- **Performance**: CloudFront origins map is built once per scan (not per region)
- **Multiple CloudFronts**: If multiple CloudFront distributions front the same resource, use the first one with WAF
- **ALB DNS Names**: Requires additional API call to get full DNS name (cached per scan)
- **REST APIs**: Even though they CAN have direct WAF, they may also be fronted by CloudFront (report both if applicable)
