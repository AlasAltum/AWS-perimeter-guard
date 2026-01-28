"""Console Logger Adapter - Outputs logs to console/stdout."""
import sys
from datetime import datetime
from typing import Any


class ConsoleLogger:
    """
    Implementation of LoggerPort that writes logs to console.

    Used for CLI-based execution.
    """

    LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}

    def __init__(self, level: str = "INFO", use_colors: bool = True):
        """
        Initialize the console logger.

        Args:
            level: Minimum log level to output (DEBUG, INFO, WARNING, ERROR)
            use_colors: Whether to use ANSI colors in output
        """
        self._level = self.LEVELS.get(level.upper(), 20)
        self._use_colors = use_colors and sys.stdout.isatty()

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

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal log method."""
        level_value = self.LEVELS.get(level, 20)
        if level_value < self._level:
            return

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        level_str = self._colorize_level(level) if self._use_colors else level

        output = f"[{timestamp}] {level_str}: {message}"

        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            output += f" ({details})"

        print(output, file=sys.stderr if level == "ERROR" else sys.stdout)

    def _colorize_level(self, level: str) -> str:
        """Add ANSI color codes to log level."""
        colors = {
            "DEBUG": "\033[36m",    # Cyan
            "INFO": "\033[32m",     # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",    # Red
        }
        reset = "\033[0m"
        color = colors.get(level, "")
        return f"{color}{level}{reset}"
