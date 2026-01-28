"""Tests for the CLI adapter."""
from click.testing import CliRunner

from src.adapters.inbound.cli_adapter import cli


class TestCLI:
    """Test the CLI interface."""

    def test_cli_help(self):
        """CLI should show help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AWS Perimeter Guard" in result.output
        assert "scan" in result.output

    def test_cli_version(self):
        """CLI should show version."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_scan_help(self):
        """Scan command should show help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--regions" in result.output
        assert "--output" in result.output
        assert "--role-arn" in result.output

    def test_list_resource_types(self):
        """Should list supported resource types."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list-resource-types"])
        assert result.exit_code == 0
        assert "APPLICATION_LOAD_BALANCER" in result.output
        assert "CLOUDFRONT_DISTRIBUTION" in result.output

    def test_list_regions(self):
        """Should list default regions."""
        runner = CliRunner()
        result = runner.invoke(cli, ["list-regions"])
        assert result.exit_code == 0
        assert "us-east-1" in result.output
