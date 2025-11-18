"""
Shared utilities for AI Manager Platform services.

This package contains common utilities used across all microservices
to ensure consistency and reduce code duplication.
"""

from .security import sanitize_error_message

__all__ = ["sanitize_error_message"]
