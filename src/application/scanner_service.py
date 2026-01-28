"""Scanner Service - Core application logic for WAF perimeter scanning."""

from src.domain.entities import Resource, ScanResult, WebACL
from src.domain.value_objects import ResourceType
from src.ports.outbound import AWSClientPort, LoggerPort, OutputPort

# Default regions to scan (only us-east-1 for now)
DEFAULT_REGIONS = [
    "us-east-1",
    # "us-east-2",
    # "us-west-1",
    # "us-west-2",
    # "ap-south-1",
    # "ap-northeast-1",
    # "ap-northeast-2",
    # "ap-northeast-3",
    # "ap-southeast-1",
    # "ap-southeast-2",
    # "ca-central-1",
    # "eu-central-1",
    # "eu-west-1",
    # "eu-west-2",
    # "eu-west-3",
    # "eu-north-1",
    # "sa-east-1",
]

# Resource types to scan by default
DEFAULT_RESOURCE_TYPES = [
    ResourceType.ALB,
    ResourceType.CLOUDFRONT,
    ResourceType.API_GATEWAY_REST,
    ResourceType.API_GATEWAY_HTTP,
    ResourceType.APPSYNC,
    ResourceType.COGNITO,
    ResourceType.APP_RUNNER,
    ResourceType.VERIFIED_ACCESS,
]


