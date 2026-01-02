"""
Автоматическая фильтрация секретных данных в логах.

Structlog processor для defensive-in-depth защиты —
секреты маскируются автоматически без явного вызова функций.
"""

import re
from typing import Any

# Поля, которые ВСЕГДА маскируются (case-insensitive)
SENSITIVE_FIELD_NAMES: set[str] = {
    # Общие
    "password", "passwd", "pwd", "secret", "api_key", "apikey",
    "token", "access_token", "refresh_token", "bearer", "authorization",
    "database_url", "connection_string",

    # Специфичные для проекта (16 провайдеров)
    "google_ai_studio_api_key", "groq_api_key", "cerebras_api_key",
    "sambanova_api_key", "huggingface_api_key", "cloudflare_api_token",
    "cloudflare_account_id", "deepseek_api_key", "cohere_api_key",
    "openrouter_api_key", "github_token", "fireworks_api_key",
    "hyperbolic_api_key", "novita_api_key", "scaleway_api_key",
    "kluster_api_key", "nebius_api_key",

    # Telegram & DB
    "telegram_bot_token", "bot_token", "postgres_password",
}

# Паттерны для поиска секретов в значениях
SENSITIVE_VALUE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),       # Google AI
    re.compile(r"sk-[A-Za-z0-9]{48,}"),          # OpenAI-style
    re.compile(r"gsk_[A-Za-z0-9_]{50,}"),        # Groq
    re.compile(r"hf_[A-Za-z0-9]{34,}"),          # HuggingFace
    re.compile(r"r8_[A-Za-z0-9]{30,}"),          # Replicate
    re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ"),       # JWT (prefix)
    re.compile(r"Bearer\s+[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
]

REDACTED = "***REDACTED***"


def _is_sensitive_field(field_name: str) -> bool:
    """Проверить, является ли поле секретным по имени."""
    normalized = field_name.lower().replace("-", "_")
    return normalized in SENSITIVE_FIELD_NAMES


def _contains_sensitive_pattern(value: str) -> bool:
    """Проверить, содержит ли значение паттерн секрета."""
    for pattern in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(value):
            return True
    return False


def _sanitize_value(value: Any) -> Any:
    """Рекурсивно очистить значение от секретов."""
    if value is None:
        return value

    if isinstance(value, str):
        if _contains_sensitive_pattern(value):
            return REDACTED
        return value

    if isinstance(value, dict):
        return _sanitize_dict(value)

    if isinstance(value, (list, tuple)):
        return type(value)(_sanitize_value(item) for item in value)

    return value


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Рекурсивно очистить словарь от секретных данных."""
    result = {}
    for key, value in data.items():
        if _is_sensitive_field(key):
            result[key] = REDACTED
        else:
            result[key] = _sanitize_value(value)
    return result


def sanitize_sensitive_data(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Structlog processor для автоматической фильтрации секретов.

    Добавляется в chain ПЕРЕД add_log_level для защиты ВСЕХ логов.

    Args:
        logger: Логгер (не используется).
        method_name: Название метода логирования.
        event_dict: Словарь события.

    Returns:
        Очищенный словарь события.
    """
    return _sanitize_dict(event_dict)
