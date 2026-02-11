---
feature_id: "F018"
feature_name: "remove-env-var-from-db"
title: "Удаление env_var из БД, SSOT через ProviderRegistry"
created: "2026-02-11"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 1
mode: "FEATURE"

related_features: [F008, F013]
services: [free-ai-selector-data-postgres-api, free-ai-selector-business-api, free-ai-selector-health-worker]
requirements_count: 9

pipelines:
  business: true
  data: true
  integration: true
  modified: [data-api, business-api, health-worker]
---

# PRD: Удаление env_var из БД, SSOT через ProviderRegistry

**Feature ID**: F018
**Версия**: 1.0
**Дата**: 2026-02-11
**Автор**: AI Agent (Аналитик)
**Статус**: Approved

---

## 1. Обзор

### 1.1 Проблема

На VPS (test_rus) Business API возвращает 500 на ВСЕ запросы:

```
"Failed to process prompt: No configured AI models available (missing API keys)"
```

**Корневая причина**: поле `env_var` пустое у ВСЕХ 16 моделей в БД на VPS. Модели были засеяны ДО добавления колонки `env_var` (миграция `0002_add_api_format_env_var`), а `seed_database()` пропускает существующие записи (`continue` на строке 173).

**Архитектурная проблема (SSOT violation)**: `env_var` дублируется в 2 местах:
1. **БД**: `seed.py` → ORM → Data API response → потребители (Business API, Health Worker)
2. **Классы провайдеров**: `API_KEY_ENV = "GROQ_API_KEY"` (class variable в каждом провайдере)

**Побочный баг**: В `seed.py` Cloudflare указан как `"CLOUDFLARE_API_KEY"`, но реальная env переменная в `CloudflareProvider` — `"CLOUDFLARE_API_TOKEN"`. Это приводит к тому, что Cloudflare health check всегда завершается с `provider_api_key_missing`.

### 1.2 Решение

Удалить `env_var` из БД полностью. Сделать `ProviderRegistry` (Business API) единственным источником правды для имён env переменных API ключей.

Ключевые компоненты:
- **Data API**: DROP COLUMN `env_var`, удалить из ORM/domain/schema/seed
- **Business API**: `ProviderRegistry.get_api_key_env(name)` — classmethod для получения имени env переменной без инстанцирования провайдера
- **Health Worker**: локальный `PROVIDER_ENV_VARS` dict (отдельный микросервис, не может импортировать из Business API)
- **Seed скрипт**: upsert существующих моделей + cleanup orphan моделей

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Разработчики | Команда разработки | SSOT для env_var, предсказуемый деплой |
| DevOps | Операторы VPS | Рабочий сервис без ручных SQL-фиксов |
| Пользователи | Конечные пользователи через Telegram/Web | Работающий AI selector (200 вместо 500) |

### 1.4 Ценностное предложение

- Устранение production-критического бага (500 на все запросы)
- Устранение нарушения SSOT (env_var в 2 местах)
- Устранение побочного бага Cloudflare (`API_KEY` vs `API_TOKEN`)
- Seed скрипт с upsert предотвратит подобные баги в будущем

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | DROP COLUMN env_var | Удалить колонку `env_var` из таблицы `ai_models` через Alembic миграцию | Миграция `0004_drop_env_var.py` выполняется без ошибок; `SELECT env_var FROM ai_models` возвращает ошибку |
| FR-002 | Удалить env_var из Data API | Удалить `env_var` из ORM, domain model, Pydantic schema, API response | GET `/api/v1/models` не содержит поле `env_var` в ответе |
| FR-003 | ProviderRegistry.get_api_key_env() | Добавить classmethod для получения имени env переменной по имени провайдера без создания экземпляра | `ProviderRegistry.get_api_key_env("Groq")` возвращает `"GROQ_API_KEY"` |
| FR-004 | Cloudflare API_KEY_ENV | Добавить `API_KEY_ENV = "CLOUDFLARE_API_TOKEN"` в CloudflareProvider | `ProviderRegistry.get_api_key_env("Cloudflare")` возвращает `"CLOUDFLARE_API_TOKEN"` |
| FR-005 | Business API: registry-based filtering | `_filter_configured_models()` использует `ProviderRegistry.get_api_key_env()` вместо `model.env_var` | POST `/api/v1/prompts/process` возвращает 200 (вместо 500) |
| FR-006 | Health Worker: PROVIDER_ENV_VARS | Локальный dict маппинга provider → env_var в Health Worker | Health Worker логирует `configured_providers` корректно |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-010 | Seed upsert | `seed_database()` обновляет `api_format`, `api_endpoint`, `is_active` для существующих моделей | При повторном запуске seed — модели обновляются, а не пропускаются |
| FR-011 | Seed orphan cleanup | `seed_database()` удаляет модели, отсутствующие в SEED_MODELS (GoogleGemini, Cohere) | После seed в БД нет моделей GoogleGemini и Cohere |
| FR-012 | Удалить env_var из seed | Убрать `"env_var"` из SEED_MODELS и из логики создания AIModelORM | Файл `seed.py` не содержит строк с `env_var` |

