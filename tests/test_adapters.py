"""Tests for output adapters."""
import os

from src.adapters.outbound.csv_exporter import CSVExporter, generate_output_filename
from src.domain.entities import Resource, ScanResult, WebACL
from src.domain.value_objects import ResourceType


class TestCSVExporter:
    """Test the CSV exporter."""

    def test_export_empty_result(self, tmp_path):
        """Export empty scan result."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )

        exporter = CSVExporter()
        output_path = str(tmp_path / "output.csv")
        actual_path = exporter.write(result, output_path)

        assert os.path.exists(actual_path)
        with open(actual_path) as f:
            content = f.read()
            assert "Account ID" in content  # Header present
            assert "Resource ARN" in content

    def test_export_with_resources(self, tmp_path):
        """Export scan result with resources."""
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
            name="test-alb-1",
            is_public=True,
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
            name="test-alb-2",
            is_public=False,
            web_acl=acl,
        ))

        exporter = CSVExporter()
        output_path = str(tmp_path / "output.csv")
        actual_path = exporter.write(result, output_path)

        with open(actual_path) as f:
            content = f.read()
            assert "test-alb-1" in content
            assert "test-alb-2" in content
            assert "test-acl" in content
            assert "Yes" in content  # Has WAF
            assert "No" in content  # No WAF

    def test_adds_csv_extension(self, tmp_path):
        """Should add .csv extension if missing."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )

        exporter = CSVExporter()
        output_path = str(tmp_path / "output")  # No extension
        actual_path = exporter.write(result, output_path)

        assert actual_path.endswith(".csv")

    def test_get_format_name(self):
        """Should return format name."""
        exporter = CSVExporter()
        assert exporter.get_format_name() == "CSV"


class TestGenerateOutputFilename:
    """Test the output filename generator."""

    def test_generates_filename(self):
        """Should generate a unique filename."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )

        filename = generate_output_filename(result)

        assert filename.startswith("waf-scan-123456789012-")
        assert filename.endswith(".csv")

    def test_custom_prefix(self):
        """Should support custom prefix."""
        result = ScanResult(
            account_id="123456789012",
            regions_scanned=["us-east-1"],
        )

        filename = generate_output_filename(result, prefix="custom")

        assert filename.startswith("custom-123456789012-")
