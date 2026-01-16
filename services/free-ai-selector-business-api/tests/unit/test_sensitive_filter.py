"""
Unit tests для SensitiveDataFilter.

Тестирует автоматическую фильтрацию секретов в логах.
"""

import pytest

from app.utils.sensitive_filter import (
    sanitize_sensitive_data,
    _is_sensitive_field,
    _contains_sensitive_pattern,
    _sanitize_value,
    _sanitize_dict,
    REDACTED,
)


class TestIsSensitiveField:
    """Тесты для проверки секретных полей по имени."""

    def test_common_sensitive_fields(self):
        """Общие секретные поля маскируются."""
        assert _is_sensitive_field("password") is True
        assert _is_sensitive_field("api_key") is True
        assert _is_sensitive_field("token") is True
        assert _is_sensitive_field("secret") is True
        assert _is_sensitive_field("authorization") is True

    def test_project_specific_fields(self):
        """Специфичные поля проекта маскируются."""
        assert _is_sensitive_field("groq_api_key") is True
        assert _is_sensitive_field("huggingface_api_key") is True
        assert _is_sensitive_field("telegram_bot_token") is True
        assert _is_sensitive_field("postgres_password") is True

    def test_case_insensitive(self):
        """Проверка регистронезависимости."""
        assert _is_sensitive_field("PASSWORD") is True
        assert _is_sensitive_field("Api_Key") is True
        assert _is_sensitive_field("TOKEN") is True

    def test_hyphen_to_underscore(self):
        """Дефисы заменяются на подчёркивания."""
        assert _is_sensitive_field("api-key") is True
        assert _is_sensitive_field("access-token") is True

    def test_safe_fields(self):
        """Безопасные поля не маскируются."""
        assert _is_sensitive_field("user") is False
        assert _is_sensitive_field("email") is False
        assert _is_sensitive_field("message") is False
        assert _is_sensitive_field("request_id") is False


class TestContainsSensitivePattern:
    """Тесты для проверки паттернов секретов в значениях."""

    def test_google_ai_pattern(self):
        """Google AI ключи маскируются."""
        # AIza + 35 символов
        assert _contains_sensitive_pattern("AIzaSyABC123XYZ789DEF456GHI012JKL345MN6") is True

    def test_openai_style_pattern(self):
        """OpenAI-style ключи маскируются."""
        # sk- + 48+ символов
        long_key = "sk-" + "a" * 50
        assert _contains_sensitive_pattern(long_key) is True

    def test_groq_pattern(self):
        """Groq ключи маскируются."""
        # gsk_ + 50+ символов
        groq_key = "gsk_" + "X" * 55
        assert _contains_sensitive_pattern(groq_key) is True

    def test_huggingface_pattern(self):
        """HuggingFace ключи маскируются."""
        # hf_ + 34+ символов
        hf_key = "hf_" + "Y" * 40
        assert _contains_sensitive_pattern(hf_key) is True

    def test_jwt_pattern(self):
        """JWT токены маскируются."""
        jwt_prefix = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        assert _contains_sensitive_pattern(jwt_prefix) is True

    def test_bearer_pattern(self):
        """Bearer токены маскируются."""
        bearer = "Bearer abcdefghijklmnopqrstuvwxyz1234567890"
        assert _contains_sensitive_pattern(bearer) is True

    def test_safe_values(self):
        """Безопасные значения не маскируются."""
        assert _contains_sensitive_pattern("normal text") is False
        assert _contains_sensitive_pattern("user@example.com") is False
        assert _contains_sensitive_pattern("12345") is False


class TestSanitizeValue:
    """Тесты для рекурсивной очистки значений."""

    def test_none_value(self):
        """None остаётся None."""
        assert _sanitize_value(None) is None

    def test_safe_string(self):
        """Безопасные строки не изменяются."""
        assert _sanitize_value("hello world") == "hello world"

    def test_sensitive_string(self):
        """Строки с секретами маскируются."""
        key = "AIzaSyABC123XYZ789DEF456GHI012JKL345MN6"
        assert _sanitize_value(key) == REDACTED

    def test_list_processing(self):
        """Списки обрабатываются рекурсивно."""
        input_list = ["normal", "AIzaSyABC123XYZ789DEF456GHI012JKL345MN6", "also normal"]
        result = _sanitize_value(input_list)
        assert result[0] == "normal"
        assert result[1] == REDACTED
        assert result[2] == "also normal"

    def test_tuple_processing(self):
        """Кортежи обрабатываются рекурсивно."""
        input_tuple = ("normal", "sk-" + "a" * 50)
        result = _sanitize_value(input_tuple)
        assert isinstance(result, tuple)
        assert result[0] == "normal"
        assert result[1] == REDACTED

    def test_dict_processing(self):
        """Словари обрабатываются рекурсивно."""
        input_dict = {"user": "john", "api_key": "secret123"}
        result = _sanitize_value(input_dict)
        assert result["user"] == "john"
        assert result["api_key"] == REDACTED


