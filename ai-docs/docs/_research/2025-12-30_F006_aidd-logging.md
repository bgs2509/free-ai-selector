---
feature_id: "F006"
feature_name: "aidd-logging"
title: "Research: Анализ текущего логирования vs AIDD Framework"
created: "2025-12-30"
author: "AI (Researcher)"
type: "_research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"
services: ["free-ai-selector-business-api", "free-ai-selector-data-postgres-api", "free-ai-selector-telegram-bot", "free-ai-selector-health-worker"]
---

# Research Report: F006 aidd-logging

## 1. Текущее состояние логирования

### 1.1 Общий обзор

| Метрика | Значение |
|---------|----------|
| Сервисов с логированием | 4 |
| Файлов с `import logging` | 53 |
| Файлов с logger calls | 29 |
| Всего logger вызовов | ~217 |
| Используемая библиотека | `logging` (stdlib) |
| Формат логов | JSON (ручная сборка строк) |

### 1.2 Анализ по сервисам

#### Business API (`free-ai-selector-business-api`)

**Конфигурация логирования** (`app/main.py:56-64`):
```python
logging.basicConfig(
    level=LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "'
    + SERVICE_NAME
    + '", "message": "%(message)s"}',
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

**request_id middleware** (`app/main.py:165-196`):
- ✅ Генерация/передача X-Request-ID
- ✅ Логирование request_started/request_completed
- ❌ Нет ContextVars (ID передаётся в `request.state`)
- ❌ Нет correlation_id
- ❌ Нет duration_ms

**Файлы с логированием:**
- `app/main.py` — 12 logger calls
- `app/application/use_cases/process_prompt.py` — 12 logger calls
- `app/application/use_cases/test_all_providers.py` — logger calls
- `app/infrastructure/http_clients/data_api_client.py` — 6 logger calls
- `app/infrastructure/ai_providers/*.py` — ~2 calls per file (16 providers)

**Критические точки для log_decision():**
- `process_prompt.py:109-112` — выбор лучшей модели
- `process_prompt.py:131-140` — fallback логика

---

#### Data API (`free-ai-selector-data-postgres-api`)

**Конфигурация** (`app/main.py:38-46`): Идентична Business API

**request_id middleware** (`app/main.py:106-137`):
- ✅ Генерация/передача X-Request-ID
- ✅ Логирование request_started/request_completed
- ❌ Нет ContextVars
- ❌ Нет correlation_id
- ❌ Нет duration_ms

**Файлы с логированием:**
- `app/main.py` — 10 logger calls
- `app/infrastructure/database/seed.py` — 3 logger calls

---

#### Telegram Bot (`free-ai-selector-telegram-bot`)

**Конфигурация** (`app/main.py:34-42`): Идентична Business API

**request_id / tracing:**
- ❌ Нет request_id middleware
- ❌ Нет correlation_id генерации
- ❌ Нет X-Correlation-ID при вызове Business API
- ❌ Нет user_id в ContextVars

**Файлы с логированием:**
- `app/main.py` — 18 logger calls

**Пример текущего логирования:**
```python
logger.info(f"User {message.from_user.id} started the bot")
logger.info(f"Processing prompt from user {user_id}: {user_prompt[:50]}...")
```

---

#### Health Worker (`free-ai-selector-health-worker`)

**Конфигурация** (`app/main.py:73-81`): Идентична Business API

**job_id / tracing:**
- ❌ Нет job_id для циклов проверок
- ❌ Нет request_id при вызовах Data API
- ❌ Нет duration_ms для health checks

**Файлы с логированием:**
- `app/main.py` — 55+ logger calls (по 2-4 на каждого из 16 провайдеров)

**Пример текущего логирования:**
```python
logger.info("Starting synthetic health checks...")
logger.info(f"Checking {model_name} ({provider})...")
logger.warning(f"Unknown provider: {provider}, skipping health check")
```

---

## 2. Сравнение с требованиями AIDD Framework

### 2.1 Матрица соответствия

| Аспект | AIDD Framework | Текущее состояние | Gap |
|--------|---------------|-------------------|-----|
| **Библиотека** | `structlog` | `logging` | ❌ Critical |
| **JSON формат** | Через processors | Ручная сборка строк | ⚠️ Medium |
| **request_id** | ContextVars + middleware | `request.state` (только API) | ⚠️ Medium |
| **correlation_id** | X-Correlation-ID между сервисами | Отсутствует | ❌ Critical |
| **causation_id** | ID события-причины | Отсутствует | — Deferred |
| **user_id** | В ContextVars | Не в контексте | ⚠️ Medium |
| **log_decision()** | Хелпер с evaluated_conditions | Отсутствует | ❌ Critical |
| **duration_ms** | Для всех операций | Отсутствует | ❌ Critical |
| **error_code** | Стандартные коды | Отсутствует | ⚠️ Medium |
| **sanitize_sensitive_data** | В structlog processors | `sanitize_error_message()` | ✅ Partial |
| **LOG_FORMAT** | json/console переключение | Только JSON | ⚠️ Medium |

### 2.2 Детальный анализ gaps

#### GAP-001: Библиотека `logging` вместо `structlog`

**Текущее:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f'{{"request_id": "{request_id}", "event": "request_started"}}')
```

**Требуется:**
```python
import structlog
logger = structlog.get_logger()
logger.info("request_started", request_id=request_id)
```

**Проблемы:**
- Ручное формирование JSON-строк (хрупко, подвержено ошибкам)
- Нет processors для автоматической обработки
- Нет цепочки обогащения логов

---

#### GAP-002: Отсутствие correlation_id

**Текущее:**
- Business API и Data API имеют request_id middleware
- TG Bot вызывает Business API без передачи ID
- Health Worker вызывает Data API без передачи ID

**Проблема:**
Невозможно трассировать запрос через цепочку:
```
TG Bot → Business API → Data API
```

---

#### GAP-003: Отсутствие log_decision()

**Текущее** (`process_prompt.py:108-112`):
```python
best_model = self._select_best_model(models)
logger.info(
    f"Selected model: {best_model.name} (reliability: {best_model.reliability_score:.3f})"
)
```

**Требуется:**
```python
log_decision(
    decision="SELECT_MODEL",
    action="selected",
    reason="highest_reliability_score",
    evaluated_conditions={
        "models_count": len(models),
        "selected_model": best_model.name,
        "reliability_score": float(best_model.reliability_score),
        "alternatives": [m.name for m in models[:3]],
    }
)
```

**Проблема:**
AI-агент не понимает ПОЧЕМУ выбрана конкретная модель, какие альтернативы рассматривались.

---

#### GAP-004: Отсутствие duration_ms

**Текущее:**
- `response_time` вычисляется для AI-запросов, но не логируется
- Нет duration_ms для HTTP-запросов к Data API
- Нет duration_ms в request_completed

---

#### GAP-005: TG Bot без tracing

**Текущее:**
```python
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(
        f"{BUSINESS_API_URL}/api/v1/prompts/process",
        json={"prompt": prompt},
    )
```

**Требуется:**
```python
correlation_id = str(uuid.uuid4())
structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(
        f"{BUSINESS_API_URL}/api/v1/prompts/process",
        json={"prompt": prompt},
        headers={"X-Correlation-ID": correlation_id},
    )
```

---

## 3. Существующие паттерны (для сохранения)

### 3.1 sanitize_error_message()

Функция существует во всех 4 сервисах в `app/utils/security.py`:

```python
def sanitize_error_message(error: Union[Exception, str]) -> str:
    """Sanitize error message to prevent API key leakage."""
```

**Использование:** ~50+ мест в коде

**Рекомендация:** Сохранить и интегрировать в structlog processor `sanitize_sensitive_data`.

### 3.2 JSON формат логов

Все сервисы используют единый формат:
```json
{"timestamp": "2025-12-30 10:00:00", "level": "INFO", "service": "...", "message": "..."}
```

**Рекомендация:** Сохранить обратную совместимость для grep-паттернов.

### 3.3 request_id middleware

Business API и Data API имеют рабочий middleware для request_id.

**Рекомендация:** Мигрировать на ContextVars, добавить correlation_id.

---

## 4. Файлы для модификации

### 4.1 Создаваемые файлы (в каждом сервисе)

| Сервис | Новые файлы |
|--------|-------------|
| Business API | `app/utils/logger.py`, `app/utils/log_helpers.py` |
| Data API | `app/utils/logger.py` |
| TG Bot | `app/utils/logger.py` |
| Health Worker | `app/utils/logger.py` |

### 4.2 Модифицируемые файлы

| Файл | Изменения |
|------|-----------|
| `services/free-ai-selector-business-api/app/main.py` | structlog config, ContextVars middleware, correlation_id |
| `services/free-ai-selector-data-postgres-api/app/main.py` | structlog config, ContextVars middleware |
| `services/free-ai-selector-telegram-bot/app/main.py` | structlog config, correlation_id генерация |
| `services/free-ai-selector-health-worker/app/main.py` | structlog config, job_id |
| `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py` | log_decision() для выбора модели |
| `services/free-ai-selector-business-api/app/infrastructure/http_clients/data_api_client.py` | X-Correlation-ID header |
| `services/*/requirements.txt` | +structlog>=24.0.0 |

### 4.3 Статистика изменений

| Метрика | Значение |
|---------|----------|
| Новых файлов | 5 |
| Модифицируемых файлов | ~15-20 |
| Точек вызова logger | ~217 (большинство не требуют изменений) |
| Критических точек для log_decision() | 3-5 |

---

## 5. Выявленные паттерны архитектуры

### 5.1 Слоистая структура (DDD/Hexagonal)

```
app/
├── api/v1/           ← HTTP handlers (логируют request/response)
├── application/      ← Use cases (логируют бизнес-решения)
├── domain/           ← Модели (минимальное логирование)
└── infrastructure/   ← Провайдеры, клиенты (логируют I/O)
```

### 5.2 HTTP-only pattern

```
TG Bot → Business API → Data API → PostgreSQL
         ↓
   AI Providers (16 шт.)
