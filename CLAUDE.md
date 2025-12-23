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
