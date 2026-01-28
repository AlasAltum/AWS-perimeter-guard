"""AWS Perimeter Guard - Main entry point.

Scan AWS resources for WAF associations.
"""
from src.adapters.inbound.cli_adapter import main as cli_main


def main() -> None:
    """Main entry point - delegates to CLI adapter."""
    cli_main()


if __name__ == "__main__":
    main()
