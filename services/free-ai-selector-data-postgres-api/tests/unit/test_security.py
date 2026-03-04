"""Тесты для app/utils/security.py — санитизация ошибок."""
import pytest
from app.utils.security import sanitize_error_message


class TestSanitizeErrorMessage:
    """Тесты для sanitize_error_message."""

    def test_google_ai_key(self):
        msg = "Error with key AIzaSyB1234567890abcdefghijklmnopqrstuvw"
        result = sanitize_error_message(msg)
        assert "AIza***" in result
        assert "SyB1234567890" not in result

    def test_openai_key(self):
        key = "sk-" + "a" * 48
        msg = f"Auth failed: {key}"
        result = sanitize_error_message(msg)
        assert "sk-***" in result
        assert key not in result

    def test_huggingface_token(self):
        token = "hf_" + "A" * 34
        result = sanitize_error_message(f"Token: {token}")
        assert "hf_***" in result

    def test_groq_key(self):
        key = "gsk_" + "x" * 50
        result = sanitize_error_message(f"Key: {key}")
        assert "gsk_***" in result

    def test_replicate_token(self):
        token = "r8_" + "B" * 30
        result = sanitize_error_message(f"Token: {token}")
        assert "r8_***" in result

    def test_bearer_token(self):
        result = sanitize_error_message("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6")
        assert "Bearer ***" in result

    def test_basic_auth(self):
        result = sanitize_error_message("Authorization: Basic dXNlcjpwYXNzd29yZDEyMzQ1Njc4OTA=")
        assert "Basic ***" in result

    def test_url_query_params(self):
        result = sanitize_error_message("GET https://api.example.com?key=secret123&token=abc456")
        assert "key=***" in result
        assert "token=***" in result

    def test_authorization_header_in_exception(self):
        msg = """headers={'Authorization': 'Bearer my-secret-token-value-here-1234567890'}"""
        result = sanitize_error_message(msg)
        assert "my-secret-token" not in result

    def test_cloudflare_account_id(self):
        cf_id = "a" * 32
        result = sanitize_error_message(f"Account: {cf_id}")
        assert "***" in result

    def test_exception_object(self):
        err = ValueError("sk-" + "a" * 48)
        result = sanitize_error_message(err)
        assert "sk-***" in result

    def test_no_false_positive_on_short_string(self):
        msg = "Simple error: connection refused"
        result = sanitize_error_message(msg)
        assert result == msg
