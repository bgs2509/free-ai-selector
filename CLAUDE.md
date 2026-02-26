# CLAUDE.md

Этот файл предоставляет инструкции для Claude Code (claude.ai/code) при работе с кодом в этом репозитории.

## Обзор проекта

Free AI Selector — платформа маршрутизации AI на основе надёжности, автоматически выбирающая лучшую бесплатную AI-модель. Формула расчёта: `reliability_score = (success_rate × 0.6) + (speed_score × 0.4)`.

## Архитектура

**4 микросервиса + PostgreSQL** с HTTP-only доступом к данным:

```
┌──────────────┐     ┌──────────────┐
│ Telegram Bot │────▶│ Business API │◀────────────┐
│ (aiogram 3.x)│     │(FastAPI:8000)│             │
└──────────────┘     └──────┬───────┘             │
                            │ HTTP only           │
┌──────────────┐     ┌──────▼───────┐   ┌────────┴───────┐
│Health Worker │────▶│   Data API   │   │  nginx-proxy   │
│ (APScheduler)│     │(FastAPI:8001)│   │ (внешний VPS)  │
└──────────────┘     └──────┬───────┘   └────────────────┘
                            │
                     ┌──────▼───────┐
                     │   Postgres   │
                     │    :5432     │
                     └──────────────┘
```

**Ключевое правило**: Бизнес-сервисы обращаются к данным ТОЛЬКО через HTTP к Data API, никогда напрямую к БД.

### Сервисы (в `services/`)

| Сервис | Назначение | Порт |
|--------|------------|------|
| `free-ai-selector-data-postgres-api` | CRUD для AI-моделей, история промптов | 8001 |
| `free-ai-selector-business-api` | Выбор модели, интеграция с AI-провайдерами | 8000 |
| `free-ai-selector-telegram-bot` | Пользовательский интерфейс (русский язык) | - |
| `free-ai-selector-health-worker` | Почасовой синтетический мониторинг | - |
| `free-ai-selector-postgres` | База данных PostgreSQL 16 | 5432 |

### Слоистая структура (DDD/Hexagonal)

Каждый сервис следует: `app/api/` → `app/application/` → `app/domain/` → `app/infrastructure/`

## Основные команды

```bash
# Docker операции
make build              # Собрать все образы
make up                 # Запустить сервисы + проверка здоровья
make down               # Остановить сервисы
make logs               # Логи всех сервисов
make logs-business      # Логи только Business API

# База данных
make migrate            # Запустить миграции Alembic
make seed               # Заполнить AI-модели
make db-shell           # PostgreSQL shell

# Тестирование (≥75% покрытия обязательно)
make test               # Все тесты
make test-data          # Тесты только Data API
make test-business      # Тесты только Business API

# Качество кода
make lint               # ruff + mypy + bandit
make format             # ruff format

# Отладка
make shell-business     # Shell в контейнере Business API
make health             # Проверить здоровье всех сервисов
```

### Запуск одного теста

```bash
docker compose exec free-ai-selector-business-api pytest tests/unit/test_process_prompt_use_case.py -v
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_domain_models.py::test_specific -v
```

## AI-провайдеры

13 бесплатных провайдеров в `services/free-ai-selector-business-api/app/infrastructure/ai_providers/`:
- Существующие (5): `groq.py`, `cerebras.py`, `sambanova.py`, `huggingface.py`, `cloudflare.py`
- Новые F003 (8): `deepseek.py`, `openrouter.py`, `github_models.py`, `fireworks.py`, `hyperbolic.py`, `novita.py`, `scaleway.py`, `nebius.py`

Все наследуют от `base.py:AIProviderBase` (должны реализовать `generate()`, `health_check()`, `get_provider_name()`).

### Добавление нового провайдера

1. Создать `services/free-ai-selector-business-api/app/infrastructure/ai_providers/newprovider.py`, наследующий `AIProviderBase`
2. Зарегистрировать в `app/application/use_cases/process_prompt.py:ProcessPromptUseCase.providers`
3. Добавить модель в `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`
4. Добавить env-переменную в `.env` и `docker-compose.yml`

## API документация

При запущенных сервисах:
- Business API: http://localhost:8000/docs
- Data API: http://localhost:8001/docs

