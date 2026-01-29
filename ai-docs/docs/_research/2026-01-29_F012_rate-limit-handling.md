---
feature_id: "F012"
feature_name: "rate-limit-handling"
title: "Research Report: Rate Limit Handling для AI Провайдеров"
created: "2026-01-29"
author: "AI (Researcher)"
type: "_research"
status: "RESEARCH_DONE"
version: 1.0
mode: "FEATURE"
services: ["free-ai-selector-business-api", "free-ai-selector-data-postgres-api", "free-ai-selector-health-worker"]
files_analyzed: 16
---

# Research Report: Rate Limit Handling для AI Провайдеров (F012)

**Feature ID**: F012
**Дата**: 2026-01-29
**Автор**: AI Agent (Исследователь)
**Режим**: FEATURE
**Статус**: RESEARCH_DONE

---

## Executive Summary

Проведён анализ текущей логики выбора моделей, обработки ошибок и интеграции с AI-провайдерами.
Ключевые выводы:

- Нет классификации ошибок: все исключения приводят к `increment_failure`, что снижает reliability даже при 429.
- Fallback ограничен одной моделью (second best), полного перебора провайдеров нет.
- Data API не хранит `available_at`, есть только `is_active`, поэтому нет механизма cooldown.
- Health worker уже фильтрует провайдеров без API ключей через `env_var`; этот паттерн можно переиспользовать.
- Входной rate limit (SlowAPI) уже есть, но он относится к HTTP API, а не к провайдерам.

**Вывод**: для F012 требуются изменения в Business API (классификация, retry, full fallback) и в Data API (cooldown/availability), плюс синхронизация с health worker.

---

## 1. Анализ текущего кода

### 1.1 ProcessPromptUseCase (Business API)

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

Текущий поток:
1. Получение моделей: `get_all_models(active_only=True)`
2. Выбор лучшей по `effective_reliability_score`
3. Один вызов провайдера
4. Один fallback (second best)
5. Любая ошибка → `increment_failure`

```python
try:
    response_text = await provider.generate(...)
    success = True
except Exception as e:
    error_message = sanitize_error_message(e)
    fallback_model = self._select_fallback_model(models, best_model)
    ...

if success:
    await self.data_api_client.increment_success(...)
else:
    await self.data_api_client.increment_failure(...)
```

**Вывод**: отсутствует классификация ошибок и retry. Любой сбой (включая 429) снижает reliability.

---

### 1.2 Ошибки и провайдеры

**Файлы**:
- `services/free-ai-selector-business-api/app/infrastructure/ai_providers/groq.py`
- `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cloudflare.py`

Общий паттерн:
- `httpx.AsyncClient` + `response.raise_for_status()`
- Ошибка → `httpx.HTTPStatusError` (есть `response.status_code` и `response.text`)
- Ошибка логируется с `sanitize_error_message`, затем re-raise

```python
response = await client.post(...)
response.raise_for_status()
```

**Вывод**: источники для классификации 429 уже доступны в исключениях, но не используются.

---

### 1.3 Data API: модель и эндпоинты

**Файлы**:
- `services/free-ai-selector-data-postgres-api/app/infrastructure/database/models.py`
- `services/free-ai-selector-data-postgres-api/app/api/v1/models.py`

AIModelORM содержит:
- `is_active`, `api_format`, `env_var`
- статистику (`success_count`, `failure_count`, `request_count`)

**Нет** поля `available_at` или статуса cooldown.
Эндпоинты:
- `GET /api/v1/models?active_only=true`
- `POST /increment-success`, `POST /increment-failure`

**Вывод**: нет механизма исключения провайдера по времени, нужен новый атрибут и API.

---

### 1.4 Health Worker: фильтрация по env_var

**Файл**: `services/free-ai-selector-health-worker/app/main.py`

Health worker уже проверяет наличие ключа:

```python
api_key = _get_api_key(env_var)
if not api_key:
    return False, 0.0
```

**Вывод**: логика "Configured Providers Only" уже реализована для health checks, но не для `process_prompt`.

---

### 1.5 Входной rate limiting

**Файл**: `services/free-ai-selector-business-api/app/main.py`

Используется `slowapi` limiter для HTTP запросов:

