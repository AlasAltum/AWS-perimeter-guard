"""Logger Port - Interface for logging operations."""
from typing import Any, Protocol


class LoggerPort(Protocol):
    """
    Port interface for logging.

    Implementations could output to:
    - Console (for CLI usage)
    - CloudWatch Logs (for Lambda usage)
    - File (for debugging)
    """

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        ...

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        ...

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        ...

    def error(self, message: str, exception: Exception | None = None, **kwargs: Any) -> None:
        """Log an error message, optionally with exception details."""
        ...

    def set_level(self, level: str) -> None:
        """
        Set the logging level.

        Args:
            level: One of DEBUG, INFO, WARNING, ERROR
        """
        ...