class TestSanitizeDict:
    """Тесты для очистки словарей."""

    def test_sanitize_by_field_name(self):
        """Поля с секретными именами маскируются."""
        event = {"user": "john", "api_key": "sk-abc123", "password": "secret"}
        result = _sanitize_dict(event)
        assert result["user"] == "john"
        assert result["api_key"] == REDACTED
        assert result["password"] == REDACTED

    def test_sanitize_by_value_pattern(self):
        """Значения с паттернами секретов маскируются."""
        event = {"message": "Token is AIzaSyABC123XYZ789DEF456GHI012JKL345MN6"}
        result = _sanitize_dict(event)
        assert result["message"] == REDACTED

    def test_sanitize_nested_dict(self):
        """Вложенные словари обрабатываются рекурсивно."""
        event = {
            "config": {
                "database": {
                    "password": "secret123",
                    "host": "localhost"
                }
            }
        }
        result = _sanitize_dict(event)
        assert result["config"]["database"]["password"] == REDACTED
        assert result["config"]["database"]["host"] == "localhost"

    def test_sanitize_list_in_dict(self):
        """Списки в словарях обрабатываются рекурсивно."""
        event = {"tokens": ["sk-" + "a" * 50, "normal"]}
        result = _sanitize_dict(event)
        assert result["tokens"][0] == REDACTED
        assert result["tokens"][1] == "normal"


class TestSanitizeSensitiveData:
    """Тесты для structlog processor."""

    def test_processor_signature(self):
        """Processor имеет правильную сигнатуру."""
        event = {"user": "john", "api_key": "secret"}
        result = sanitize_sensitive_data(None, "info", event)
        assert isinstance(result, dict)

    def test_processor_filters_secrets(self):
        """Processor фильтрует секреты."""
        event = {
            "event": "api_call",
            "groq_api_key": "gsk_" + "X" * 55,
            "user_id": "123"
        }
        result = sanitize_sensitive_data(None, "info", event)
        assert result["event"] == "api_call"
        assert result["groq_api_key"] == REDACTED
        assert result["user_id"] == "123"

    def test_processor_preserves_structure(self):
        """Processor сохраняет структуру события."""
        event = {
            "event": "test",
            "nested": {"key": "value"},
            "list": [1, 2, 3]
        }
        result = sanitize_sensitive_data(None, "info", event)
        assert result["event"] == "test"
        assert result["nested"]["key"] == "value"
        assert result["list"] == [1, 2, 3]


class TestProjectSpecificFields:
    """Тесты для специфичных полей проекта."""

    def test_all_provider_keys_masked(self):
        """Все API ключи провайдеров маскируются."""
        provider_fields = [
            "groq_api_key",
            "cerebras_api_key",
            "sambanova_api_key",
            "huggingface_api_key",
            "cloudflare_api_token",
            "deepseek_api_key",
            "openrouter_api_key",
            "github_token",
            "fireworks_api_key",
            "hyperbolic_api_key",
            "novita_api_key",
            "scaleway_api_key",
            "kluster_api_key",
            "nebius_api_key",
        ]

        for field in provider_fields:
            event = {field: "some_secret_value"}
            result = sanitize_sensitive_data(None, "info", event)
            assert result[field] == REDACTED, f"Field {field} should be redacted"

    def test_telegram_and_db_fields(self):
        """Telegram и DB поля маскируются."""
        event = {
            "telegram_bot_token": "123456:ABC-DEF",
            "bot_token": "789012:GHI-JKL",
            "postgres_password": "dbsecret",
            "database_url": "postgresql://user:pass@host/db"
        }
        result = sanitize_sensitive_data(None, "info", event)
        assert result["telegram_bot_token"] == REDACTED
        assert result["bot_token"] == REDACTED
        assert result["postgres_password"] == REDACTED
        assert result["database_url"] == REDACTED