---

## 3. User Stories

### US-001: Рабочий AI Selector на VPS

**Как** пользователь Telegram бота
**Я хочу** получать AI-ответы без ошибок 500
**Чтобы** пользоваться сервисом

**Критерии приёмки:**
- [ ] POST `/api/v1/prompts/process` возвращает 200
- [ ] AI-модель выбирается по reliability_score
- [ ] Ответ генерируется через выбранного провайдера

**Связанные требования:** FR-003, FR-004, FR-005

---

### US-002: Корректный деплой новых провайдеров

**Как** разработчик
**Я хочу** чтобы seed скрипт обновлял существующие модели
**Чтобы** добавление нового поля в seed не ломало VPS

**Критерии приёмки:**
- [ ] Существующие модели обновляются (upsert)
- [ ] Orphan модели удаляются
- [ ] Новые модели создаются

**Связанные требования:** FR-010, FR-011, FR-012

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (изменение существующей архитектуры) |
| Затрагиваемые пайплайны | Data API, Business API, Health Worker |

### 4.1 Бизнес-пайплайн

**Основной flow (до и после):**

```
ДО (сломано):
[Request] → [Get Models from Data API] → [Filter by model.env_var] → [env_var = ""] → [0 models] → 500

ПОСЛЕ (исправлено):
[Request] → [Get Models from Data API] → [Filter by ProviderRegistry.get_api_key_env()] → [N models] → 200
```

### 4.2 Data Pipeline

**Изменение потока данных:**

```
ДО:
  Data API response: { "id": 1, "name": "...", "env_var": "GROQ_API_KEY", ... }
  Business API: uses model.env_var for filtering

ПОСЛЕ:
  Data API response: { "id": 1, "name": "...", ... }  ← без env_var
  Business API: uses ProviderRegistry.get_api_key_env(model.provider)
  Health Worker: uses PROVIDER_ENV_VARS[model.provider]
```

### 4.3 Интеграционный пайплайн

**Точки интеграции:**

| ID | От | К | Изменение |
|----|----|---|-----------|
| INT-001 | Business API | Data API | Response schema теряет поле `env_var` — Business API больше не использует его |
| INT-002 | Health Worker | Data API | Response schema теряет поле `env_var` — Health Worker использует локальный dict |

### 4.4 Влияние на существующие пайплайны

| Пайплайн | Тип изменения | Затрагиваемые этапы | Обратная совместимость |
|----------|---------------|---------------------|------------------------|
| Data API | remove | Schema, ORM, Domain | Нет — поле `env_var` удалено из response |
| Business API | modify | Model selection | Да — внешний API не меняется |
| Health Worker | modify | Provider env lookup | Да — внешний API не меняется |

**Breaking changes:**
- [x] Data API: поле `env_var` удалено из GET `/api/v1/models` response
- [ ] Это НЕ breaking для клиентов, т.к. Business API и Health Worker — единственные потребители, и оба переключаются на локальные источники

---

## 5. UI/UX требования

Нет изменений UI. Рефакторинг backend-only.

---

## 6. Нефункциональные требования

### 6.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Время отклика | Без деградации (±5%) | Сравнение до/после |

### 6.2 Безопасность

| ID | Требование | Описание |
|----|------------|----------|
| NF-020 | Отсутствие секретов в коде | Env var names (не значения) в коде — допустимо |

### 6.3 Надёжность

| ID | Метрика | Требование |
|----|---------|------------|
| NF-030 | Деплой без простоя | Миграция DROP COLUMN безопасна при порядке: build → migrate → up |

### 6.4 Требования к тестированию

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Unit | Тесты process_prompt обновлены для registry-based filtering | Да |
| TRQ-002 | Unit | Тесты F012 обновлены (убран env_var из mock моделей) | Да |
| TRQ-003 | Integration | POST `/api/v1/prompts/process` → 200 на VPS | Да |
| TRQ-004 | Smoke | Health Worker logs без ошибок | Да |

