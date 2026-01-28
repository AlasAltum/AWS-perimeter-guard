"""CloudWatch Logger Adapter - Outputs structured logs to CloudWatch."""
import json
from datetime import datetime
from typing import Any


class CloudWatchLogger:
    """
    Implementation of LoggerPort that writes structured JSON logs.

    Used for Lambda execution where logs go to CloudWatch.
    The JSON format enables CloudWatch Insights queries.
    """

    LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

    def __init__(self, level: str = "INFO", context: dict | None = None):
        """
        Initialize the CloudWatch logger.

        Args:
            level: Minimum log level to output
            context: Additional context to include in all log entries
        """
        self._level = self.LEVELS.get(level.upper(), 20)
        self._context = context or {}

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, exception: Exception | None = None, **kwargs: Any) -> None:
        """Log an error message, optionally with exception details."""
        if exception:
            kwargs["error"] = str(exception)
            kwargs["error_type"] = type(exception).__name__
        self._log("ERROR", message, **kwargs)

    def set_level(self, level: str) -> None:
        """Set the logging level."""
        self._level = self.LEVELS.get(level.upper(), 20)

    def set_context(self, **kwargs: Any) -> None:
        """
        Set additional context to include in all log entries.

        Useful for adding scan_id, account_id, etc.
        """
        self._context.update(kwargs)

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal log method - outputs JSON."""
        level_value = self.LEVELS.get(level, 20)
        if level_value < self._level:
            return

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **self._context,
            **kwargs,
        }

        # Print JSON - Lambda runtime captures this to CloudWatch
        print(json.dumps(log_entry, default=str))
