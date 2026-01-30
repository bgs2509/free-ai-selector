# План фичи: F012 Rate Limit Handling для AI Провайдеров

**Feature ID**: F012
**Дата создания**: 2026-01-29
**Автор**: AI (Architect)
**Статус**: DRAFT
**PRD**: `_analysis/2026-01-29_F012_rate-limit-handling.md`
**Research**: `_research/2026-01-29_F012_rate-limit-handling.md`

---

## 1. Обзор

### 1.1 Краткое описание

Реализация комплексной системы обработки rate limit (HTTP 429) для AI провайдеров:
- **Error Classification** — распознавание типов ошибок (429, 5xx, auth, validation)
- **Retry Mechanism** — 10 попыток с фиксированной задержкой 10s для 5xx/timeout
- **Availability Cooldown** — временное исключение провайдера через `available_at` в Data API
- **Full Fallback** — перебор всех доступных моделей по убыванию score
- **Graceful Degradation** — 429 не снижает reliability_score

### 1.2 Связь с существующим функционалом

| Зависимость | Статус | Влияние |
|-------------|--------|---------|
| F008 (Provider Registry SSOT) | DEPLOYED | Используем `ProviderRegistry` и `env_var` из БД |
| F010 (Rolling Window Reliability) | DEPLOYED | Используем `effective_reliability_score` для выбора |
| F011-B (System Prompts) | IMPLEMENT_OK | Совместимость с новыми параметрами |

### 1.3 Бизнес-ценность

| Метрика | До | После |
|---------|-----|-------|
| Время простоя при rate limit | 5+ часов | 0 (автоматическое восстановление) |
| Reliability score при 429 | Падает | Не падает |
| Fallback механизм | Только 1 модель | Все доступные модели |

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Роль | Изменения |
|--------|------|-----------|
| `free-ai-selector-data-postgres-api` | Хранение `available_at`, фильтрация | ORM, миграция, endpoint, repository |
| `free-ai-selector-business-api` | Классификация ошибок, retry, fallback | exceptions, use case, client |
| `free-ai-selector-health-worker` | Использует `available_only` | Минорные изменения |

### 2.2 Точки интеграции

```
┌─────────────────────┐
│  ProcessPromptUseCase│
│  (process_prompt.py)│
└──────────┬──────────┘
           │ 1. classify_error()
           │ 2. retry for 5xx/timeout
           │ 3. set_availability() for 429
           │ 4. full fallback loop
           ▼
┌─────────────────────┐     HTTP      ┌─────────────────────┐
│   DataAPIClient     │──────────────▶│   Data API          │
│(data_api_client.py) │               │                     │
│                     │               │ GET /models         │
│ • get_all_models()  │◀──────────────│   ?available_only   │
│   available_only    │               │                     │
│                     │               │ PATCH /models/{id}/ │
│ • set_availability()│──────────────▶│   availability      │
└─────────────────────┘               └─────────────────────┘
```

### 2.3 Существующие зависимости

**Business API:**
- `httpx.AsyncClient` — HTTP клиент (используется в провайдерах)
- `httpx.HTTPStatusError` — источник для классификации ошибок
- `sanitize_error_message()` — безопасное логирование
- `ProviderRegistry` — получение провайдеров (F008)

**Data API:**
- `SQLAlchemy 2.0` — ORM
- `Alembic` — миграции
- `AIModelORM` — модель с полями `is_active`, `env_var`

---

## 3. План изменений

### 3.1 Новые компоненты

| Компонент | Расположение | Описание |
|-----------|--------------|----------|
| `exceptions.py` | `business-api/app/domain/exceptions.py` | Иерархия исключений: `RateLimitError`, `ServerError`, `TimeoutError`, `AuthenticationError`, `ValidationError` |
| `error_classifier.py` | `business-api/app/application/services/error_classifier.py` | Функция `classify_error(exception) -> ProviderError` |
| `retry_service.py` | `business-api/app/application/services/retry_service.py` | Retry логика с configurable параметрами |

### 3.2 Модификации существующего кода

