"""Inbound adapters - Entry points (CLI, Lambda)."""
from src.adapters.inbound.lambda_handler import handler as lambda_handler

__all__ = ["lambda_handler"]
