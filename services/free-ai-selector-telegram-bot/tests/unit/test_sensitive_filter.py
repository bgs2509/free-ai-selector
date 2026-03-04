"""Тесты для app/utils/sensitive_filter.py."""
from app.utils.sensitive_filter import sanitize_sensitive_data


class TestSanitizeSensitiveData:
    def test_masks_password_field(self):
        event = {"event": "test", "password": "secret123"}
        result = sanitize_sensitive_data(None, None, event)
        assert result["password"] == "***REDACTED***"

    def test_masks_api_key_field(self):
        event = {"event": "test", "api_key": "sk-12345"}
        result = sanitize_sensitive_data(None, None, event)
        assert result["api_key"] == "***REDACTED***"

    def test_masks_token_field(self):
        event = {"event": "test", "token": "abc"}
        result = sanitize_sensitive_data(None, None, event)
        assert result["token"] == "***REDACTED***"

    def test_masks_telegram_bot_token(self):
        event = {"event": "test", "telegram_bot_token": "123:ABC"}
        result = sanitize_sensitive_data(None, None, event)
        assert result["telegram_bot_token"] == "***REDACTED***"

    def test_preserves_non_sensitive(self):
        event = {"event": "test", "model": "llama-3"}
        result = sanitize_sensitive_data(None, None, event)
        assert result["model"] == "llama-3"

    def test_masks_nested_dict(self):
        event = {"event": "test", "data": {"password": "secret"}}
        result = sanitize_sensitive_data(None, None, event)
        assert result["data"]["password"] == "***REDACTED***"

    def test_masks_sensitive_value_pattern(self):
        event = {"event": "test", "header": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0"}
        result = sanitize_sensitive_data(None, None, event)
        assert "eyJ" not in str(result["header"])

    def test_preserves_event_field(self):
        event = {"event": "test_event", "level": "info"}
        result = sanitize_sensitive_data(None, None, event)
        assert result["event"] == "test_event"