#### Data API

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/infrastructure/database/models.py` | Добавить `available_at: datetime?` в `AIModelORM` | FR-4: Хранение cooldown |
| `app/domain/models.py` | Добавить `available_at: datetime?` в `AIModel` | Доменная модель |
| `app/api/v1/schemas.py` | Добавить `available_at: datetime?` в `AIModelResponse` | API контракт |
| `app/api/v1/models.py` | Добавить `PATCH /{id}/availability`, параметр `available_only` в `GET /` | FR-4: Endpoint и фильтр |
| `app/infrastructure/repositories/ai_model_repository.py` | Добавить `set_availability()`, обновить `get_all()` | Repository pattern |
| `alembic/versions/*_add_available_at.py` | Миграция `ALTER TABLE ai_models ADD available_at` | БД изменение |

#### Business API

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/domain/models.py` | Добавить `available_at: datetime?` в `AIModelInfo` | DTO |
| `app/domain/exceptions.py` | **Создать** иерархию исключений | FR-1: Error Classification |
| `app/application/services/error_classifier.py` | **Создать** classify_error() | FR-1 |
| `app/application/services/retry_service.py` | **Создать** retry логику | FR-2 |
| `app/application/use_cases/process_prompt.py` | Интегрировать retry, classification, full fallback | FR-1,2,5,9 |
| `app/infrastructure/http_clients/data_api_client.py` | Добавить `set_availability()`, параметр `available_only` | FR-4 |
| `app/config.py` или env | Добавить `MAX_RETRIES`, `RETRY_DELAY_SECONDS`, `RATE_LIMIT_DEFAULT_COOLDOWN` | FR-6 |

#### Health Worker

| Файл | Изменение | Причина |
|------|-----------|---------|
| `app/main.py` | Использовать `available_only=True` при получении моделей | Исключить rate-limited |

### 3.3 Новые зависимости

| Зависимость | Версия | Назначение |
|-------------|--------|------------|
| — | — | Новых внешних зависимостей не требуется |

---

## 4. API контракты

### 4.1 Data API: Новый endpoint

```http
PATCH /api/v1/models/{model_id}/availability?retry_after_seconds=60

Response: 200 OK
{
  "id": 1,
  "name": "Cloudflare",
  "available_at": "2026-01-29T13:00:00Z",
  ...
}
```

### 4.2 Data API: Обновление GET /models

```http
GET /api/v1/models?active_only=true&available_only=true&include_recent=true

# available_only=true исключает модели с available_at > now()
```

### 4.3 Обратная совместимость

- `available_only` по умолчанию `false` — существующие клиенты не затронуты
- `available_at` nullable — существующие записи работают без изменений
- Новые поля в response добавляются (не удаляются существующие)

---

## 5. Влияние на существующие тесты

### 5.1 Business API тесты

| Тест | Влияние | Действие |
|------|---------|----------|
| `test_process_prompt_use_case.py` | Высокое | Обновить для новой логики fallback |
| `test_data_api_client.py` | Среднее | Добавить тесты для `set_availability()` |

### 5.2 Data API тесты

| Тест | Влияние | Действие |
|------|---------|----------|
| `test_models_endpoints.py` | Среднее | Добавить тесты для нового endpoint |
| `test_ai_model_repository.py` | Среднее | Добавить тесты для `set_availability()` |

### 5.3 Новые тесты

| Тест | Покрытие |
|------|----------|
| `test_error_classification.py` | FR-1: Все типы ошибок |
| `test_retry_mechanism.py` | FR-2: Retry для 5xx/timeout |
| `test_availability_cooldown.py` | FR-4: available_at обновление и фильтрация |
| `test_full_fallback.py` | FR-9: Перебор всех моделей |
| `test_graceful_degradation.py` | FR-5: 429 не записывается как failure |

---

## 6. План интеграции

| # | Шаг | Зависимости | Файлы |
|---|-----|-------------|-------|
| 1 | Добавить `available_at` в Data API ORM и миграция | — | `models.py`, `alembic/` |
| 2 | Обновить Data API domain model и schema | Шаг 1 | `domain/models.py`, `schemas.py` |
| 3 | Добавить repository метод `set_availability()` | Шаг 1 | `ai_model_repository.py` |
| 4 | Обновить `get_all()` с фильтром `available_only` | Шаг 1 | `ai_model_repository.py` |
| 5 | Добавить endpoint `PATCH /availability` | Шаг 3 | `api/v1/models.py` |
| 6 | Обновить `GET /models` с параметром `available_only` | Шаг 4 | `api/v1/models.py` |
| 7 | **Data API тесты** | Шаги 1-6 | `tests/` |
| 8 | Создать `exceptions.py` в Business API | — | `domain/exceptions.py` |
| 9 | Создать `error_classifier.py` | Шаг 8 | `services/error_classifier.py` |
| 10 | Создать `retry_service.py` | Шаг 8 | `services/retry_service.py` |
| 11 | Обновить `AIModelInfo` с `available_at` | — | `domain/models.py` |
| 12 | Обновить `DataAPIClient` | Шаги 5-6 | `data_api_client.py` |
| 13 | Обновить `ProcessPromptUseCase` | Шаги 9-12 | `process_prompt.py` |
| 14 | Добавить env vars | — | `docker-compose.yml` |
| 15 | **Business API тесты** | Шаги 8-14 | `tests/` |
| 16 | Обновить Health Worker | Шаг 6 | `health-worker/app/main.py` |
| 17 | **Integration тесты** | Все | End-to-end |

---

## 7. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| БД миграция ломает Data API | Очень низкая | Высокое | Простая `ALTER TABLE ADD COLUMN`, nullable, можно откатить |
| Retry увеличивает latency | Средняя | Среднее | Retry только для 5xx/timeout, не для 429; configurable через env |
| `available_at` не сбрасывается | Низкая | Среднее | Автоматический сброс при `available_at <= now()` в `get_all()` |
| Все провайдеры rate limited | Очень низкая | Высокое | 14 провайдеров — маловероятно одновременно |
| Breaking changes в fallback | Низкая | Среднее | Сохраняем обратную совместимость, расширяем поведение |

---

## 8. Breaking Changes

### Нет breaking changes

Все изменения **обратно совместимы**:

1. **Data API**:
   - Новое поле `available_at` nullable — существующие записи работают
   - Новый параметр `available_only` по умолчанию `false`
   - Новый endpoint не влияет на существующие

2. **Business API**:
   - Новые исключения в `domain/exceptions.py` — не влияют на существующий код
   - Расширение fallback логики — улучшает поведение, не ломает

3. **API контракты**:
   - Новые поля в response (additive change)
   - Новые query параметры с default values

---

## 9. Миграции БД

### 9.1 Alembic миграция

**Файл**: `alembic/versions/xxxx_add_available_at_to_ai_models.py`

```python
"""Add available_at column to ai_models table

Revision ID: xxxx
Revises: <previous>
Create Date: 2026-01-29
"""

from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column(
        'ai_models',
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=True)
    )

def downgrade() -> None:
    op.drop_column('ai_models', 'available_at')
```

### 9.2 Влияние

- **Время миграции**: мгновенно (добавление nullable колонки)
- **Downtime**: нет
- **Откат**: простой `DROP COLUMN`

---

## 10. Environment Variables

| Переменная | Default | Описание |
|------------|---------|----------|
| `MAX_RETRIES` | `10` | Количество retry попыток для 5xx/timeout |
| `RETRY_DELAY_SECONDS` | `10` | Задержка между retry (секунды) |
| `RATE_LIMIT_DEFAULT_COOLDOWN` | `3600` | Дефолтный cooldown при 429 без Retry-After (секунды) |

---

## 11. Детали реализации ключевых компонентов

### 11.1 Error Classification (`error_classifier.py`)

```python
from httpx import HTTPStatusError, TimeoutException
from app.domain.exceptions import (
    RateLimitError, ServerError, TimeoutError,
    AuthenticationError, ValidationError
)

def classify_error(exception: Exception) -> Exception:
    """
    Классифицировать исключение провайдера.

    FR-1.1-1.6: Различные типы ошибок обрабатываются по-разному.
    """
    if isinstance(exception, TimeoutException):
        return TimeoutError(str(exception))

    if isinstance(exception, HTTPStatusError):
        status = exception.response.status_code
        detail = exception.response.text

        # FR-1.6: 500 с текстом "429" = RateLimitError
        if status == 429 or (status == 500 and "429" in detail):
            retry_after = _parse_retry_after(exception.response.headers)
            return RateLimitError(
                message=str(exception),
                retry_after_seconds=retry_after
            )

        if status >= 500:
            return ServerError(str(exception))

        if status in (401, 403):
            return AuthenticationError(str(exception))

        if status in (400, 422):
            return ValidationError(str(exception))

    return exception
```

### 11.2 ProcessPromptUseCase (обновлённая логика)

```python
async def execute(self, request: PromptRequest) -> PromptResponse:
    # 1. Получить доступные модели (FR-4, FR-8)
    models = await self.data_api_client.get_all_models(
        active_only=True,
        available_only=True,  # Исключить rate-limited
        configured_only=True  # Исключить без API ключей
    )

    # 2. Отсортировать по effective_reliability_score
    sorted_models = sorted(models, key=lambda m: m.effective_reliability_score, reverse=True)

    # 3. Full fallback loop (FR-9)
    for model in sorted_models:
        try:
            provider = self._get_provider_for_model(model)

            # Retry для 5xx/timeout (FR-2)
            response_text = await self._generate_with_retry(provider, request)

            # Успех
            await self.data_api_client.increment_success(model.id, response_time)
            return PromptResponse(...)

        except RateLimitError as e:
            # FR-5: Не записываем как failure
            logger.warning("rate_limit_detected", model=model.name, retry_after=e.retry_after_seconds)
            await self.data_api_client.set_availability(model.id, e.retry_after_seconds)
            continue  # Следующая модель

        except (ServerError, TimeoutError) as e:
            # Записываем как failure после исчерпания retry
            await self.data_api_client.increment_failure(model.id, response_time)
            continue  # Следующая модель

    # Все модели не сработали
    raise Exception("All AI providers failed")
```

---

## 12. Acceptance Criteria (из PRD)

- [ ] FR-1: Error Classification работает для всех типов ошибок
- [ ] FR-2: Retry 10×10s для 5xx/timeout
- [ ] FR-3: Retry-After parsing или дефолтный cooldown
- [ ] FR-4: `available_at` обновляется при 429
- [ ] FR-5: 429 НЕ записывается как failure
- [ ] FR-6: Env vars для retry/cooldown
- [ ] FR-8: Модели без API ключей исключены
- [ ] FR-9: Full fallback по всем доступным моделям
- [ ] NFR-1: Overhead на успешный запрос <10ms
- [ ] NFR-2: Все 70+ существующих тестов проходят
- [ ] NFR-3: Логи rate_limit_detected, availability_updated
- [ ] NFR-4: Coverage ≥75% для нового кода

---

## 13. Оценка объёма работ

| Компонент | Файлов | Строк кода (прим.) |
|-----------|--------|-------------------|
| Data API: ORM + миграция | 2 | ~30 |
| Data API: Domain + Schema | 2 | ~20 |
| Data API: Repository | 1 | ~40 |
| Data API: Endpoint | 1 | ~50 |
| Data API: Тесты | 2 | ~100 |
| Business API: Exceptions | 1 | ~50 |
| Business API: Error Classifier | 1 | ~60 |
| Business API: Retry Service | 1 | ~40 |
| Business API: Process Prompt | 1 | ~100 (модификация) |
| Business API: Data Client | 1 | ~40 (модификация) |
| Business API: Тесты | 5 | ~300 |
| Health Worker | 1 | ~10 |
| **Итого** | **19** | **~840** |

---

## 14. Quality Cascade Checklist (16/16)

> **Принцип**: Архитектурные ошибки — самые дорогие. Проверяем качество ДО реализации.

### QC-1: DRY (Don't Repeat Yourself) ✅

- [x] План сверен с Research Report (секция "Код для переиспользования")
- [x] `DataAPIClient` расширяется, не дублируется
- [x] `ProviderRegistry` (F008) переиспользуется
- [x] `sanitize_error_message` переиспользуется
- [x] Логика `env_var` из health worker переиспользуется

→ **Обоснование**: Все новые компоненты расширяют существующие, не создают дублей.

---

### QC-2: KISS (Keep It Simple, Stupid) ✅

- [x] Количество новых файлов минимизировано (3 новых файла в Business API)
- [x] Нет отдельного "circuit breaker" сервиса — достаточно `available_at`
- [x] Retry реализуется внутри `ProcessPromptUseCase` без новых слоёв
- [x] Один источник cooldown (Data API) вместо локального кеша

→ **Обоснование**: Fixed retry (10×10s) проще exponential backoff, достаточен для MVP.

---

### QC-3: YAGNI (You Aren't Gonna Need It) ✅

- [x] Каждый компонент привязан к FR из PRD:
  - `exceptions.py` → FR-1
  - `error_classifier.py` → FR-1
  - `retry_service.py` → FR-2
  - `available_at` → FR-4
- [x] Exponential backoff исключён (не в PRD)
- [x] Circuit breaker исключён (не в PRD)

→ **Трассировка**: См. секцию 12 "Acceptance Criteria".

---

### QC-4: SRP (Single Responsibility Principle) ✅

| Модуль | Единственная ответственность |
|--------|------------------------------|
| `exceptions.py` | Определение типов ошибок провайдеров |
| `error_classifier.py` | Классификация исключений по типу |
| `retry_service.py` | Логика повторных попыток |
| `ProcessPromptUseCase` | Оркестрация выбора модели и fallback |
| `DataAPIClient` | HTTP-коммуникация с Data API |
| Data API endpoint | CRUD для availability |

→ **Обоснование**: Каждый модуль делает одну вещь.

---

### QC-5: OCP (Open/Closed Principle) ✅

- [x] Новые типы ошибок добавляются без модификации `error_classifier.py`
- [x] `exceptions.py` использует иерархию наследования для расширяемости
- [x] Retry стратегия конфигурируется через env vars

→ **Точки расширения**: Добавление новых исключений в иерархию `ProviderError`.

---

### QC-6: ISP (Interface Segregation Principle) ✅

- [x] `DataAPIClient` получает только 2 новых метода:
  - `set_availability(model_id, seconds)`
  - параметр `available_only` в `get_all_models()`
- [x] Новый endpoint `PATCH /availability` минимален (1 параметр)
- [x] Интерфейсы не раздуваются

→ **Обоснование**: Клиенты зависят только от используемых методов.

---

### QC-7: DIP (Dependency Inversion Principle) ✅

- [x] `ProcessPromptUseCase` зависит от абстракции `DataAPIClient`, не от реализации
- [x] Провайдеры получаются через `ProviderRegistry` (F008)
- [x] Конкретные реализации (Groq, Cloudflare) заменяемы

→ **Граф зависимостей**: UseCase → Client → HTTP → Data API (направление к абстракциям).

---

### QC-8: SoC (Separation of Concerns) ✅

- [x] **API layer** (`api/v1/`) — HTTP endpoints
- [x] **Application** (`application/`) — классификация, retry, use case
- [x] **Domain** (`domain/`) — исключения, модели
- [x] **Infrastructure** (`infrastructure/`) — провайдеры, HTTP клиенты

→ **Слои**: DDD/Hexagonal соблюдён, бизнес-логика в application, не в infrastructure.

---

### QC-9: SSoT (Single Source of Truth) ✅

- [x] `available_at` хранится ТОЛЬКО в Data API (PostgreSQL)
- [x] Конфигурация retry в ENV vars (единый источник)
- [x] Типы ошибок в `domain/exceptions.py` (единственное место)
- [x] Модели в `ProviderRegistry` (F008 SSOT)

→ **Источники данных**: Data API = SSOT для availability, ENV = SSOT для config.

---

### QC-10: LoD (Law of Demeter) ✅

- [x] `ProcessPromptUseCase` взаимодействует только с `DataAPIClient` и `ProviderRegistry`
- [x] Нет цепочек вызовов `a.b.c.d`
- [x] Модули не знают внутренности других модулей

→ **Связанность**: UseCase ↔ Client ↔ Data API (минимальная цепочка).

---

### QC-11: CoC (Convention over Configuration) ✅

- [x] Именование следует паттернам проекта (`*_use_case.py`, `*_client.py`)
- [x] Структура `domain/exceptions.py` соответствует существующей
- [x] Async + `httpx.AsyncClient` — конвенция проекта
- [x] Логирование через structlog + `sanitize_error_message`

→ **Конвенции из Research**: Все 6 конвенций (секция QC-6) соблюдены.

---

### QC-12: Fail Fast ✅

- [x] Валидация входных данных на границе (API endpoint)
- [x] Ошибки классифицируются сразу при получении
- [x] 429 → немедленный переход к fallback (не retry)
- [x] Исчерпание retry → немедленный fallback

→ **Стратегия**: Классифицировать рано, падать явно, переходить к fallback быстро.

---

### QC-13: Explicit > Implicit ✅

- [x] API контракты явно описаны (секция 4)
- [x] Зависимости явно указаны (секция 2.3)
- [x] Retry параметры явные (ENV vars)
- [x] Нет магического поведения

→ **Сигнатуры**: `classify_error(exception) -> ProviderError`, `set_availability(model_id, seconds)`.

---

### QC-14: Composition > Inheritance ✅

- [x] Иерархия исключений ≤ 2 уровня: `Exception → ProviderError → RateLimitError`
- [x] `ProcessPromptUseCase` использует композицию (inject `DataAPIClient`)
- [x] Нет множественного наследования

→ **Паттерн**: Dependency Injection для переиспользования.

---

### QC-15: Testability ✅

- [x] `error_classifier` — чистая функция, легко тестировать
- [x] `retry_service` — зависимости инжектируются
- [x] `DataAPIClient` можно замокать в тестах UseCase
- [x] Нет скрытых зависимостей от глобального состояния

→ **Стратегия тестирования**: Unit tests для classifier/retry, Integration для UseCase.

---

### QC-16: Security ✅

- [x] API ключи только из ENV (не хардкодятся)
- [x] Логи через `sanitize_error_message` (секреты не логируются)
- [x] Заголовки провайдеров не логируются
- [x] `Retry-After` не сохраняется с конфиденциальными данными
- [x] Ошибки классифицируются по статусу, тело ответа не печатается

→ **Security-меры из Research**: Все 3 риска митигированы (секция QC-7).

---

**Итого**: 16/16 проверок пройдено ✅

---

## 15. Следующий шаг

После утверждения плана:

```bash
/aidd-code
```

---

**Статус**: APPROVED (2026-01-29)
