# Advanced CLI Usage

AWS ARMOR perimeter guard can be used in many ways. Here are some advanced examples:

##### Scan Specific Regions
```bash
# Scan multiple specific regions
python -m src.main scan --regions us-east-1,eu-west-1,ap-southeast-1

# Scan all regions (use with caution - may take time)
python -m src.main scan --regions all
```

#### Scan Specific Resource Types
```bash
# Scan only load balancers and CloudFront distributions
python -m src.main scan --resource-types ALB,CLOUDFRONT

# Scan API-related resources
python -m src.main scan --resource-types API_GATEWAY_REST,API_GATEWAY_HTTP,APPSYNC
```

##### Cross-Account Scanning
```bash
# Use a specific AWS profile
AWS_PROFILE=my-profile python -m src.main scan

# Assume a role in another account
python -m src.main scan --role-arn arn:aws:iam::123456789012:role/WAFScannerRole
```

##### Output Options
```bash
# Save to specific file
python -m src.main scan --output my-security-audit.csv

# Output to stdout (for piping or scripting)
python -m src.main scan --stdout | grep NON_COMPLIANT

# Quiet mode (less verbose output)
python -m src.main scan --quiet --output results.csv
```

#### Utility Commands

```bash
# List all supported resource types
python -m src.main list-resource-types

# List default regions that will be scanned
python -m src.main list-regions

# Check AWS identity and permissions
python -m src.main whoami

# Show detailed help
python -m src.main --help
python -m src.main scan --help
```

#### Examples for Common CLI Use Cases

##### Security Audit
```bash
# Comprehensive security audit across multiple regions
python -m src.main scan \
  --regions us-east-1,eu-west-1,ap-southeast-1 \
  --output security-audit-$(date +%Y%m%d).csv \
  --verbose
```

##### Quick Compliance Check
```bash
# Fast check of critical resources
python -m src.main scan \
  --resource-types ALB,CLOUDFRONT,API_GATEWAY_REST \
  --regions us-east-1 \
  --output compliance-check.csv
```

##### CI/CD Integration
```bash
# Automated scanning in CI/CD pipeline
python -m src.main scan \
  --stdout \
  --quiet \
  | grep -c NON_COMPLIANT || exit 1
```
