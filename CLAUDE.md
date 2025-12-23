# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Free AI Selector is a reliability-based AI routing platform that automatically selects the best-performing free AI model. It uses the formula: `reliability_score = (success_rate × 0.6) + (speed_score × 0.4)`.

## Architecture

**5 microservices + PostgreSQL** with HTTP-only data access:

```
┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│  Business API   │
│  (aiogram 3.x)  │     │  (FastAPI:8000) │
└─────────────────┘     └────────┬────────┘
                                 │ HTTP only
┌─────────────────┐     ┌────────▼────────┐     ┌──────────┐
│  Health Worker  │────▶│    Data API     │────▶│ Postgres │
│  (APScheduler)  │     │  (FastAPI:8001) │     │   :5432  │
└─────────────────┘     └─────────────────┘     └──────────┘
        ▲
        │
┌───────┴───────┐
│ Nginx (proxy) │  External :8000 → Business API
└───────────────┘
```

**Key rule**: Business services access data ONLY via HTTP to Data API, never direct DB.

### Services (in `services/`)

| Service | Purpose | Internal Port |
|---------|---------|---------------|
| `aimanager_data_postgres_api` | CRUD for AI models, prompt history | 8001 |
| `aimanager_business_api` | Model selection, AI provider integration | 8000 |
| `aimanager_telegram_bot` | Russian-language user interface | - |
| `aimanager_health_worker` | Hourly synthetic monitoring | - |
| `aimanager_nginx` | Reverse proxy with AI-optimized timeouts | 8000 |

### Layer Structure (DDD/Hexagonal)

Each service follows: `app/api/` → `app/application/` → `app/domain/` → `app/infrastructure/`

## Common Commands

```bash
# Docker operations
make build              # Build all images
make up                 # Start services + health check
make down               # Stop services
make logs               # All service logs
make logs-business      # Business API logs only

# Database
make migrate            # Run Alembic migrations
make seed               # Seed AI models
make db-shell           # PostgreSQL shell

# Testing (≥75% coverage required)
make test               # Run all tests
make test-data          # Data API tests only
make test-business      # Business API tests only

# Code quality
make lint               # ruff + mypy + bandit
make format             # ruff format

# Debug
make shell-business     # Shell in Business API container
make health             # Check all service health
```

### Running single test

```bash
docker compose exec aimanager_business_api pytest tests/unit/test_process_prompt_use_case.py -v
docker compose exec aimanager_data_postgres_api pytest tests/unit/test_domain_models.py::test_specific -v
```

## AI Providers

6 free providers in `services/aimanager_business_api/app/infrastructure/ai_providers/`:
- `google_gemini.py` - Google AI Studio
- `groq.py` - Groq LPU
- `cerebras.py` - Cerebras
- `sambanova.py` - SambaNova
- `huggingface.py` - HuggingFace Inference
- `cloudflare.py` - Cloudflare Workers AI

All inherit from `base.py:AIProviderBase`.

## External Ports (VPS)

Configured in docker-compose.yml to avoid conflicts:
- `8000` - Business API (via nginx)
- `8002` - Data API
- `5433` - PostgreSQL

## API Documentation

When services are running:
- Business API: http://localhost:8000/docs
- Data API: http://localhost:8002/docs

## Adding a New AI Provider

1. Create `services/aimanager_business_api/app/infrastructure/ai_providers/newprovider.py` extending `AIProviderBase`
2. Register in `app/application/use_cases/process_prompt.py`
3. Add model to `services/aimanager_data_postgres_api/app/infrastructure/database/seed.py`
4. Add env var to `.env` and `docker-compose.yml`

## Submodules

- `.aidd/` - AIDD MVP Generator framework (read-only knowledge base for AI-driven development)

---

<!-- Добавлено из шаблона AIDD -->

## AIDD Framework Integration

Этот проект использует фреймворк **AIDD-MVP Generator** для AI-driven разработки.