---

## 7. Технические ограничения

### 7.1 Обязательные технологии

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL 16
- **Migration**: Alembic
- **Container**: Docker, Docker Compose

### 7.2 Ограничения

- Health Worker не может импортировать из Business API (отдельный микросервис) — требуется локальный dict
- Alembic миграция `0004_drop_env_var` зависит от `0003_add_available_at`
- Cloudflare провайдер не наследует `OpenAICompatibleProvider` — нужно добавить `API_KEY_ENV` явно

---

## 8. Допущения и риски

### 8.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | Все 14 провайдеров имеют `API_KEY_ENV` class variable (кроме Cloudflare) | Нужно добавить для каждого отсутствующего |
| 2 | Telegram Bot не использует `env_var` из Data API response | Нужно проверить и обновить бот |
| 3 | Нет внешних потребителей Data API кроме Business API, Health Worker, Telegram Bot | Breaking change для внешних клиентов |

### 8.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | DROP COLUMN на production DB | Low | High | Backup перед миграцией; downgrade() в миграции |
| 2 | Рассинхронизация PROVIDER_ENV_VARS в Health Worker | Med | Med | Документация; при добавлении нового провайдера обновлять оба места |
| 3 | Тесты используют env_var в фикстурах | High | Low | Обновить все тесты, моки |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Telegram Bot использует `env_var`? | Resolved | Нет — бот не работает с env_var напрямую |
| 2 | Порядок деплоя на VPS? | Resolved | `git pull → build → migrate → up` |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| SSOT | Single Source of Truth — единственный источник правды для данных |
| env_var | Имя переменной окружения, содержащей API ключ провайдера |
| API_KEY_ENV | Class variable в провайдерах, содержащий имя env переменной |
| ProviderRegistry | Singleton-реестр провайдеров в Business API (`registry.py`) |
| Upsert | INSERT OR UPDATE — создание или обновление записи |
| Orphan model | Модель в БД, отсутствующая в текущем SEED_MODELS |

---

## 11. Затронутые файлы

### Data API (`services/free-ai-selector-data-postgres-api/`)

| Файл | Изменение |
|------|-----------|
| `app/infrastructure/database/models.py` | Удалить `env_var` из ORM |
| `app/domain/models.py` | Удалить `env_var` из dataclass |
| `app/api/v1/schemas.py` | Удалить `env_var` из Pydantic schema |
| `app/api/v1/models.py` | Убрать `env_var` из `_model_to_response()` |
| `app/infrastructure/database/seed.py` | Убрать `env_var` из SEED_MODELS; добавить upsert + cleanup |
| `alembic/versions/0004_drop_env_var.py` | Новый — DROP COLUMN env_var |

### Business API (`services/free-ai-selector-business-api/`)

| Файл | Изменение |
|------|-----------|
| `app/infrastructure/ai_providers/registry.py` | Добавить `get_api_key_env()` classmethod |
| `app/infrastructure/ai_providers/cloudflare.py` | Добавить `API_KEY_ENV = "CLOUDFLARE_API_TOKEN"` |
| `app/application/use_cases/process_prompt.py` | `_filter_configured_models()` — registry вместо model.env_var |
| `app/domain/models.py` | Удалить `env_var` из `AIModelInfo` |
| `app/infrastructure/http_clients/data_api_client.py` | Убрать парсинг `env_var` |
| `tests/conftest.py` | Убрать `env_var` из фикстур |
| `tests/unit/test_process_prompt_use_case.py` | Mock `ProviderRegistry.get_api_key_env()` |
| `tests/unit/test_f012_rate_limit_handling.py` | Убрать `env_var` из mock-моделей |

### Health Worker (`services/free-ai-selector-health-worker/`)

| Файл | Изменение |
|------|-----------|
| `app/main.py` | Добавить `PROVIDER_ENV_VARS` dict; заменить `model.get("env_var")` |

---

## 12. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-02-11 | AI Analyst | Первоначальная версия |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-001..FR-012, NF-001..NF-030, TRQ-001..TRQ-004)
- [x] Критерии приёмки определены для каждого требования
- [x] User stories связаны с требованиями
- [x] Бизнес-пайплайн описан
- [x] Data Pipeline описан
- [x] Интеграционный пайплайн описан
- [x] Раздел "Влияние на существующие пайплайны" заполнен
- [x] Нет блокирующих открытых вопросов
- [x] Риски идентифицированы и имеют план митигации
- [x] Затронутые файлы перечислены (Section 11)