```

Все сервисы общаются через HTTP — correlation_id должен передаваться через заголовки.

### 5.3 Асинхронность

Все сервисы используют `async/await` — ContextVars корректно работают с asyncio.

---

## 6. Риски и ограничения

### 6.1 Риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Несовместимость grep-паттернов | Low | Medium | Тесты на парсинг логов |
| Увеличение latency | Low | Low | Benchmark до/после |
| Конфликт ContextVars в async | Low | High | Тесты с параллельными запросами |

### 6.2 Ограничения

- Не использовать centralized logging (ELK) — выходит за scope MVP Level 2
- Не добавлять causation_id в этой итерации
- Не менять уровни логирования (INFO по умолчанию)

---

## 7. Рекомендации

### 7.1 Приоритет реализации

1. **P0 (Critical):** structlog config, ContextVars, correlation_id
2. **P1 (High):** log_decision(), duration_ms
3. **P2 (Medium):** error_code, TG Bot tracing, Health Worker job_id
4. **P3 (Low):** user_id автоматически, path_params

### 7.2 Подход к миграции

1. Создать `app/utils/logger.py` с конфигурацией structlog
2. Заменить `logging.basicConfig()` на `structlog.configure()`
3. Заменить `logging.getLogger()` на `structlog.get_logger()`
4. Существующие `logger.info()` вызовы работают без изменений
5. Добавить ContextVars middleware
6. Добавить `log_decision()` в критических точках

### 7.3 Обратная совместимость

- Сохранить поля: `timestamp`, `level`, `service`, `message`
- Добавить новые поля: `request_id`, `correlation_id`, `duration_ms`, `error_code`
- `message` теперь будет содержать только текст события

---

## 8. Качественные ворота

### RESEARCH_DONE Checklist

- [x] Анализ существующего кода выполнен
- [x] Архитектурные паттерны выявлены
- [x] Gaps идентифицированы и документированы
- [x] Файлы для модификации определены
- [x] Риски оценены
- [x] Рекомендации сформулированы

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-12-30 | AI Researcher | Первоначальная версия |
