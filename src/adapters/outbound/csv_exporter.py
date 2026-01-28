"""CSV Exporter Adapter - Outputs scan results to CSV files."""
import csv
import os
from datetime import datetime

from src.domain.entities import Resource, ScanResult


class CSVExporter:
    """
    Implementation of OutputPort that writes scan results to CSV files.

    The CSV includes all resources with their WAF association status.
    """

    def write(self, scan_result: ScanResult, output_path: str) -> str:
        """
        Write scan results to a CSV file.

        Args:
            scan_result: The scan result to write
            output_path: Path for the output file. If no extension, .csv is added.
                        Use "stdout" to print to console instead.

        Returns:
            The actual path where data was written
        """
        # Handle stdout case
        if output_path.lower() == "stdout":
            return self._write_to_stdout(scan_result)

        # Ensure .csv extension
        if not output_path.endswith(".csv"):
            output_path += ".csv"

        # Create directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        rows = self._build_rows(scan_result)

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self._get_headers())
            writer.writeheader()
            writer.writerows(rows)

        return output_path

    def get_format_name(self) -> str:
        """Get the name of the output format."""
        return "CSV"

    def _get_headers(self) -> list[str]:
        """Get CSV column headers."""
        return [
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
            "Fronted By Resource",
            "Fronted By WAF",
            "Notes",
        ]

    def _build_rows(self, scan_result: ScanResult) -> list[dict]:
        """Build CSV rows from scan result."""
        rows = []
        for resource in scan_result.resources:
            rows.append(self._resource_to_row(resource))
        return rows

    def _resource_to_row(self, resource: Resource) -> dict:
        """Convert a Resource to a CSV row."""
        return {
            "Account ID": resource.account_id,
            "Region": resource.region,
            "Resource Type": resource.resource_type.display_name,
            "Resource Name": resource.name or "",
            "Resource ARN": resource.arn,
            "Has WAF": "Yes" if resource.has_waf() else "No",
            "WAF Name": resource.get_waf_name() or "",
            "WAF ARN": resource.get_waf_arn() or "",
            "Is Public": "Yes" if resource.is_public else "No",
            "Compliance Status": resource.get_compliance_status(),
            "Scanned At": resource.scanned_at.isoformat() if resource.scanned_at else "",
            "Fronted By Resource": resource.fronted_by_resource_arn or "",
            "Fronted By WAF": resource.fronted_by_waf.name if resource.fronted_by_waf else "",
            "Notes": resource.fronted_by_notes or "",
        }

    def _write_to_stdout(self, scan_result: ScanResult) -> str:
        """Write scan results to stdout."""
        import sys
        rows = self._build_rows(scan_result)
        writer = csv.DictWriter(sys.stdout, fieldnames=self._get_headers())
        writer.writeheader()
        writer.writerows(rows)
        return "stdout"


def generate_output_filename(scan_result: ScanResult, prefix: str = "waf-scan") -> str:
    """
    Generate a default output filename.

    Format: {prefix}-{account_id}-{timestamp}.csv
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{scan_result.account_id}-{timestamp}.csv"
