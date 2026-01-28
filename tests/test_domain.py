"""Tests for the domain model."""

from src.domain.entities import Resource, ScanResult, WebACL
from src.domain.value_objects import ResourceType


class TestResourceType:
    """Test the ResourceType enum."""

    def test_all_resource_types_defined(self):
        """Verify all 8 resource types are defined."""
        expected_types = [
            ResourceType.ALB,
            ResourceType.CLOUDFRONT,
            ResourceType.API_GATEWAY_REST,
            ResourceType.API_GATEWAY_HTTP,
            ResourceType.APPSYNC,
            ResourceType.COGNITO,
            ResourceType.APP_RUNNER,
            ResourceType.VERIFIED_ACCESS,
        ]
        assert len(expected_types) == 8
        for rt in expected_types:
            assert isinstance(rt, ResourceType)

    def test_cloudfront_scope(self):
        """CloudFront should use CLOUDFRONT scope."""
        assert ResourceType.CLOUDFRONT.is_cloudfront_scope is True
        assert ResourceType.ALB.is_cloudfront_scope is False

    def test_display_name(self):
        """Resource types should have display names."""
        assert ResourceType.ALB.display_name == "Application Load Balancer"
        assert ResourceType.CLOUDFRONT.display_name == "CloudFront Distribution"

    def test_aws_service(self):
        """Resource types should have AWS service names."""
        assert ResourceType.ALB.aws_service == "elasticloadbalancing"
        assert ResourceType.CLOUDFRONT.aws_service == "cloudfront"


class TestWebACL:
    """Test the WebACL entity."""

    def test_create_web_acl(self):
        """Create a basic WebACL."""
        acl = WebACL(
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/test/1234",
            name="test-acl",
            id="1234",
            scope="REGIONAL",
            region="us-east-1",
        )
        assert acl.name == "test-acl"
        assert acl.is_regional() is True
        assert acl.is_global() is False

    def test_global_acl(self):
        """Create a global (CloudFront) WebACL."""
        acl = WebACL(
            arn="arn:aws:wafv2:global:123456789012:global/webacl/test/1234",
            name="global-acl",
            id="1234",
            scope="CLOUDFRONT",
            region="us-east-1",
        )
        assert acl.is_global() is True
        assert acl.is_regional() is False


class TestResource:
    """Test the Resource entity."""

    def test_resource_without_waf(self):
        """Resource without WAF association."""
        resource = Resource(
            arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/1234",
            resource_type=ResourceType.ALB,
            region="us-east-1",
            account_id="123456789012",
            name="test-alb",
            is_public=True,
        )
        assert resource.has_waf() is False
        assert resource.get_waf_arn() is None
        assert resource.get_waf_name() is None

    def test_resource_with_waf(self):
        """Resource with WAF association."""
        acl = WebACL(
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/test/1234",
            name="test-acl",
            id="1234",
            scope="REGIONAL",
            region="us-east-1",
        )
        resource = Resource(
            arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/1234",
            resource_type=ResourceType.ALB,
            region="us-east-1",
            account_id="123456789012",
            name="test-alb",
            is_public=True,
            web_acl=acl,
        )
        assert resource.has_waf() is True
        assert resource.get_waf_arn() == acl.arn
        assert resource.get_waf_name() == "test-acl"

    def test_compliance_public_alb_without_waf(self):
        """Public ALB without WAF should be non-compliant."""
        resource = Resource(
            arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/1234",
            resource_type=ResourceType.ALB,
            region="us-east-1",
            account_id="123456789012",
            is_public=True,
        )
        assert resource.is_compliant() is False
        assert resource.get_compliance_status() == "NON_COMPLIANT"

    def test_compliance_cloudfront_without_waf(self):
        """CloudFront without WAF should be non-compliant."""
        resource = Resource(
            arn="arn:aws:cloudfront::123456789012:distribution/ABC123",
            resource_type=ResourceType.CLOUDFRONT,
            region="global",
            account_id="123456789012",
            is_public=True,
        )
        assert resource.is_compliant() is False


class TestScanResult:
    """Test the ScanResult aggregate."""

    def test_empty_scan_result(self):
        """Empty scan result should have 100% compliance."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )
        assert result.total_resources == 0
        assert result.get_compliance_rate() == 100.0
        assert result.get_waf_coverage_rate() == 0.0

    def test_add_resources(self):
        """Add resources to scan result."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )
        resource = Resource(
            arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/1234",
            resource_type=ResourceType.ALB,
            region="us-east-1",
            account_id="123456789012",
        )
        result.add_resource(resource)

        assert result.total_resources == 1
        assert resource.scanned_at is not None  # Should be set by add_resource

    def test_statistics(self):
        """Test scan result statistics."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )

        # Add resource without WAF
        result.add_resource(Resource(
            arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test1/1234",
            resource_type=ResourceType.ALB,
            region="us-east-1",
            account_id="123456789012",
        ))

        # Add resource with WAF
        acl = WebACL(
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/test/1234",
            name="test-acl",
            id="1234",
            scope="REGIONAL",
            region="us-east-1",
        )
        result.add_resource(Resource(
            arn="arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test2/5678",
            resource_type=ResourceType.ALB,
            region="us-east-1",
            account_id="123456789012",
            web_acl=acl,
        ))

        assert result.total_resources == 2
        assert result.resources_with_waf == 1
        assert result.resources_without_waf == 1
        assert result.get_waf_coverage_rate() == 50.0

    def test_complete_scan(self):
        """Test marking scan as complete."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )
        assert result.scan_completed_at is None

        result.complete()

        assert result.scan_completed_at is not None
