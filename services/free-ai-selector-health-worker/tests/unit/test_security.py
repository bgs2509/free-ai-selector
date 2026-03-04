"""Тесты для app/utils/security.py — санитизация ошибок."""
import pytest
from app.utils.security import sanitize_error_message


class TestSanitizeErrorMessage:
    def test_google_ai_key(self):
        msg = "Error with key AIzaSyB1234567890abcdefghijklmnopqrstuvw"
        result = sanitize_error_message(msg)
        assert "AIza***" in result
        assert "SyB1234567890" not in result

    def test_openai_key(self):
        key = "sk-" + "a" * 48
        result = sanitize_error_message(f"Error: {key}")
        assert "sk-***" in result

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
        result = sanitize_error_message("Auth: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6")
        assert "Bearer ***" in result

    def test_basic_auth(self):
        result = sanitize_error_message("Auth: Basic dXNlcjpwYXNzd29yZDEyMzQ1Njc4OTA=")
        assert "Basic ***" in result

    def test_url_params(self):
        result = sanitize_error_message("GET https://api.com?key=secret123&token=abc456")
        assert "key=***" in result
        assert "token=***" in result

    def test_authorization_header(self):
        msg = """headers={'Authorization': 'Bearer long-secret-token-12345678901234567890'}"""
        result = sanitize_error_message(msg)
        assert "long-secret-token" not in result

    def test_cloudflare_id(self):
        cf_id = "a" * 32
        result = sanitize_error_message(f"Account: {cf_id}")
        assert "***" in result

    def test_exception_object(self):
        err = ValueError("sk-" + "a" * 48)
        result = sanitize_error_message(err)
        assert "sk-***" in result

    def test_no_false_positive(self):
        msg = "Simple error: connection refused"
        assert sanitize_error_message(msg) == msg