class ScannerService:
    """
    Core application service for WAF perimeter scanning.

    This service orchestrates the scanning of AWS resources and their
    WAF associations across multiple regions.
    """

    def __init__(
        self,
        aws_client: AWSClientPort,
        output: OutputPort,
        logger: LoggerPort,
    ):
        """
        Initialize the scanner service.

        Args:
            aws_client: AWS client for resource and WAF operations
            output: Output adapter for writing results
            logger: Logger for operation logging
        """
        self._aws_client = aws_client
        self._output = output
        self._logger = logger

    def scan(
        self,
        regions: list[str] | None = None,
        resource_types: list[ResourceType] | None = None,
        include_waf_lookup: bool = True,
    ) -> ScanResult:
        """
        Execute a WAF perimeter scan.

        Args:
            regions: List of regions to scan (default: all commercial regions)
            resource_types: List of resource types to scan (default: all supported)
            include_waf_lookup: Whether to look up WAF associations (default: True)

        Returns:
            ScanResult containing all discovered resources and their WAF status
        """
        regions = regions or DEFAULT_REGIONS
        resource_types = resource_types or DEFAULT_RESOURCE_TYPES

        # Get account info
        identity = self._aws_client.get_caller_identity()
        account_id = identity["account"]

        self._logger.info(
            "Starting WAF perimeter scan",
            account_id=account_id,
            regions_count=len(regions),
            resource_types_count=len(resource_types),
        )

        scan_result = ScanResult(
            account_id=account_id,
            regions_scanned=regions,
        )

        # Build WAF associations map upfront for regional resources (more efficient)
        waf_map: dict[str, WebACL] = {}
        if include_waf_lookup:
            self._logger.info("Building WAF associations map for regional resources")
            waf_map = self._aws_client.get_waf_associations_map(regions)
            self._logger.info(f"Found {len(waf_map)} regional resources with WAF associations")

        # Scan resources
        for region in regions:
            self._scan_region(
                scan_result=scan_result,
                region=region,
                resource_types=resource_types,
                waf_map=waf_map,
            )

        # Build CloudFront origins map and enrich resources with fronted-by relationships
        if include_waf_lookup:
            self._logger.info("Building CloudFront origins map for fronted-by detection")
            origins_map = self._aws_client.get_cloudfront_origins_map()
            self._enrich_fronted_by_relationships(scan_result, origins_map)

        scan_result.complete()

        self._logger.info(
            "Scan completed",
            total_resources=scan_result.total_resources,
            resources_with_waf=scan_result.resources_with_waf,
            resources_without_waf=scan_result.resources_without_waf,
            compliance_rate=f"{scan_result.get_compliance_rate():.1f}%",
            errors_count=len(scan_result.errors),
        )

        return scan_result

    def _scan_region(
        self,
        scan_result: ScanResult,
        region: str,
        resource_types: list[ResourceType],
        waf_map: dict[str, WebACL],
    ) -> None:
        """Scan all resource types in a single region."""
        self._logger.debug(f"Scanning region: {region}")

        for resource_type in resource_types:
            self._scan_resource_type(
                scan_result=scan_result,
                region=region,
                resource_type=resource_type,
                waf_map=waf_map,
            )

    def _scan_resource_type(
        self,
        scan_result: ScanResult,
        region: str,
        resource_type: ResourceType,
        waf_map: dict[str, WebACL],
    ) -> None:
        """Scan a single resource type in a region."""
        # CloudFront is global - only scan once from us-east-1
        if resource_type == ResourceType.CLOUDFRONT and region != "us-east-1":
            return

        try:
            resources = self._aws_client.list_resources(resource_type, region)

            self._logger.debug(
                f"Found {len(resources)} {resource_type.display_name} in {region}"
            )

            for resource in resources:
                # CloudFront already has WAF info from distribution config
                # For other resources, enrich from the pre-built map
                if resource.resource_type != ResourceType.CLOUDFRONT and resource.arn in waf_map:
                    resource.web_acl = waf_map[resource.arn]
                scan_result.add_resource(resource)

        except Exception as e:
            error_msg = f"Error scanning {resource_type.value} in {region}: {e}"
            self._logger.error(error_msg, exception=e)
            scan_result.add_error(
                region=region,
                resource_type=resource_type.value,
                error_message=str(e),
            )

    def _enrich_fronted_by_relationships(
        self,
        scan_result: ScanResult,
        origins_map: dict[str, list[dict]],
    ) -> None:
        """
        Enrich resources with fronted-by CloudFront information.

        This method identifies resources (HTTP APIs, REST APIs, ALBs) that are
        "fronted by" CloudFront distributions with WAF protection.

        Args:
            scan_result: The scan result containing all resources
            origins_map: Map of origin domains to CloudFront distributions
        """
        enriched_count = 0

        for resource in scan_result.resources:
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
            origin_domain = self._aws_client.match_resource_to_origin(resource)
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
                    enriched_count += 1
                    self._logger.info(
                        f"Resource {resource.name} ({resource.resource_type.value}) is fronted by "
                        f"CloudFront {cf_dist['cloudfront_id']} with WAF {cf_dist['web_acl'].name}"
                    )
                    break  # Use first CloudFront with WAF

        self._logger.info(f"Enriched {enriched_count} resources with fronted-by CloudFront information")

    def _enrich_with_waf(self, resource: Resource) -> None:
        """
        Look up and attach WAF information to a resource.

        DEPRECATED: Use waf_map from get_waf_associations_map() instead.
        """
        try:
            web_acl = self._aws_client.get_web_acl_for_resource(
                resource_arn=resource.arn,
                resource_type=resource.resource_type,
            )
            resource.web_acl = web_acl
        except Exception as e:
            self._logger.warning(
                f"Could not get WAF for {resource.arn}: {e}"
            )

    def export_results(
        self,
        scan_result: ScanResult,
        output_path: str,
    ) -> str:
        """
        Export scan results using the configured output adapter.

        Args:
            scan_result: The scan result to export
            output_path: Path for the output

        Returns:
            The actual path where results were written
        """
        output_location = self._output.write(scan_result, output_path)
        self._logger.info(
            f"Results exported to {output_location}",
            format=self._output.get_format_name(),
        )
        return output_location

    def scan_and_export(
        self,
        output_path: str,
        regions: list[str] | None = None,
        resource_types: list[ResourceType] | None = None,
    ) -> ScanResult:
        """
        Convenience method to scan and export in one call.

        Args:
            output_path: Path for the output file
            regions: List of regions to scan
            resource_types: List of resource types to scan

        Returns:
            The ScanResult (also exported to file)
        """
        scan_result = self.scan(regions=regions, resource_types=resource_types)
        self.export_results(scan_result, output_path)
        return scan_result


def create_scanner(
    logger: LoggerPort,
    output: OutputPort | None = None,
    role_arn: str | None = None,
) -> ScannerService:
    """
    Factory function to create a properly configured ScannerService.

    Args:
        logger: Logger instance to use
        output: Output adapter (defaults to CSVExporter)
        role_arn: Optional role to assume for cross-account access

    Returns:
        Configured ScannerService instance
    """
    from src.adapters.outbound import Boto3AWSClient, CSVExporter

    aws_client = Boto3AWSClient(logger=logger)

    if role_arn:
        aws_client = aws_client.assume_role(
            role_arn=role_arn,
            session_name="aws-perimeter-guard",
        )

    output = output or CSVExporter()

    return ScannerService(
        aws_client=aws_client,
        output=output,
        logger=logger,
    )
