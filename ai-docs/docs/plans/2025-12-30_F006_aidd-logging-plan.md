---
feature_id: "F006"
feature_name: "aidd-logging"
title: "Plan: Приведение логирования к стандартам AIDD Framework"
created: "2025-12-30"
author: "AI (Architect)"
type: "plan"
status: "APPROVED"
version: 1
mode: "FEATURE"
services: ["free-ai-selector-business-api", "free-ai-selector-data-postgres-api", "free-ai-selector-telegram-bot", "free-ai-selector-health-worker"]
---

# План фичи: F006 aidd-logging

## 1. Обзор

### 1.1 Цель

Полная миграция логирования на structlog с реализацией Log-Driven Design:
- Замена стандартного `logging` на `structlog`
- Добавление сквозной трассировки (correlation_id)
- Реализация `log_decision()` для понимания AI-выбора
- Добавление `duration_ms` для метрик производительности

### 1.2 Scope

| В scope | Вне scope |
|---------|-----------|
| structlog конфигурация | causation_id (следующая итерация) |
| ContextVars middleware | ELK интеграция |
| correlation_id между сервисами | Centralized logging |
| log_decision() для process_prompt | Полная структуризация всех логов |
| duration_ms в request_completed | Изменение уровней логирования |

### 1.3 Затрагиваемые сервисы

| Сервис | Изменения |
|--------|-----------|
| Business API | logger.py, request_id.py, log_helpers.py, main.py, process_prompt.py, data_api_client.py |
| Data API | logger.py, request_id.py, main.py |
| TG Bot | logger.py, request_id.py, main.py |
| Health Worker | logger.py, main.py |

---

## 2. Анализ существующего кода

### 2.1 Текущая конфигурация

Все 4 сервиса используют идентичный паттерн:
```python
logging.basicConfig(
    level=LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "'
    + SERVICE_NAME
    + '", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)
```

### 2.2 Существующие компоненты для сохранения

| Компонент | Файл | Действие |
|-----------|------|----------|
| `sanitize_error_message()` | `app/utils/security.py` | Интегрировать в structlog processors |
| request_id middleware | Business/Data API main.py | Мигрировать на ContextVars |
| JSON формат логов | Все сервисы | Сохранить обратную совместимость |

### 2.3 Точки интеграции

```
TG Bot (генерирует correlation_id)
    │
    ▼ X-Correlation-ID
Business API (middleware → ContextVars)
    │
    ▼ X-Correlation-ID
Data API (middleware → ContextVars)
```

---

## 3. План изменений

### 3.1 Новые компоненты

| Компонент | Сервис | Расположение | Описание |
|-----------|--------|--------------|----------|
| logger.py | Business API | `app/utils/logger.py` | structlog конфигурация, setup_logging(), get_logger() |
| request_id.py | Business API | `app/utils/request_id.py` | ContextVars для request_id, correlation_id |
| log_helpers.py | Business API | `app/utils/log_helpers.py` | log_decision(), log_request_started/completed |
| logger.py | Data API | `app/utils/logger.py` | structlog конфигурация (упрощённая) |
| request_id.py | Data API | `app/utils/request_id.py` | ContextVars (аналогично Business API) |
| logger.py | TG Bot | `app/utils/logger.py` | structlog конфигурация + user_id в контексте |
| request_id.py | TG Bot | `app/utils/request_id.py` | ContextVars + генерация correlation_id |
| logger.py | Health Worker | `app/utils/logger.py` | structlog конфигурация + job_id |

### 3.2 Модификации существующего кода

#### Business API

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/main.py` | Заменить `logging.basicConfig()` на `setup_logging()` | FR-001 |
| `app/main.py` | Мигрировать middleware на ContextVars | FR-003, FR-004 |
| `app/main.py` | Добавить duration_ms в request_completed | FR-011 |
| `app/application/use_cases/process_prompt.py` | Добавить `log_decision()` для выбора модели | FR-010 |
| `app/application/use_cases/process_prompt.py` | Добавить `log_decision()` для fallback | FR-010 |
| `app/infrastructure/http_clients/data_api_client.py` | Добавить X-Correlation-ID header | FR-004 |
| `requirements.txt` | Добавить structlog>=24.0.0 | FR-001 |

#### Data API

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/main.py` | Заменить `logging.basicConfig()` на `setup_logging()` | FR-001 |
| `app/main.py` | Мигрировать middleware на ContextVars | FR-003, FR-004 |
| `app/main.py` | Добавить duration_ms в request_completed | FR-011 |
| `requirements.txt` | Добавить structlog>=24.0.0 | FR-001 |

