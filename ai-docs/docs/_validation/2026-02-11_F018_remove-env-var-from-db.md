---
feature_id: "F018"
feature_name: "remove-env-var-from-db"
title: "Completion Report: Удаление env_var из БД, SSOT через ProviderRegistry"
created: "2026-02-11"
deployed: null
author: "AI (Validator)"
type: "completion"
status: "DRAFT"
version: 1

metrics:
  coverage_percent: null
  tests_passed: null
  tests_total: null
  security_issues: 0

services:
  - free-ai-selector-data-postgres-api
  - free-ai-selector-business-api
  - free-ai-selector-health-worker

adr_count: 4

artifacts:
  prd: "_analysis/2026-02-11_F018_remove-env-var-from-db.md"
  research: "_research/2026-02-11_F018_remove-env-var-from-db.md"
  plan: "_plans/features/2026-02-11_F018_remove-env-var-from-db.md"

depends_on:
  - F008
  - F013
enables: []
---

# Completion Report: Удаление env_var из БД, SSOT через ProviderRegistry

> **Feature ID**: F018
> **Статус**: DRAFT
> **Дата создания**: 2026-02-11
> **Автор**: AI Agent (Валидатор)

> **DRAFT — QA не выполнено. Статический анализ пройден. Для production-ready результата требуется полный /aidd-validate.**

---

## 1. Executive Summary

F018 устраняет нарушение SSOT: колонка `env_var` дублировалась в БД (seed.py) и в классах провайдеров (`API_KEY_ENV`). Это приводило к production-критическому багу на VPS — Business API возвращал 500 на все запросы из-за пустого `env_var` у 16 моделей. Решение: полное удаление `env_var` из БД, `ProviderRegistry.get_api_key_env()` как единственный источник правды.

### 1.1 Ключевые результаты

| Метрика | Значение |
|---------|----------|
| Сервисов затронуто | 3 |
| Файлов изменено | 17 |
| Требований реализовано | 9/9 (FR-001 — FR-012) |
| ADR задокументировано | 4 |
| Все ворота пройдены | DRAFT (DOCUMENTED) |

### 1.2 Затронутые сервисы

- **free-ai-selector-data-postgres-api** — удалён `env_var` из ORM, domain, schema, API response; upsert seed; Alembic миграция
- **free-ai-selector-business-api** — `ProviderRegistry.get_api_key_env()` SSOT; Cloudflare `API_KEY_ENV` fix
- **free-ai-selector-health-worker** — `PROVIDER_ENV_VARS` dict для lookup env var по provider name

---

## 2. Реализованные компоненты

### 2.1 Data API изменения

| Файл | Изменение |
|------|-----------|
| `infrastructure/database/models.py` | Удалён `env_var` mapped_column из AIModelORM |
| `domain/models.py` | Удалён `env_var` из AIModel dataclass |
| `api/v1/schemas.py` | Удалён `env_var` из AIModelResponse Pydantic schema |
| `api/v1/models.py` | Удалён `env_var` из `_model_to_response()` |
| `infrastructure/repositories/ai_model_repository.py` | Удалён `env_var` из `_to_domain()` |
| `infrastructure/database/seed.py` | Удалён `env_var` из SEED_MODELS; добавлен upsert + cleanup orphans |
| `alembic/versions/20260211_0004_drop_env_var.py` | DROP COLUMN `env_var` (новая миграция) |

### 2.2 Business API изменения

| Файл | Изменение |
|------|-----------|
| `infrastructure/ai_providers/cloudflare.py` | Добавлен `API_KEY_ENV = "CLOUDFLARE_API_TOKEN"` |
| `infrastructure/ai_providers/registry.py` | Добавлен `get_api_key_env()` classmethod |
| `application/use_cases/process_prompt.py` | `_filter_configured_models()` использует registry вместо `model.env_var` |
| `domain/models.py` | Удалён `env_var` из AIModelInfo dataclass |
| `infrastructure/http_clients/data_api_client.py` | Удалён парсинг `env_var` из API response |

### 2.3 Health Worker изменения

| Файл | Изменение |
|------|-----------|
| `app/main.py` | Добавлен `PROVIDER_ENV_VARS` dict (14 провайдеров); `universal_health_check()` lookup по provider name |

### 2.4 Тесты

| Файл | Изменение |
|------|-----------|
| `business-api/tests/conftest.py` | Удалён `env_var` из фикстур |
| `business-api/tests/unit/test_process_prompt_use_case.py` | Mock ProviderRegistry.get_api_key_env() |
| `business-api/tests/unit/test_f012_rate_limit_handling.py` | Mock ProviderRegistry.get_api_key_env(); переписаны TestF012FilterConfiguredModels |
| `data-api/tests/unit/test_f015_dry_refactoring.py` | Удалён `env_var` из `_create_test_model()` |

---

## 3. Architecture Decision Records (ADR)

### ADR-001: ProviderRegistry.get_api_key_env() как SSOT

