"""Output Port - Interface for outputting scan results."""
from typing import Protocol

from src.domain.entities import ScanResult


class OutputPort(Protocol):
    """
    Port interface for outputting scan results.

    Implementations could output to:
    - CSV file (main use case)
    - Console (for debugging)
    - S3 bucket (future)
    """

    def write(self, scan_result: ScanResult, output_path: str) -> str:
        """
        Write scan results to the specified output.

        Args:
            scan_result: The scan result to write
            output_path: Path or destination for the output

        Returns:
            The actual path/location where data was written
        """
        ...

    def get_format_name(self) -> str:
        """
        Get the name of the output format.

        Returns:
            Format name (e.g., "CSV", "JSON", "Console")
        """
        ...