```python
limiter = Limiter(key_func=get_remote_address)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Вывод**: это rate limit входящих запросов к API, не относится к лимитам провайдеров.

---

## 2. Точки расширения и зависимости

| Слой | Файл | Роль | Что менять для F012 |
|------|------|-----|---------------------|
| Data API ORM | `app/infrastructure/database/models.py` | AIModelORM | добавить `available_at: datetime?` |
| Data API Domain | `app/domain/models.py` | AIModel | поле `available_at` |
| Data API Schemas | `app/api/v1/schemas.py` | AIModelResponse | добавить `available_at` |
| Data API Routes | `app/api/v1/models.py` | GET /models | фильтр `available_only` или `exclude_unavailable` |
| Data API Repo | `app/infrastructure/repositories/ai_model_repository.py` | CRUD | метод обновления `available_at` |
| Alembic | `alembic/` | миграции | добавить колонку `available_at` |
| Business API Use Case | `app/application/use_cases/process_prompt.py` | Генерация | классификация ошибок, retry, full fallback |
| Business API Domain | `app/domain/exceptions.py` (новый) | Ошибки | `RateLimitError`, `ServerError`, `TimeoutError` |
| Business API Client | `app/infrastructure/http_clients/data_api_client.py` | Data API | endpoint для cooldown + фильтр available |
| Health Worker | `app/main.py` | health checks | учитывать `available_at` при запросе моделей |

---

## 3. Технические ограничения

1. **HTTP-only доступ к данным**: Business API не может писать в БД напрямую, всё через Data API.
2. **Async повсеместно**: retry должен использовать `await asyncio.sleep(...)` без блокировки event loop.
3. **Агрегированные метрики**: reliability зависит от `success_count/failure_count`. 429 нельзя учитывать как failure.
4. **Alembic миграции обязательны** при добавлении поля `available_at`.
5. **sanitize_error_message** обязателен для логирования ошибок (секреты не логируем).

---

## 4. Риски и несоответствия

1. **Несоответствие описания**: в `features_registry` указаны `exponential backoff` и `circuit breaker`, но в PRD описан фиксированный retry. Нужна явная договорённость о финальном scope.
2. **Retry-After формат**: заголовок может быть числом секунд или HTTP-date; нужно оба варианта.
3. **Статус 429 в теле**: часть провайдеров возвращают 500 с текстом "429" — классификация по тексту может быть хрупкой.
4. **Конкурентные запросы**: без централизованного cooldown запросы могут продолжать бить в лимит (нужен `available_at`).
5. **Расхождение по времени**: `available_at` должен храниться в UTC, иначе некорректные фильтры.

---

## 5. Рекомендации по реализации

1. **Классификатор ошибок** в Business API:
   - `httpx.HTTPStatusError.response.status_code`
   - поиск "429" в тексте ошибки
   - маппинг в доменные исключения

2. **Retry для 5xx/timeout**:
   - 10 попыток с фиксированной задержкой (ENV: `MAX_RETRIES`, `RETRY_DELAY_SECONDS`)
   - 429 не retry

3. **Cooldown в Data API**:
   - поле `available_at` + метод обновления
   - `GET /models` фильтрует `available_at <= now()`

4. **Configured Providers Only**:
   - фильтр моделей по `env_var` (аналог health worker)

5. **Full fallback**:
   - отсортировать модели по score и проходить по списку
   - при 429 сразу переходить к следующей

---

## 6. Quality Cascade Checklist (7/7)

### QC-1: DRY (Don't Repeat Yourself) ✅

**Код для переиспользования:**
- `DataAPIClient` (`app/infrastructure/http_clients/data_api_client.py`) — расширить методами availability
- `ProviderRegistry` (`app/infrastructure/ai_providers/registry.py`) — SSOT для провайдеров
- `sanitize_error_message` (`app/utils/security.py`) — безопасность логов
- Логика `env_var` из health worker — готовый паттерн "configured only"

**Рекомендация**: не создавать новые registry/clients, расширить существующие.

---

### QC-2: KISS (Keep It Simple, Stupid) ✅

**Упрощение дизайна:**
- Не вводить отдельный "circuit breaker" сервис — достаточно `available_at`.
- Retry реализовать внутри `ProcessPromptUseCase` без новых слоёв.
- Один источник cooldown в Data API вместо локального кеша.

---

### QC-3: YAGNI (You Aren't Gonna Need It) ✅

**Кандидаты на исключение из scope:**
- Полноценный circuit breaker, если не описан в FR (уточнить с владельцем).
- Экспоненциальный backoff, если PRD остаётся с fixed delay.

**Рекомендация**: начать с фиксированного retry и cooldown, усложнение — только по подтверждённой необходимости.

---

### QC-4: SoC (Separation of Concerns) ✅

**Разделение ответственности:**
- **API layer**: принимает запросы (`api/v1/prompts.py`)
- **Application**: классификация и retry (`process_prompt.py`)
- **Infrastructure**: провайдеры и HTTP (ai_providers, data_api_client)
- **Data API**: хранение доступности и статистики

**Интеграция**: классификация в Use Case, хранение cooldown в Data API.

---

### QC-5: SSoT (Single Source of Truth) ✅

**Источники данных:**
- Модели и `env_var` → Data API (SSOT)
- Маппинг провайдеров → `ProviderRegistry`
- Секреты → ENV
- Доступность (`available_at`) → Data API

**Рекомендация**: не дублировать фильтры по провайдерам в нескольких сервисах.

---

### QC-6: CoC (Convention over Configuration) ✅

**Конвенции проекта:**
- DDD/Hexagonal слои: `api/` → `application/` → `domain/` → `infrastructure/`
- Async + `httpx.AsyncClient` для всех внешних запросов
- Логирование через structlog-style + `sanitize_error_message`

**Рекомендация**: новые ошибки оформить как доменные исключения в `domain/`.

---

### QC-7: Security ✅

**Текущие практики:**
- Все API ключи только из env
- Логи чистятся через `sanitize_error_message`

**Риски и митигации:**
- Не логировать заголовки запросов провайдеров
- Не сохранять `Retry-After` вместе с конфиденциальными данными
- Ошибки классифицировать по статусу без печати тела ответа

---

## 7. Итог

Кодовая база хорошо подготовлена для F012: архитектура модульная, HTTP-only доступ соблюдён, а `env_var` уже доступен в данных. Основные изменения требуются в `ProcessPromptUseCase` и Data API для добавления cooldown (`available_at`) и корректной классификации ошибок.

Готов перейти к `/aidd-plan-feature` после подтверждения scope (fixed retry vs exponential/circuit breaker).
