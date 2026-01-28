"""Lambda Handler - AWS Lambda entry point for Perimeter Guard scanner."""
import json
import os
from typing import Any

from src.adapters.outbound import Boto3AWSClient, CloudWatchLogger
from src.application.scanner_service import ScannerService
from src.ports.outbound import OutputPort


class CloudWatchResultsOutput(OutputPort):
    """
    Output adapter that writes scan results as structured JSON logs.

    This allows results to be queried via CloudWatch Logs Insights.
    """

    def __init__(self, logger: CloudWatchLogger):
        self._logger = logger

    def write(self, content: str, destination: str | None = None) -> None:
        """Write content to CloudWatch logs."""
        self._logger.info("scan_results_output", content=content)

    def write_scan_result(self, scan_result: Any) -> None:
        """Write scan result as structured JSON to CloudWatch."""
        # Log summary
        self._logger.info(
            "scan_summary",
            account_id=scan_result.account_id,
            total_resources=scan_result.total_resources,
            resources_with_waf=scan_result.resources_with_waf,
            resources_without_waf=scan_result.resources_without_waf,
            compliance_rate=scan_result.get_compliance_rate(),
            regions_scanned=scan_result.regions_scanned,
            errors_count=len(scan_result.errors),
        )

        # Log each unprotected resource for alerting
        for resource in scan_result.resources:
            if not resource.has_waf:
                self._logger.warning(
                    "unprotected_resource",
                    resource_arn=resource.arn,
                    resource_type=resource.resource_type.value,
                    resource_name=resource.name,
                    region=resource.region,
                    account_id=scan_result.account_id,
                    fronted_by_protected_cloudfront=resource.fronted_by_protected_cloudfront,
                )

        # Log errors
        for error in scan_result.errors:
            self._logger.error(
                "scan_error",
                region=error.get("region"),
                resource_type=error.get("resource_type"),
                error_message=error.get("message"),
            )


def handler(event: dict, context: Any) -> dict:
    """
    Entrypoint used when application is called as a lambda.
    AWS Lambda handler for Perimeter Guard scanner.

    Environment Variables:
        TARGET_ACCOUNTS: Comma-separated list of AWS account IDs to scan
        ASSUME_ROLE_NAME: Name of the IAM role to assume in target accounts
        EXTERNAL_ID: External ID for secure role assumption
        SCAN_REGIONS: Comma-separated list of AWS regions to scan
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)

    Args:
        event: Lambda event (can trigger manual scans with specific params)
        context: Lambda context

    Returns:
        Dict with scan results summary
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO")
    logger = CloudWatchLogger(level=log_level)

    target_accounts_str = os.environ.get("TARGET_ACCOUNTS", "")
    target_accounts = [a.strip() for a in target_accounts_str.split(",") if a.strip()]

    assume_role_name = os.environ.get("ASSUME_ROLE_NAME", "PerimeterGuardScanRole")
    external_id = os.environ.get("EXTERNAL_ID", "")

    scan_regions_str = os.environ.get("SCAN_REGIONS", "us-east-1")
    scan_regions = [r.strip() for r in scan_regions_str.split(",") if r.strip()]

    logger.info(
        "lambda_invoked",
        target_accounts_count=len(target_accounts),
        scan_regions=scan_regions,
        event_type=event.get("scan_type", "manual"),
    )

    # Results aggregation
    all_results = []
    errors = []

    # Create base AWS client (for local account or assuming roles)
    base_client = Boto3AWSClient(logger=logger)

    # If no target accounts configured, scan the local account only
    if not target_accounts:
        logger.info("No target accounts configured, scanning local account only")
        target_accounts = ["local"]

    for account_id in target_accounts:
        try:
            logger.info(f"Starting scan for account: {account_id}")
            logger.set_context(current_account=account_id)

            # Determine which client to use
            if account_id == "local":
                aws_client = base_client
            else:
                # Assume role in target account
                role_arn = f"arn:aws:iam::{account_id}:role/{assume_role_name}"
                aws_client = base_client.assume_role(
                    role_arn=role_arn,
                    session_name="perimeter-guard-lambda",
                    external_id=external_id if external_id else None,
                )

            # Create output adapter
            output = CloudWatchResultsOutput(logger=logger)

            # Create scanner and execute
            scanner = ScannerService(
                aws_client=aws_client,
                output=output,
                logger=logger,
            )

            scan_result = scanner.scan(regions=scan_regions)

            # Output results to CloudWatch
            output.write_scan_result(scan_result)

            # Aggregate results
            all_results.append({
                "account_id": scan_result.account_id,
                "total_resources": scan_result.total_resources,
                "resources_with_waf": scan_result.resources_with_waf,
                "resources_without_waf": scan_result.resources_without_waf,
                "compliance_rate": scan_result.get_compliance_rate(),
                "errors_count": len(scan_result.errors),
            })

            logger.info(
                f"Completed scan for account: {account_id}",
                total_resources=scan_result.total_resources,
                compliance_rate=f"{scan_result.get_compliance_rate():.1f}%",
            )

        except Exception as e:
            error_msg = f"Failed to scan account {account_id}: {str(e)}"
            logger.error(error_msg, exception=e)
            errors.append({
                "account_id": account_id,
                "error": str(e),
            })

    # Build response
    total_resources = sum(r["total_resources"] for r in all_results)
    total_protected = sum(r["resources_with_waf"] for r in all_results)
    total_unprotected = sum(r["resources_without_waf"] for r in all_results)

    response = {
        "statusCode": 200 if not errors else 207,  # 207 Multi-Status if partial failure
        "body": {
            "accounts_scanned": len(all_results),
            "accounts_failed": len(errors),
            "total_resources": total_resources,
            "resources_with_waf": total_protected,
            "resources_without_waf": total_unprotected,
            "overall_compliance_rate": (
                (total_protected / total_resources * 100) if total_resources > 0 else 100.0
            ),
            "results_by_account": all_results,
            "errors": errors,
        },
    }

    logger.info(
        "lambda_completed",
        accounts_scanned=len(all_results),
        accounts_failed=len(errors),
        total_resources=total_resources,
        overall_compliance_rate=response["body"]["overall_compliance_rate"],
    )

    return response