#### TG Bot

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/main.py` | Заменить `logging.basicConfig()` на `setup_logging()` | FR-001 |
| `app/main.py` | Генерировать correlation_id при получении сообщения | FR-013 |
| `app/main.py` | Добавить X-Correlation-ID в вызовы Business API | FR-004 |
| `app/main.py` | Добавить user_id в ContextVars | FR-020 |
| `requirements.txt` | Добавить structlog>=24.0.0 | FR-001 |

#### Health Worker

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/main.py` | Заменить `logging.basicConfig()` на `setup_logging()` | FR-001 |
| `app/main.py` | Добавить job_id для циклов проверок | FR-014 |
| `app/main.py` | Добавить duration_ms для health checks | FR-011 |
| `requirements.txt` | Добавить structlog>=24.0.0 | FR-001 |

### 3.3 Новые зависимости

| Зависимость | Версия | Назначение | Сервисы |
|-------------|--------|------------|---------|
| structlog | >=24.0.0 | Структурированное логирование | Все 4 |

---

## 4. Детальный дизайн

### 4.1 logger.py (общий для всех сервисов)

```python
"""Структурированное логирование по Log-Driven Design."""
import logging
import os
from typing import Any
import structlog

# Константы
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json или console

def setup_logging(service_name: str) -> None:
    """Настроить structlog."""
    json_logs = LOG_FORMAT == "json"

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service=service_name)

def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Получить логгер."""
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(module=name)
    return logger
```

### 4.2 request_id.py (для API сервисов)

```python
"""ContextVars для трассировки запросов."""
import uuid
from contextvars import ContextVar

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"

def generate_id() -> str:
    return uuid.uuid4().hex

def get_request_id() -> str | None:
    return _request_id_ctx.get()

def set_request_id(value: str | None) -> None:
    _request_id_ctx.set(value)

def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()

def set_correlation_id(value: str | None) -> None:
    _correlation_id_ctx.set(value)

def get_user_id() -> str | None:
    return _user_id_ctx.get()

def set_user_id(value: str | None) -> None:
    _user_id_ctx.set(value)

def setup_tracing_context(
    request_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Установить контекст трассировки."""
    if request_id is None:
        request_id = generate_id()

    set_request_id(request_id)
    set_correlation_id(correlation_id or request_id)
    set_user_id(user_id)

    # Биндим к structlog
    import structlog
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        correlation_id=correlation_id or request_id,
    )
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)

def clear_tracing_context() -> None:
    """Очистить контекст."""
    set_request_id(None)
    set_correlation_id(None)
    set_user_id(None)
    import structlog
    structlog.contextvars.unbind_contextvars("request_id", "correlation_id", "user_id")

def create_tracing_headers() -> dict[str, str]:
    """Создать заголовки для исходящего запроса."""
    headers = {}
    correlation_id = get_correlation_id()
    if correlation_id:
        headers[CORRELATION_ID_HEADER] = correlation_id
    request_id = get_request_id()
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    return headers
```

### 4.3 log_helpers.py (для Business API)

```python
"""Хелперы для логирования решений."""
import time
from typing import Any, Literal
import structlog

DecisionType = Literal["ACCEPT", "REJECT", "RETRY", "SKIP", "FALLBACK"]

def log_decision(
    logger: structlog.BoundLogger,
    decision: DecisionType,
    reason: str,
    evaluated_conditions: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """Залогировать бизнес-решение."""
    log_data = {
        "decision": decision,
        "reason": reason,
    }
    if evaluated_conditions:
        log_data["evaluated_conditions"] = evaluated_conditions
    log_data.update(kwargs)

    if decision in ("REJECT", "RETRY", "FALLBACK"):
        logger.warning("decision_made", **log_data)
    else:
        logger.info("decision_made", **log_data)

def log_request_started(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    **kwargs: Any,
) -> float:
    """Залогировать начало запроса."""
    logger.info("request_started", method=method, path=path, **kwargs)
    return time.perf_counter()

def log_request_completed(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    start_time: float,
    status_code: int,
    **kwargs: Any,
) -> None:
    """Залогировать завершение запроса."""
    duration_ms = (time.perf_counter() - start_time) * 1000
    log_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    log_data.update(kwargs)

    if status_code >= 500:
        logger.error("request_completed", **log_data)
    elif status_code >= 400:
        logger.warning("request_completed", **log_data)
    else:
        logger.info("request_completed", **log_data)
```

### 4.4 Изменения в main.py (Business API)

```python
# Заменить:
import logging
logging.basicConfig(...)
logger = logging.getLogger(__name__)

# На:
from app.utils.logger import setup_logging, get_logger
from app.utils.request_id import (
    setup_tracing_context, clear_tracing_context,
    REQUEST_ID_HEADER, CORRELATION_ID_HEADER, generate_id,
)
from app.utils.log_helpers import log_request_started, log_request_completed

setup_logging(SERVICE_NAME)
logger = get_logger(__name__)

# Заменить middleware:
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    # Извлечь из заголовков
    request_id = request.headers.get(REQUEST_ID_HEADER, generate_id())
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, request_id)

    # Установить контекст
    setup_tracing_context(request_id=request_id, correlation_id=correlation_id)

    # Логировать начало
    start_time = log_request_started(
        logger, method=request.method, path=request.url.path
    )

    try:
        response = await call_next(request)

        # Добавить заголовки в ответ
        response.headers[REQUEST_ID_HEADER] = request_id

        # Логировать завершение с duration_ms
        log_request_completed(
            logger,
            method=request.method,
            path=request.url.path,
            start_time=start_time,
            status_code=response.status_code,
        )

        return response
    finally:
        clear_tracing_context()
```