| Аспект | Описание |
|--------|----------|
| **Решение** | Новый classmethod `get_api_key_env(name)` читает `API_KEY_ENV` из класса провайдера без инстанцирования |
| **Контекст** | env_var дублировался в БД и в классах — нарушение SSOT. Инстанцирование провайдера бросает ValueError при отсутствии ключа |
| **Альтернативы** | 1) Исправить seed.py (не устраняет дублирование), 2) Получать из инстанса (бросает ValueError) |
| **Последствия** | **Плюсы**: единый источник правды, нет дублирования / **Минусы**: нет |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

### ADR-002: Cloudflare API_KEY_ENV class variable

| Аспект | Описание |
|--------|----------|
| **Решение** | Добавить `API_KEY_ENV = "CLOUDFLARE_API_TOKEN"` в CloudflareProvider |
| **Контекст** | Cloudflare — единственный провайдер без `API_KEY_ENV` (наследует AIProviderBase, не OpenAICompatibleProvider). В seed.py был баг: `"CLOUDFLARE_API_KEY"` вместо `"CLOUDFLARE_API_TOKEN"` |
| **Альтернативы** | Хардкод в registry (нарушает паттерн) |
| **Последствия** | **Плюсы**: единообразие, исправлен баг / **Минусы**: нет |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

### ADR-003: Health Worker PROVIDER_ENV_VARS dict

| Аспект | Описание |
|--------|----------|
| **Решение** | Локальный dict `PROVIDER_ENV_VARS` маппинг provider name → env var name |
| **Контекст** | Health Worker — отдельный микросервис, не может импортировать ProviderRegistry из Business API |
| **Альтернативы** | 1) Shared library (overhead для 14 строк), 2) Запрашивать из Data API (circular dependency) |
| **Последствия** | **Плюсы**: простота, изоляция / **Минусы**: дублирование с registry (14 строк, редко меняется) |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

### ADR-004: Seed upsert + orphan cleanup

| Аспект | Описание |
|--------|----------|
| **Решение** | seed.py обновляет поля существующих моделей (api_format, api_endpoint, is_active) и удаляет модели, отсутствующие в SEED_MODELS |
| **Контекст** | Старый seed пропускал существующие записи → поля добавленные позже оставались пустыми (root cause бага на VPS) |
| **Альтернативы** | DROP + INSERT (потеря статистик) |
| **Последствия** | **Плюсы**: предотвращает подобные баги, чистит orphans / **Минусы**: сложнее старого seed |
| **Статус** | Принято |
| **Дата** | 2026-02-11 |

---

## 4. Отклонения от плана (Scope Changes)

### 4.1 Что планировали vs что сделали

| Требование | План | Факт | Причина |
|------------|------|------|---------|
| FR-001 | DROP COLUMN env_var | Реализовано | — |
| FR-002 | Удалить env_var из Data API | Реализовано | — |
| FR-003 | ProviderRegistry.get_api_key_env() | Реализовано | — |
| FR-004 | Cloudflare API_KEY_ENV | Реализовано | — |
| FR-005 | Business API registry-based filtering | Реализовано | — |
| FR-006 | Health Worker PROVIDER_ENV_VARS | Реализовано | — |
| FR-010 | Seed upsert | Реализовано | — |
| FR-011 | Seed orphan cleanup | Реализовано | — |
| FR-012 | Удалить env_var из seed | Реализовано | — |

### 4.2 Дополнительно реализовано (не было в плане)

| Описание | Причина |
|----------|---------|
| Обнаружены и исправлены пропущенные `env_var` в `ai_model_repository.py:_to_domain()` и `data_api_client.py:get_model_by_id()` | Финальная grep-верификация выявила пропущенные места |

---

## 5. Известные ограничения и Technical Debt

### 5.1 Known Limitations

| ID | Описание | Влияние | Workaround |
|----|----------|---------|------------|
| KL-001 | Health Worker PROVIDER_ENV_VARS дублирует данные из registry | При добавлении нового провайдера нужно обновить оба места | Задокументировано в docstring |

### 5.2 Technical Debt

| ID | Описание | Приоритет | Рекомендация |
|----|----------|-----------|--------------|
| TD-001 | Pre-existing mypy ошибки (10 шт) в Data API и Business API | Low | Исправить отдельно от F018 |
| TD-002 | Pre-existing ruff F401 в Health Worker utils | Low | Добавить explicit re-export |

### 5.3 Security Considerations

| Аспект | Статус | Комментарий |
|--------|--------|-------------|
| Secrets в .env | ✅ | Не в git, .gitignore настроен |
| Hardcoded credentials | ✅ | API keys только из env vars |
| Input validation | ✅ | Pydantic schemas |
| SQL Injection | ✅ | SQLAlchemy ORM |
| Bandit scan | ✅ | 0 issues (5251 LOC scanned) |

---

## 6. Метрики качества

### 6.1 Static Analysis (Quick Mode)