| Документ | Путь | Назначение |
|----------|------|------------|
| Фреймворк | [.aidd/CLAUDE.md](.aidd/CLAUDE.md) | Правила и процесс разработки |
| Workflow | [.aidd/workflow.md](.aidd/workflow.md) | Пайплайн (этапы 0-8) |
| Conventions | [.aidd/conventions.md](.aidd/conventions.md) | Соглашения о коде |

## Slash-команды (AIDD Pipeline)

| # | Команда | Описание | Агент | Ворота IN | Ворота OUT |
|---|---------|----------|-------|-----------|------------|
| 0 | `/init` | Инициализация проекта | — | — | BOOTSTRAP_READY |
| 1 | `/idea` | Создание PRD документа | Аналитик | BOOTSTRAP_READY | PRD_READY |
| 2 | `/research` | Анализ кодовой базы | Исследователь | PRD_READY | RESEARCH_DONE |
| 3 | `/plan` | Архитектурный план (CREATE) | Архитектор | RESEARCH_DONE | PLAN_APPROVED |
| 3 | `/feature-plan` | План фичи (FEATURE) | Архитектор | RESEARCH_DONE | PLAN_APPROVED |
| 4 | `/generate` | Генерация кода | Реализатор | PLAN_APPROVED | IMPLEMENT_OK |
| 5 | `/review` | Код-ревью | Ревьюер | IMPLEMENT_OK | REVIEW_OK |
| 6 | `/test` | Тестирование и QA | QA | REVIEW_OK | QA_PASSED |
| 7 | `/validate` | Финальная проверка | Валидатор | QA_PASSED | ALL_GATES_PASSED |
| 8 | `/deploy` | Сборка и запуск | Валидатор | ALL_GATES_PASSED | DEPLOYED |

### Алгоритм выполнения команды для AI

1. **Проверить ворота**: Прочитать `.pipeline-state.json`, убедиться что Ворота IN пройдены
2. **Загрузить инструкции**: Прочитать `.aidd/.claude/commands/{command}.md`
3. **Загрузить роль**: Прочитать `.aidd/.claude/agents/{agent}.md` (если указан агент)
4. **Выполнить**: Следовать инструкциям из загруженных файлов
5. **Обновить состояние**: Записать результат в `.pipeline-state.json`

## Роли AI-агентов

| Роль | Файл инструкций | Этапы | Ответственность |
|------|-----------------|-------|-----------------|
| Аналитик | `.aidd/.claude/agents/analyst.md` | 1 | PRD, требования |
| Исследователь | `.aidd/.claude/agents/researcher.md` | 2 | Анализ кода/требований |
| Архитектор | `.aidd/.claude/agents/architect.md` | 3 | Проектирование |
| Реализатор | `.aidd/.claude/agents/implementer.md` | 4 | Генерация кода |
| Ревьюер | `.aidd/.claude/agents/reviewer.md` | 5 | Качество кода |
| QA | `.aidd/.claude/agents/qa.md` | 6 | Тестирование |
| Валидатор | `.aidd/.claude/agents/validator.md` | 7-8 | Финальная проверка, деплой |

## Порядок чтения файлов для AI

### При первом запуске (новая сессия)

```
1. ./CLAUDE.md                  ← Этот файл (контекст проекта)
2. ./.pipeline-state.json       ← Состояние, режим, ворота
3. ./ai-docs/docs/              ← Существующие артефакты
4. ./.aidd/CLAUDE.md            ← Правила фреймворка
```

### При выполнении команды

```
1. ./.aidd/.claude/commands/{command}.md   ← Инструкции команды
2. ./.aidd/.claude/agents/{agent}.md       ← Инструкции роли (если есть)
3. ./.aidd/templates/documents/            ← Шаблоны (при создании)
```

## Правила для AI (AIDD)

1. **Читать сначала контекст проекта** (этот файл, .pipeline-state.json, ai-docs/)
2. **Затем инструкции фреймворка** (.aidd/)
3. **Не модифицировать .aidd/** — это read-only submodule
4. **Проверять ворота** перед переходом к следующему этапу
5. **Генерировать код** только в `services/` и корне проекта