### 4.5 Изменения в process_prompt.py

```python
from app.utils.log_helpers import log_decision

# В execute(), после выбора модели:
best_model = self._select_best_model(models)
log_decision(
    logger,
    decision="ACCEPT",
    reason="highest_reliability_score",
    evaluated_conditions={
        "models_count": len(models),
        "selected_model": best_model.name,
        "selected_provider": best_model.provider,
        "reliability_score": float(best_model.reliability_score),
    },
)

# При fallback:
if fallback_model:
    log_decision(
        logger,
        decision="FALLBACK",
        reason="primary_model_failed",
        evaluated_conditions={
            "failed_model": best_model.name,
            "fallback_model": fallback_model.name,
            "error": error_message,
        },
    )
```

### 4.6 Изменения в data_api_client.py

```python
from app.utils.request_id import create_tracing_headers

# В каждом методе добавить headers:
async def get_all_models(...):
    headers = create_tracing_headers()
    async with httpx.AsyncClient(...) as client:
        response = await client.get(url, headers=headers)
```

---

## 5. План интеграции

| # | Шаг | Описание | Зависимости | Файлы |
|---|-----|----------|-------------|-------|
| 1 | Добавить structlog | requirements.txt всех сервисов | — | 4 файла |
| 2 | Создать logger.py | Конфигурация structlog | Шаг 1 | 4 файла |
| 3 | Создать request_id.py | ContextVars для API | Шаг 1 | 3 файла |
| 4 | Создать log_helpers.py | Хелперы для Business API | Шаг 2 | 1 файл |
| 5 | Мигрировать Business API main.py | Заменить logging, middleware | Шаги 2-4 | 1 файл |
| 6 | Мигрировать Data API main.py | Заменить logging, middleware | Шаги 2-3 | 1 файл |
| 7 | Мигрировать TG Bot main.py | Заменить logging, добавить correlation_id | Шаги 2-3 | 1 файл |
| 8 | Мигрировать Health Worker main.py | Заменить logging, добавить job_id | Шаг 2 | 1 файл |
| 9 | Добавить log_decision() в process_prompt.py | Логирование выбора модели | Шаг 4 | 1 файл |
| 10 | Добавить X-Correlation-ID в data_api_client.py | Трассировка между сервисами | Шаг 3 | 1 файл |
| 11 | Тесты | Проверить логирование | Шаги 5-10 | Существующие |

---

## 6. Влияние на существующие тесты

### 6.1 Необходимые изменения

| Тест | Изменение |
|------|-----------|
| `test_static_files.py` | Без изменений |
| `test_process_prompt_use_case.py` | Без изменений (логгер мокается) |
| Интеграционные тесты | Возможно потребуется mock structlog |

### 6.2 Новые тесты

| Тест | Описание |
|------|----------|
| `test_logger_config.py` | Проверка setup_logging() |
| `test_request_id.py` | Проверка ContextVars |
| `test_log_helpers.py` | Проверка log_decision() |

---

## 7. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Несовместимость grep-паттернов | Low | Medium | Тесты на парсинг логов |
| Увеличение latency | Low | Low | Benchmark до/после |
| Конфликт ContextVars в async | Low | High | Тесты с параллельными запросами |
| Ломается существующее логирование | Medium | Medium | Постепенная миграция, тесты |

---

## 8. Обратная совместимость

### 8.1 Сохраняемые поля

| Поле | Текущее | После миграции |
|------|---------|----------------|
| timestamp | `"2025-12-30 10:00:00"` | `"2025-12-30T10:00:00.000000"` (ISO) |
| level | `"INFO"` | `"info"` (lowercase) |
| service | `"free-ai-selector-business-api"` | Без изменений |
| message | Текст | `event` (в structlog) |

### 8.2 Новые поля

| Поле | Описание |
|------|----------|
| request_id | UUID запроса |
| correlation_id | UUID исходного запроса |
| duration_ms | Время выполнения |
| decision | Тип решения (ACCEPT/FALLBACK) |
| evaluated_conditions | Условия решения |

---

## 9. Качественные ворота

### PLAN_APPROVED Checklist

- [x] Интеграция: Точки интеграции определены
- [x] Изменения: Необходимые изменения описаны
- [x] Риски: Потенциальные риски учтены
- [x] Обратная совместимость: Проанализирована
- [x] **Утверждение: План утверждён пользователем**

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-12-30 | AI Architect | Первоначальная версия |