| Инструмент | Data API | Business API | Health Worker | F018-specific |
|-----------|----------|-------------|--------------|---------------|
| ruff | 0 errors | 0 errors | 1 error (pre-existing F401) | 0 errors |
| bandit | 0 issues | 0 issues | 0 issues | 0 issues |
| mypy | 5 errors (pre-existing) | 5 errors (pre-existing) | 0 errors | 0 errors |

### 6.2 Code Quality

| Метрика | Значение |
|---------|----------|
| Файлов изменено | 17 |
| Строк добавлено | 195 |
| Строк удалено | 88 |
| Type Hints Coverage | 100% (в F018 коде) |
| Backward Compatible | Да (для внешних клиентов) |

### 6.3 Test Coverage

> Skipped (Quick mode). Тесты не запускались.

---

## 7. Зависимости

### 7.1 Зависит от (depends_on)

| FID | Название | Как используется |
|-----|----------|------------------|
| F008 | Provider Registry SSOT | ProviderRegistry — основа SSOT. F018 расширяет registry методом get_api_key_env() |
| F013 | AI Providers Consolidation | OpenAICompatibleProvider.API_KEY_ENV — используется для lookup в registry |

### 7.2 Включает возможность для (enables)

| Потенциальная фича | Как может использовать |
|-------------------|----------------------|
| Добавление нового провайдера | Достаточно добавить класс с API_KEY_ENV и запись в seed.py — env_var разрешается автоматически |

---

## 8. Ссылки на артефакты

| Артефакт | Путь | Статус |
|----------|------|--------|
| PRD | `ai-docs/docs/_analysis/2026-02-11_F018_remove-env-var-from-db.md` | ✅ |
| Research | `ai-docs/docs/_research/2026-02-11_F018_remove-env-var-from-db.md` | ✅ |
| Plan | `ai-docs/docs/_plans/features/2026-02-11_F018_remove-env-var-from-db.md` | ✅ |
| Completion | `ai-docs/docs/_validation/2026-02-11_F018_remove-env-var-from-db.md` | ✅ (DRAFT) |

---

## 9. Timeline

| Дата | Этап | Ворота | Комментарий |
|------|------|--------|-------------|
| 2026-02-11 | Идея | PRD_READY | PRD создан |
| 2026-02-11 | Исследование | RESEARCH_DONE | 15 файлов проанализировано, blast radius определён |
| 2026-02-11 | Архитектура | PLAN_APPROVED | 9-шаговый план утверждён пользователем |
| 2026-02-11 | Реализация | IMPLEMENT_OK | 17 файлов изменено, 1 создан |
| 2026-02-11 | Документация | DOCUMENTED | DRAFT Completion Report |

**Общее время разработки**: 1 день

---

## 10. Рекомендации для следующих итераций

### 10.1 Высокий приоритет

1. **Деплой на VPS**: `git pull → make build → make migrate → make seed → make up → make health`. Это устранит production 500 баг.
2. **Полный /aidd-validate**: Запустить полный цикл (Review + Test + Validate + Deploy) для production-ready статуса.

### 10.2 Средний приоритет

1. **Исправить pre-existing mypy ошибки**: 10 ошибок в Data API и Business API не связаны с F018.
2. **Shared provider config**: Рассмотреть вынесение PROVIDER_ENV_VARS в shared config для Health Worker.

---

## Заключение

**Статус фичи**: DRAFT (DOCUMENTED)

F018 устраняет архитектурное нарушение SSOT — колонка `env_var` удалена из базы данных, `ProviderRegistry.get_api_key_env()` стал единственным источником правды для имён env переменных API ключей. Попутно исправлен баг Cloudflare (`CLOUDFLARE_API_KEY` → `CLOUDFLARE_API_TOKEN`) и улучшен seed-скрипт (upsert вместо skip для существующих моделей). Все 9 требований реализованы, статический анализ пройден без F018-специфичных ошибок.

---

**Документ создан**: 2026-02-11
**Автор**: AI Agent (Валидатор)
**Версия**: 1.0 (DRAFT)

---

## Для AI-агентов: Quick Reference

```yaml
feature_id: F018
feature_name: remove-env-var-from-db
status: DRAFT
services:
  - free-ai-selector-data-postgres-api
  - free-ai-selector-business-api
  - free-ai-selector-health-worker
key_changes:
  - DROP COLUMN env_var from ai_models
  - ProviderRegistry.get_api_key_env() classmethod
  - Cloudflare API_KEY_ENV = "CLOUDFLARE_API_TOKEN"
  - Health Worker PROVIDER_ENV_VARS dict
  - Seed upsert + orphan cleanup
depends_on:
  - F008 (Provider Registry SSOT)
  - F013 (AI Providers Consolidation)
known_limitations:
  - KL-001: Health Worker PROVIDER_ENV_VARS duplicates registry data
technical_debt:
  - TD-001: Pre-existing mypy errors (10)
  - TD-002: Pre-existing ruff F401 in health-worker utils
```