## VPS деплой

Проект настроен для деплоя на VPS с внешним nginx-proxy:

```bash
# На VPS
cd /opt/free-ai-selector
./scripts/deploy-vps.sh deploy   # Полный деплой
./scripts/deploy-vps.sh update   # Обновление
./scripts/deploy-vps.sh health   # Проверка здоровья
```

Доступ через nginx-proxy: `http://<VPS_IP>/free-ai-selector/`

## Документация проекта

Полная документация в `docs/`:

| Раздел | Описание |
|--------|----------|
| [docs/index.md](docs/index.md) | Главная навигация |
| [docs/ai-context/](docs/ai-context/) | **AI Context Files для Claude Code** |
| [docs/project/](docs/project/) | Специфика проекта |
| [docs/api/](docs/api/) | API Reference |
| [docs/operations/](docs/operations/) | Runbooks и troubleshooting |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

### AI Context Files (для генерации кода)

| Файл | Описание |
|------|----------|
| [docs/ai-context/PROJECT_CONTEXT.md](docs/ai-context/PROJECT_CONTEXT.md) | Quick facts, правила, CORRECT/WRONG примеры |
| [docs/ai-context/SERVICE_MAP.md](docs/ai-context/SERVICE_MAP.md) | Карта сервисов, endpoints, env vars |
| [docs/ai-context/EXAMPLES.md](docs/ai-context/EXAMPLES.md) | Примеры кода: endpoints, use cases, tests |

## AIDD Framework

Проект использует фреймворк AIDD-MVP Generator v4.0 (read-only submodule в `.aidd/`).

**Не модифицировать файлы в `.aidd/`** — для AI-driven разработки см. [.aidd/CLAUDE.md](.aidd/CLAUDE.md)

### Команды AIDD (v4.0+)

Фреймворк использует унифицированную систему именования на базе 5 ключевых слов:

**analyst, researcher, planner, coder, validator**

| Команда | Роль |
|---------|------|
| `/aidd-analyze` | Аналитик |
| `/aidd-research` | Исследователь |
| `/aidd-plan` | Планировщик (CREATE) |
| `/aidd-plan-feature` | Планировщик (FEATURE) |
| `/aidd-code` | Программист |
| `/aidd-validate` | Валидатор |

### Slash-команды AIDD

| # | Этап | Команда | Агент | Ворота | Артефакт |
|---|------|---------|-------|--------|----------|
| 0 | Bootstrap | `/aidd-init` | — | `BOOTSTRAP_READY` | Структура проекта |
| 1 | Идея | `/aidd-analyze` | Аналитик | `PRD_READY` | `_analysis/{name}.md` |
| 2 | Исследование | `/aidd-research` | Исследователь | `RESEARCH_DONE` | `_research/{name}.md` |
| 3 | Архитектура (CREATE) | `/aidd-plan` | Планировщик | `PLAN_APPROVED` | `_plans/mvp/{name}.md` |
| 3 | Архитектура (FEATURE) | `/aidd-plan-feature` | Планировщик | `PLAN_APPROVED` | `_plans/features/{feature}.md` |
| 4 | Реализация | `/aidd-code` | Программист | `IMPLEMENT_OK` | `services/`, тесты |
| 5 | Quality & Deploy | `/aidd-validate` | Валидатор | `REVIEW_OK`, `QA_PASSED`, `ALL_GATES_PASSED`, `DEPLOYED` | `_validation/{name}.md` |

**Примечание**: Команды `/aidd-review`, `/aidd-test`, `/aidd-deploy` не существуют как отдельные — они являются шагами внутри `/aidd-validate`.

### Naming Version

Проект использует `naming_version: "v3"` в `.pipeline-state.json` — современная структура артефактов, соответствующая AIDD v4.0+.

**Преимущества v3:**
- Чистая структура с префиксом `_` для артефактов (`_analysis/`, `_plans/`, `_validation/`, `_research/`)
- Меньше дублирования в именах файлов (`{name}.md` вместо `{name}-prd.md`)
- Соответствие стандарту AIDD v4.0+
- Улучшенная читаемость и организация

**Миграция:** Выполнена 2026-01-29, backup сохранён в теге `before-aidd-v4-migration`.
