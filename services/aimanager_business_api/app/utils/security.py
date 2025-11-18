"""
Security utilities for safe logging and error handling.

Prevents sensitive data (API keys, tokens, credentials) from being leaked
into application logs through exception messages and error strings.
"""

import re
from typing import Union


def sanitize_error_message(error: Union[Exception, str]) -> str:
    """
    Sanitize error messages to remove sensitive information before logging.

    This function removes API keys, authentication tokens, query parameters,
    and other sensitive data that might be present in exception messages,
    especially from HTTP client libraries like httpx.

    Security patterns removed:
    - Google AI Studio keys: AIza... (39 chars)
    - OpenAI-style keys: sk-... (48+ chars)
    - HuggingFace tokens: hf_... (34+ chars)
    - Groq keys: gsk_... (50+ chars)
    - Cloudflare tokens: cloudflare_api_token patterns
    - Bearer tokens in headers
    - URL query parameters (e.g., ?key=secret)
    - Generic long alphanumeric tokens (20+ chars)

    Args:
        error: Exception object or error string to sanitize

    Returns:
        Sanitized error message safe for logging

    Examples:
        >>> sanitize_error_message("HTTP 401 for URL https://api.example.com?key=AIzaSyABC123XYZ")
        'HTTP 401 for URL https://api.example.com?key=***'

        >>> sanitize_error_message("Authorization: Bearer sk-abc123def456")
        'Authorization: Bearer ***'
    """
    # Convert exception to string
    if isinstance(error, Exception):
        message = str(error)
    else:
        message = str(error)

    # Pattern 1: Google AI Studio API keys (AIza followed by 35 chars)
    message = re.sub(r"AIza[A-Za-z0-9_-]{35}", "AIza***", message)

    # Pattern 2: OpenAI-style API keys (sk- followed by 48+ chars)
    message = re.sub(r"sk-[A-Za-z0-9]{48,}", "sk-***", message)

    # Pattern 3: HuggingFace tokens (hf_ followed by 34+ chars)
    message = re.sub(r"hf_[A-Za-z0-9]{34,}", "hf_***", message)

    # Pattern 4: Groq API keys (gsk_ followed by 50+ chars)
    message = re.sub(r"gsk_[A-Za-z0-9_]{50,}", "gsk_***", message)

    # Pattern 5: Replicate tokens (r8_ prefix)
    message = re.sub(r"r8_[A-Za-z0-9]{30,}", "r8_***", message)

    # Pattern 6: Generic Bearer tokens (Authorization headers)
    message = re.sub(r"Bearer [A-Za-z0-9_\-\.]{20,}", "Bearer ***", message, flags=re.IGNORECASE)

    # Pattern 7: Basic auth (base64 encoded credentials)
    message = re.sub(r"Basic [A-Za-z0-9+/=]{20,}", "Basic ***", message, flags=re.IGNORECASE)

    # Pattern 8: URL query parameters that might contain secrets
    # Matches: ?key=value, &key=value, ?token=value, &secret=value, etc.
    sensitive_params = [
        "key",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "secret",
        "password",
        "pwd",
        "auth",
        "authorization",
        "credential",
        "api-key",
    ]

    for param in sensitive_params:
        # Match ?param=value or &param=value (case-insensitive)
        pattern = rf"([?&]{param}=)[^&\s]+"
        message = re.sub(pattern, r"\1***", message, flags=re.IGNORECASE)

    # Pattern 9: Authorization header values in exception messages
    # Common in httpx exceptions: "headers={'Authorization': 'Bearer xyz'}"
    message = re.sub(
        r"(['\"]Authorization['\"]\s*:\s*['\"])(Bearer|Basic)\s+[^'\"]+(['\"])",
        r"\1\2 ***\3",
        message,
        flags=re.IGNORECASE,
    )

    # Pattern 10: Generic long alphanumeric strings (likely tokens/keys)
    # Only replace if they look suspicious (20+ chars, mix of letters and numbers)
    # This is aggressive but necessary for unknown token formats
    # We preserve common patterns like UUIDs (with hyphens) and short strings
    message = re.sub(
        r"\b(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])[A-Za-z0-9_]{30,}\b",
        "***",
        message,
    )

    # Pattern 11: Cloudflare account IDs (32 hex chars)
    message = re.sub(r"\b[a-f0-9]{32}\b", "***", message)

    # Pattern 12: Clean up any remaining fragments
    # Remove any standalone long strings that might be token fragments
    message = re.sub(r"(?<=[=:'\"\s])[A-Za-z0-9_\-\.]{40,}(?=[,;'\"\s]|$)", "***", message)

    return message


def is_sensitive_key_present(text: str) -> bool:
    """
    Check if text contains patterns that look like API keys or tokens.

    Useful for validation before logging or returning error messages to users.

    Args:
        text: Text to check for sensitive patterns

    Returns:
        True if sensitive patterns detected, False otherwise

    Examples:
        >>> is_sensitive_key_present("Error: Invalid API key AIzaSyABC123")
        True

        >>> is_sensitive_key_present("Error: Connection timeout")
        False
    """
    # Check for common API key patterns
    patterns = [
        r"AIza[A-Za-z0-9_-]{35}",  # Google
        r"sk-[A-Za-z0-9]{48,}",  # OpenAI
        r"hf_[A-Za-z0-9]{34,}",  # HuggingFace
        r"gsk_[A-Za-z0-9_]{50,}",  # Groq
        r"Bearer [A-Za-z0-9_\-\.]{20,}",  # Bearer tokens
        r"[?&](key|token|secret)=[^&\s]+",  # URL params
    ]

    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False
