"""CLI Adapter - Command-line interface for AWS Perimeter Guard."""
import sys

import click

from src.adapters.outbound import ConsoleLogger, CSVExporter, generate_output_filename
from src.application.scanner_service import (
    DEFAULT_REGIONS,
    create_scanner,
)
from src.domain.value_objects import ResourceType

# Available resource type choices
RESOURCE_TYPE_CHOICES = [rt.value for rt in ResourceType]


@click.group()
@click.version_option(version="0.1.0", prog_name="aws-perimeter-guard")
def cli() -> None:
    """
    AWS Perimeter Guard - Scan AWS resources for WAF associations.

    This tool scans your AWS account for resources that can have WAF protection
    and reports on their WAF association status.
    """
    pass


@cli.command()
@click.option(
    "--regions", "-r",
    multiple=True,
    help="AWS regions to scan. Can be specified multiple times. Default: all commercial regions.",
)
@click.option(
    "--resource-types", "-t",
    multiple=True,
    type=click.Choice(RESOURCE_TYPE_CHOICES, case_sensitive=False),
    help="Resource types to scan. Can be specified multiple times. Default: all supported types.",
)
@click.option(
    "--output", "-o",
    default=None,
    help="Output file path for CSV results. Default: auto-generated filename.",
)
@click.option(
    "--role-arn",
    default=None,
    help="IAM role ARN to assume for cross-account scanning.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output (DEBUG level logging).",
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Suppress all output except errors.",
)
@click.option(
    "--stdout",
    is_flag=True,
    help="Output CSV to stdout instead of a file.",
)
def scan(
    regions: tuple,
    resource_types: tuple,
    output: str | None,
    role_arn: str | None,
    verbose: bool,
    quiet: bool,
    stdout: bool,
) -> None:
    """
    Scan AWS resources for WAF associations.

    Examples:

        # Scan all resources in all regions
        aws-perimeter-guard scan

        # Scan specific regions
        aws-perimeter-guard scan -r us-east-1 -r eu-west-1

        # Scan only ALBs and CloudFront
        aws-perimeter-guard scan -t APPLICATION_LOAD_BALANCER -t CLOUDFRONT_DISTRIBUTION

        # Cross-account scan
        aws-perimeter-guard scan --role-arn arn:aws:iam::123456789012:role/WAFScannerRole

        # Output to stdout
        aws-perimeter-guard scan --stdout
    """
    # Set up logger
    log_level = "DEBUG" if verbose else ("ERROR" if quiet else "INFO")
    logger = ConsoleLogger(level=log_level)

    # Parse regions
    regions_list: list[str] | None = list(regions) if regions else None

    # Parse resource types
    resource_types_list: list[ResourceType] | None = None
    if resource_types:
        resource_types_list = [ResourceType(rt) for rt in resource_types]

    try:
        # Create scanner
        scanner = create_scanner(
            logger=logger,
            output=CSVExporter(),
            role_arn=role_arn,
        )

        # Run scan
        scan_result = scanner.scan(
            regions=regions_list,
            resource_types=resource_types_list,
        )

        # Determine output path
        if stdout:
            output_path = "stdout"
        elif output:
            output_path = output
        else:
            output_path = generate_output_filename(scan_result)

        # Export results
        actual_path = scanner.export_results(scan_result, output_path)

        # Print summary (unless outputting to stdout or quiet)
        if not stdout and not quiet:
            _print_summary(scan_result, actual_path)

    except Exception as e:
        logger.error(f"Scan failed: {e}", exception=e)
        sys.exit(1)


@cli.command()
@click.option(
    "--role-arn",
    default=None,
    help="IAM role ARN to assume (test assumed role identity).",
)
def whoami(role_arn: str | None) -> None:
    """
    Show the current AWS identity.

    Useful for verifying credentials before scanning.
    """
    logger = ConsoleLogger(level="INFO")

    try:
        from src.adapters.outbound import Boto3AWSClient

        aws_client = Boto3AWSClient(logger=logger)

        if role_arn:
            aws_client = aws_client.assume_role(
                role_arn=role_arn,
                session_name="aws-perimeter-guard-test",
            )

        identity = aws_client.get_caller_identity()

        click.echo(f"Account: {identity['account']}")
        click.echo(f"ARN: {identity['arn']}")
        click.echo(f"User ID: {identity['user_id']}")

    except Exception as e:
        logger.error(f"Failed to get identity: {e}", exception=e)
        sys.exit(1)


@cli.command()
def list_resource_types() -> None:
    """
    List all supported resource types.

    Shows the resource types that can be scanned for WAF associations.
    """
    click.echo("Supported resource types:\n")
    for rt in ResourceType:
        click.echo(f"  {rt.value}")
        click.echo(f"    Display name: {rt.display_name}")
        click.echo(f"    AWS service: {rt.aws_service}")
        click.echo(f"    WAF scope: {'CLOUDFRONT' if rt.is_cloudfront_scope else 'REGIONAL'}")
        click.echo()


@cli.command()
def list_regions() -> None:
    """
    List all default regions that will be scanned.
    """
    click.echo("Default regions to scan:\n")
    for region in DEFAULT_REGIONS:
        click.echo(f"  {region}")


def _print_summary(scan_result, output_path: str) -> None:
    """Print a summary of scan results."""
    click.echo("\n" + "=" * 60)
    click.echo("SCAN SUMMARY")
    click.echo("=" * 60)
    click.echo(f"Account: {scan_result.account_id}")
    click.echo(f"Regions scanned: {len(scan_result.regions_scanned)}")
    click.echo(f"Total resources: {scan_result.total_resources}")
    click.echo(f"Resources with WAF: {scan_result.resources_with_waf}")
    click.echo(f"Resources without WAF: {scan_result.resources_without_waf}")
    click.echo(f"WAF coverage: {scan_result.get_waf_coverage_rate():.1f}%")
    click.echo(f"Compliance rate: {scan_result.get_compliance_rate():.1f}%")

    if scan_result.errors:
        click.echo(f"\nErrors encountered: {len(scan_result.errors)}")

    click.echo(f"\nResults written to: {output_path}")
    click.echo("=" * 60)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
