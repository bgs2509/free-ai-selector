# План фичи: F009 Security Hardening & Reverse Proxy Alignment

**Дата**: 2026-01-01
**Архитектор**: AI Agent (Architect)
**Feature ID**: F009
**Статус**: AWAITING_APPROVAL

---

## 1. Обзор

### 1.1 Цель

Внедрить defensive-in-depth подход к безопасности логирования и привести конфигурацию reverse proxy к стандартам .aidd Framework:

1. **SensitiveDataFilter** — structlog processor для автоматической фильтрации секретов
2. **ROOT_PATH в Data API** — консистентность с Business API
3. **Удаление hardcoded mount** — следование best practice

### 1.2 Связь с существующим функционалом

| Фича | Связь |
|------|-------|
| F006 (aidd-logging) | Все 4 сервиса уже используют structlog — расширяем chain |
| F005 (openapi-docs-fix) | ROOT_PATH уже в Business API — добавляем в Data API |
| security.py | sanitize_error_message() — сохраняем для обратной совместимости |

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Изменения |
|--------|-----------|
| `free-ai-selector-business-api` | sensitive_filter.py, logger.py, main.py (удалить hardcode) |
| `free-ai-selector-data-postgres-api` | sensitive_filter.py, logger.py, main.py (ROOT_PATH) |
| `free-ai-selector-telegram-bot` | sensitive_filter.py, logger.py |
| `free-ai-selector-health-worker` | sensitive_filter.py, logger.py |

### 2.2 Точки интеграции

```
logger.py:setup_logging()
    ↓
shared_processors = [
    structlog.contextvars.merge_contextvars,
    sanitize_sensitive_data,  # ← ДОБАВИТЬ (из sensitive_filter.py)
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]
```

### 2.3 Существующие зависимости

| Файл | Импорты | Действие |
|------|---------|----------|
| `utils/security.py` | Определяет `sanitize_error_message()` | Сохранить |
| `utils/logger.py` | `structlog`, `logging`, `os` | Добавить import `sensitive_filter` |
| `utils/__init__.py` | Re-export security | Добавить re-export `sensitive_filter` |

---

## 3. План изменений

### 3.1 Новые компоненты

| # | Компонент | Расположение | Описание |
|---|-----------|--------------|----------|
| 1 | `sensitive_filter.py` | `business-api/app/utils/` | SensitiveDataFilter processor |
| 2 | `sensitive_filter.py` | `data-postgres-api/app/utils/` | Копия (идентичный код) |
| 3 | `sensitive_filter.py` | `telegram-bot/app/utils/` | Копия (идентичный код) |
| 4 | `sensitive_filter.py` | `health-worker/app/utils/` | Копия (идентичный код) |
| 5 | `test_sensitive_filter.py` | `business-api/tests/unit/` | Unit тесты |

### 3.2 Модификации существующего кода

| # | Файл | Изменение | Строки |
|---|------|-----------|--------|
| 1 | `business-api/app/utils/logger.py` | Добавить import и processor | +3 |
| 2 | `data-postgres-api/app/utils/logger.py` | Добавить import и processor | +3 |
| 3 | `telegram-bot/app/utils/logger.py` | Добавить import и processor | +3 |
| 4 | `health-worker/app/utils/logger.py` | Добавить import и processor | +3 |
| 5 | `data-postgres-api/app/main.py` | Добавить ROOT_PATH | +5 |
| 6 | `business-api/app/main.py` | Удалить hardcoded mount | -2 |
| 7 | `docker-compose.yml` | ROOT_PATH для Data API | +1 |

### 3.3 Новые зависимости

Нет новых зависимостей — используем только `structlog` (уже установлен).

---

## 4. Детальный дизайн

### 4.1 sensitive_filter.py

```python
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
```

### 4.2 Изменения в logger.py

```python
# ДОБАВИТЬ импорт (после существующих)
from app.utils.sensitive_filter import sanitize_sensitive_data

# ИЗМЕНИТЬ shared_processors
shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    sanitize_sensitive_data,  # ← ДОБАВИТЬ (ПЕРЕД add_log_level!)
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]
```

### 4.3 Изменения в Data API main.py

```python
# ДОБАВИТЬ после строки SERVICE_VERSION
ROOT_PATH = os.getenv("ROOT_PATH", "")

# ИЗМЕНИТЬ FastAPI app
app = FastAPI(
    title="AI Manager Platform - Data API",
    description="...",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=ROOT_PATH,  # ← ДОБАВИТЬ
    lifespan=lifespan,
)
```

### 4.4 Изменения в Business API main.py

```python
# УДАЛИТЬ строки 154-155:
# app.mount("/free-ai-selector/static", StaticFiles(directory=static_dir), name="static-proxy")

# ОСТАВИТЬ только:
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
```

### 4.5 Изменения в docker-compose.yml

```yaml
free-ai-selector-data-postgres-api:
  environment:
    # Существующие переменные...
    - ROOT_PATH=${DATA_API_ROOT_PATH:-}  # ← ДОБАВИТЬ
```

---

## 5. Влияние на существующие тесты

