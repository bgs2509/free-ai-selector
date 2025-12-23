# CLAUDE.md

Этот файл предоставляет инструкции для Claude Code (claude.ai/code) при работе с кодом в этом репозитории.

## Обзор проекта

Free AI Selector — платформа маршрутизации AI на основе надёжности, автоматически выбирающая лучшую бесплатную AI-модель. Формула расчёта: `reliability_score = (success_rate × 0.6) + (speed_score × 0.4)`.

## Архитектура

**5 микросервисов + PostgreSQL** с HTTP-only доступом к данным:

```
┌──────────────┐     ┌──────────────┐
│ Telegram Bot │────▶│ Business API │◀──┐
│ (aiogram 3.x)│     │(FastAPI:8000)│   │
└──────────────┘     └──────┬───────┘   │
                            │ HTTP only │
┌──────────────┐     ┌──────▼───────┐   │   ┌──────────┐
│Health Worker │────▶│   Data API   │──▶│──▶│ Postgres │
│ (APScheduler)│     │(FastAPI:8001)│   │   │  :5432   │
└──────────────┘     └──────────────┘   │   └──────────┘
                                        │
                     ┌──────────────┐   │
                     │    Nginx     │───┘
                     │ :8000 (ext)  │
                     └──────────────┘
```

**Ключевое правило**: Бизнес-сервисы обращаются к данным ТОЛЬКО через HTTP к Data API, никогда напрямую к БД.

### Сервисы (в `services/`)

| Сервис | Назначение | Внутр. | Внешн. |
|--------|------------|--------|--------|
| `aimanager_data_postgres_api` | CRUD для AI-моделей, история промптов | 8001 | 8002 |
| `aimanager_business_api` | Выбор модели, интеграция с AI-провайдерами | 8000 | через nginx |
| `aimanager_telegram_bot` | Пользовательский интерфейс (русский язык) | - | - |
| `aimanager_health_worker` | Почасовой синтетический мониторинг | - | - |
| `aimanager_nginx` | Reverse proxy с оптимизированными таймаутами для AI | 8000 | 8000 |
| `postgres` | База данных PostgreSQL 16 | 5432 | 5433 |

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
docker compose exec aimanager_business_api pytest tests/unit/test_process_prompt_use_case.py -v
docker compose exec aimanager_data_postgres_api pytest tests/unit/test_domain_models.py::test_specific -v
```

## AI-провайдеры

6 бесплатных провайдеров в `services/aimanager_business_api/app/infrastructure/ai_providers/`:
- `google_gemini.py`, `groq.py`, `cerebras.py`, `sambanova.py`, `huggingface.py`, `cloudflare.py`

Все наследуют от `base.py:AIProviderBase` (должны реализовать `generate()`, `health_check()`, `get_provider_name()`).

### Добавление нового провайдера

1. Создать `services/aimanager_business_api/app/infrastructure/ai_providers/newprovider.py`, наследующий `AIProviderBase`
2. Зарегистрировать в `app/application/use_cases/process_prompt.py:ProcessPromptUseCase.providers`
3. Добавить модель в `services/aimanager_data_postgres_api/app/infrastructure/database/seed.py`
4. Добавить env-переменную в `.env` и `docker-compose.yml`

## API документация

При запущенных сервисах:
- Business API: http://localhost:8000/docs
- Data API: http://localhost:8002/docs

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

Проект использует фреймворк AIDD-MVP Generator (read-only submodule в `.aidd/`).

**Не модифицировать файлы в `.aidd/`** — для AI-driven разработки см. [.aidd/CLAUDE.md](.aidd/CLAUDE.md)

### Slash-команды AIDD

| # | Команда | Описание | Ворота |
|---|---------|----------|--------|
| 0 | `/aidd-init` | Инициализация проекта | BOOTSTRAP_READY |
| 1 | `/aidd-idea` | Создание PRD | PRD_READY |
| 2 | `/aidd-research` | Анализ кодовой базы | RESEARCH_DONE |
| 3 | `/aidd-plan` | Архитектурный план | PLAN_APPROVED |
| 3 | `/aidd-feature-plan` | План фичи | PLAN_APPROVED |
| 4 | `/aidd-generate` | Генерация кода | IMPLEMENT_OK |
| 5 | `/aidd-review` | Код-ревью | REVIEW_OK |
| 6 | `/aidd-test` | Тестирование | QA_PASSED |
| 7 | `/aidd-validate` | Финальная проверка | ALL_GATES_PASSED |
| 8 | `/aidd-deploy` | Сборка и запуск | DEPLOYED |