### 5.1 Ожидаемое влияние

| Категория | Влияние |
|-----------|---------|
| Существующие unit тесты | ✅ Без изменений |
| Существующие integration тесты | ✅ Без изменений |
| Logger behavior | Изменён: секреты автоматически маскируются |

### 5.2 Новые тесты

```python
# test_sensitive_filter.py

def test_sanitize_by_field_name():
    """Поля с секретными именами маскируются."""
    event = {"user": "john", "api_key": "sk-abc123"}
    result = sanitize_sensitive_data(None, "info", event)
    assert result["user"] == "john"
    assert result["api_key"] == "***REDACTED***"

def test_sanitize_by_value_pattern():
    """Значения с паттернами секретов маскируются."""
    event = {"message": "Token is AIzaSyABC123XYZ789DEF456GHI"}
    result = sanitize_sensitive_data(None, "info", event)
    assert "***REDACTED***" in result["message"]

def test_sanitize_nested_dict():
    """Nested dicts обрабатываются рекурсивно."""
    event = {"config": {"database": {"password": "secret123"}}}
    result = sanitize_sensitive_data(None, "info", event)
    assert result["config"]["database"]["password"] == "***REDACTED***"

def test_sanitize_list():
    """Lists обрабатываются рекурсивно."""
    event = {"tokens": ["sk-abc123xyz456", "normal"]}
    result = sanitize_sensitive_data(None, "info", event)
    assert result["tokens"][0] == "***REDACTED***"
    assert result["tokens"][1] == "normal"

def test_project_specific_fields():
    """Специфичные поля проекта маскируются."""
    event = {"groq_api_key": "gsk_abc", "huggingface_api_key": "hf_xyz"}
    result = sanitize_sensitive_data(None, "info", event)
    assert result["groq_api_key"] == "***REDACTED***"
    assert result["huggingface_api_key"] == "***REDACTED***"
```

---

## 6. План интеграции

### Этап 1: Создание sensitive_filter.py (все 4 сервиса)

| # | Действие | Сервис |
|---|----------|--------|
| 1.1 | Создать `sensitive_filter.py` | business-api |
| 1.2 | Скопировать `sensitive_filter.py` | data-postgres-api |
| 1.3 | Скопировать `sensitive_filter.py` | telegram-bot |
| 1.4 | Скопировать `sensitive_filter.py` | health-worker |

### Этап 2: Обновление logger.py (все 4 сервиса)

| # | Действие | Сервис |
|---|----------|--------|
| 2.1 | Добавить import и processor | business-api |
| 2.2 | Добавить import и processor | data-postgres-api |
| 2.3 | Добавить import и processor | telegram-bot |
| 2.4 | Добавить import и processor | health-worker |

### Этап 3: ROOT_PATH для Data API

| # | Действие | Файл |
|---|----------|------|
| 3.1 | Добавить ROOT_PATH env var | data-postgres-api/main.py |
| 3.2 | Добавить root_path в FastAPI | data-postgres-api/main.py |
| 3.3 | Добавить ROOT_PATH в env | docker-compose.yml |

### Этап 4: Удаление hardcoded mount

| # | Действие | Файл |
|---|----------|------|
| 4.1 | Удалить второй mount | business-api/main.py |

### Этап 5: Тестирование

| # | Действие |
|---|----------|
| 5.1 | Создать unit тесты |
| 5.2 | Запустить `make test` |
| 5.3 | Проверить логи на фильтрацию |

---

## 7. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| R-001 | False positive — полезные данные маскируются | Средняя | Низкое | Паттерны настроены консервативно |
| R-002 | Performance degradation | Низкая | Среднее | processor выполняется O(n) по ключам dict |
| R-003 | nginx config incompatibility | Низкая | Высокое | Проверить текущий nginx config на VPS |
| R-004 | Circular import | Низкая | Высокое | sensitive_filter.py не импортирует другие модули проекта |

---

## 8. Обратная совместимость

| Аспект | Совместимость |
|--------|---------------|
| Существующие API | ✅ Без изменений |
| Существующие логи | ✅ Формат сохраняется, добавляется фильтрация |
| sanitize_error_message() | ✅ Сохраняется для legacy кода |
| ROOT_PATH (Business API) | ✅ Без изменений |
| StaticFiles на localhost | ✅ Работает без изменений |

---

## 9. Чеклист готовности

### Перед началом реализации

- [x] PRD утверждён (PRD_READY)
- [x] Research завершён (RESEARCH_DONE)
- [x] Точки интеграции определены
- [x] Изменения минимизированы
- [x] Риски оценены

### Требуется подтверждение

- [ ] **План утверждён пользователем**

---

## Качественные ворота

### PLAN_APPROVED Checklist

- [x] Точки интеграции определены (logger.py:shared_processors)
- [x] Необходимые изменения описаны (12 файлов)
- [x] Риски учтены (4 риска с митигацией)
- [x] Обратная совместимость обеспечена
- [ ] **План утверждён пользователем**

---

## Следующий шаг

После утверждения плана:

```bash
/aidd-generate
```
