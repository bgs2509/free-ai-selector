# Free AI Selector

> **Intelligent AI Model Selection Platform** - Automatically choose the best free AI model based on real-time reliability metrics

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/framework-AIDD--MVP-purple.svg)](.aidd/)
[![Maturity Level](https://img.shields.io/badge/maturity-Level%202%20(Development)-green.svg)](.aidd/docs/)

## 🎯 What is Free AI Selector?

Free AI Selector is a **reliability-based AI routing platform** that automatically selects the best-performing free AI model for your prompts. Instead of manually trying different AI providers, the platform:

- **Monitors** real-time success rates and response times across multiple free AI providers
- **Selects** the most reliable model using the formula: `reliability_score = (success_rate × 0.6) + (speed_score × 0.4)`
- **Routes** your requests automatically to the best-performing provider
- **Learns** from actual usage and synthetic monitoring to improve selection accuracy

### Key Features

✅ **Dual-Channel Access**: REST API + Telegram Bot
✅ **Smart Selection**: Automatic model selection based on reliability metrics
✅ **Dual Monitoring**: Real-time metrics from actual requests + hourly synthetic checks
✅ **6 Free AI Providers**: No credit card required - Google Gemini, Groq, Cerebras, SambaNova, HuggingFace, Cloudflare
✅ **Production-Ready**: Level 2 maturity with health checks, JSON logging, and integration tests

---

## 🏗️ Architecture

**Improved Hybrid Approach** with HTTP-only data access and 4 microservices:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI Manager Platform                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐          ┌──────────────────┐            │
│  │  Telegram Bot    │          │  Business API    │            │
│  │  (aiogram 3.x)   │─────────▶│  (FastAPI)       │            │
│  └──────────────────┘          └──────────────────┘            │
│         │                              │                        │
│         │                              │ HTTP Only              │
│         │                              ▼                        │
│         │                      ┌──────────────────┐            │
│         │                      │  Data API        │            │
│         └─────────────────────▶│  (PostgreSQL)    │            │
│                                └──────────────────┘            │
│                                        ▲                        │
│                                        │                        │
│                                ┌──────────────────┐            │
│                                │  Health Worker   │            │
│                                │  (APScheduler)   │            │
│                                └──────────────────┘            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Purpose | Port | Technology |
|---------|---------|------|------------|
| **free-ai-selector-data-postgres-api** | Data layer - CRUD operations for AI models and prompt history | 8021 (host) / 8001 (internal) | FastAPI + SQLAlchemy 2.0 async |
| **free-ai-selector-business-api** | Business logic - prompt processing, model selection, AI provider integration | 8020 | FastAPI + httpx |
| **free-ai-selector-telegram-bot** | User interface for end users (Russian language) | - | Aiogram 3.13+ |
| **free-ai-selector-health-worker** | Background monitoring - hourly synthetic checks, stats updates | - | AsyncIO + APScheduler |
| **free-ai-selector-postgres** | PostgreSQL 16 database | 5432 | PostgreSQL 16 |

---

## 🚀 Quick Start

### Prerequisites

- Docker 24.0+
- Docker Compose 2.0+
- Git

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/free-ai-selector.git
cd free-ai-selector
```

### 2. Configure Environment

```bash
cp .env.example .env
```

**Need help getting API keys?** See detailed step-by-step guide: [API Keys Setup](docs/operations/api-keys.md)

Edit `.env` and set your API keys:

```bash
# Required: AI Provider API Keys (all 100% free, no credit card required)

# Google AI Studio - https://aistudio.google.com/apikey
# Free tier: 10 RPM, 250 RPD
GOOGLE_AI_STUDIO_API_KEY=your_google_ai_studio_key_here

# Groq - https://console.groq.com/keys
# Free tier: 20 RPM, 14,400 RPD, 1,800 tokens/sec
GROQ_API_KEY=your_groq_api_key_here

# Cerebras - https://cloud.cerebras.ai/
# Free tier: 1M tokens/day, 30 RPM, 2,500+ tokens/sec
CEREBRAS_API_KEY=your_cerebras_api_key_here

# SambaNova - https://cloud.sambanova.ai/
# Free tier: 20 RPM, 430 tokens/sec
SAMBANOVA_API_KEY=your_sambanova_api_key_here

# HuggingFace - https://huggingface.co/settings/tokens
# Free tier: Rate limited inference API
HUGGINGFACE_API_KEY=your_huggingface_token_here

# Cloudflare Workers AI - https://dash.cloudflare.com/
# Free tier: 10,000 Neurons/day
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here

# Required: Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Optional: Admin user IDs (comma-separated Telegram user IDs)
BOT_ADMIN_IDS=123456789,987654321
```

### 3. Start Services

```bash
make build  # Build all Docker images
make up     # Start services (access via localhost:8020/8021)
```

Wait ~30 seconds for services to initialize, then verify health:

```bash
make health
```

Expected output:
```
✅ PostgreSQL: Ready
✅ Data API (http://localhost:8021/health): Healthy
✅ Business API (http://localhost:8020/health): Healthy
```

Single `docker-compose.yml` is used for all environments. Differences are configured through `.env` values.

### 4. Initialize Database

```bash
make migrate  # Run database migrations
make seed     # Seed with initial AI models
```

### 5. Test the Platform

#### Option A: REST API

```bash
# 1. Simple prompt (automatic model selection)
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate a short poem about AI"}'

# 2. Prompt with system instructions
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List 3 benefits of AI",
    "system_prompt": "You are a helpful technical writer. Keep responses concise and factual."
  }'

# 3. Request JSON response format
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate a list of 3 programming languages with their primary use cases",
    "response_format": {"type": "json_object"}
  }'

# 4. Combined: System prompt + JSON format
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze the pros and cons of microservices architecture",
    "system_prompt": "You are a senior software architect. Provide structured analysis.",
    "response_format": {"type": "json_object"}
  }'

# Get model statistics
curl http://localhost:8020/api/v1/models/stats
```

**Note**:
- `system_prompt` is supported by OpenAI-compatible providers (Groq, Cerebras, SambaNova)
- `response_format: {"type": "json_object"}` requests structured JSON output
- The platform automatically selects the best available model based on reliability

#### Option B: Telegram Bot

1. Open Telegram and find your bot by token
2. Send `/start` to initialize
3. Send any text message to process it with the best AI model
4. Send `/stats` to see reliability statistics

---

## 📊 How It Works

### Reliability-Based Selection Algorithm

The platform calculates a **reliability score** for each AI model:

```python
reliability_score = (success_rate × 0.6) + (speed_score × 0.4)
```

Where:
- **success_rate**: Percentage of successful requests (0.0 - 1.0)
- **speed_score**: Normalized response time score (0.0 - 1.0, faster = higher)

### Dual Monitoring System

1. **Real-Time Metrics** (from actual user requests):
   - Success/failure tracking
   - Response time measurement
   - Error categorization

2. **Synthetic Monitoring** (hourly background checks):
   - Health Worker sends test prompts to all providers
   - Updates availability and baseline performance metrics
   - Detects provider outages before users encounter them

---

## 🔌 Free AI Providers

All 6 providers are **100% free with NO credit card required**:

| Provider | Model | Free Tier Limits | Speed | Credit Card |
|----------|-------|------------------|-------|-------------|
| **Google Gemini** | Gemini 2.5 Flash | 10 RPM, 250 RPD | Fast | ❌ Not Required |
| **Groq** | Llama 3.3 70B Versatile | 20 RPM, 14,400 RPD | 1,800 tokens/sec | ❌ Not Required |
| **Cerebras** | Llama 3.3 70B | 1M tokens/day, 30 RPM | 2,500+ tokens/sec | ❌ Not Required |
| **SambaNova** | Meta-Llama-3.3-70B-Instruct | 20 RPM | 430 tokens/sec | ❌ Not Required |
| **HuggingFace** | Meta-Llama-3-8B-Instruct | Rate limited | Moderate | ❌ Not Required |
| **Cloudflare** | Llama 3.3 70B FP8 Fast | 10,000 Neurons/day | Fast | ❌ Not Required |

### Getting API Keys

1. **Google AI Studio**: Visit https://aistudio.google.com/apikey - instant API key generation
2. **Groq**: Sign up at https://console.groq.com/keys - instant access to ultra-fast LPU
3. **Cerebras**: Register at https://cloud.cerebras.ai/ - world's fastest AI inference
4. **SambaNova**: Create account at https://cloud.sambanova.ai/ - access to Llama 405B
5. **HuggingFace**: Get token at https://huggingface.co/settings/tokens - free inference API
6. **Cloudflare**: Dashboard at https://dash.cloudflare.com/ - need Account ID + API Token

**Note**: All providers offer instant API key generation without payment information. Simply sign up with email and start using immediately.

---

## 🛠️ Development

### Available Commands

```bash
make help           # Show all available commands
make up             # Start services (ports 8020/8021)
make down           # Stop services
make logs           # View logs from all services
make logs-business  # View Business API logs only
make test           # Run all tests (≥75% coverage required)
make lint           # Run linters (ruff, mypy, bandit)
make format         # Format code with ruff
make migrate        # Run database migrations
make shell-business # Open shell in Business API container
make db-shell       # Open PostgreSQL shell
```

### Project Structure

```
free-ai-selector/
├── .aidd/                      # AIDD-MVP framework (git submodule)
├── services/
│   ├── free-ai-selector-data-postgres-api/    # Data layer service
│   │   ├── app/
│   │   │   ├── api/            # FastAPI routes
│   │   │   ├── domain/         # Domain models
│   │   │   ├── infrastructure/ # Database, repositories
│   │   │   └── main.py
│   │   ├── tests/              # Unit + integration tests
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── free-ai-selector-business-api/         # Business logic service
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── application/    # Use cases
│   │   │   ├── domain/
│   │   │   ├── infrastructure/ # HTTP clients, AI providers
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── free-ai-selector-telegram-bot/         # Telegram interface
│   │   └── ...
│   └── free-ai-selector-health-worker/        # Background monitoring
│       └── ...
├── shared/                     # Shared utilities (future)
├── docker-compose.yml          # Single config for all environments
├── Makefile                    # Development commands
└── README.md                   # This file
```

### Testing

Run tests with coverage reporting:

```bash
make test
```

Level 2 maturity requires **≥75% code coverage** for all services.

---

## 📖 API Documentation

### Interactive Docs (Swagger / ReDoc)

При запущенных сервисах:

| Сервис | Swagger UI | ReDoc |
|--------|------------|-------|
| Business API | http://localhost:8020/docs | http://localhost:8020/redoc |
| Data API | http://localhost:8021/docs | http://localhost:8021/redoc |

### Business API (port 8020)

Бизнес-логика, маршрутизация промптов и интеграция с AI-провайдерами.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/prompts/process` | Обработать промпт лучшей AI-моделью |
| `GET` | `/api/v1/models/stats` | Статистика надёжности всех моделей |
| `POST` | `/api/v1/providers/test` | Тестировать все AI-провайдеры |
| `GET` | `/health` | Health check (сервис + Data API) |
| `GET` | `/api` | Информация о сервисе |

**Основной endpoint** — `POST /api/v1/prompts/process`:

```bash
curl -X POST http://localhost:8020/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a poem about AI",
    "system_prompt": "You are a creative writer",
    "model_id": 3,
    "response_format": {"type": "json_object"}
  }'
```

Ответ включает telemetry: `attempts` (количество попыток) и `fallback_used` (был ли fallback).

При перегрузке возвращает **429** / **503** с заголовком `Retry-After` и структурированным `ErrorResponse`.

### Data API (port 8021 host / 8001 internal)

CRUD для AI-моделей и истории промптов. Внутренний сервис — не доступен извне.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/models` | Список AI-моделей (фильтры: `active_only`, `available_only`, `include_recent`) |
| `GET` | `/api/v1/models/{id}` | Модель по ID |
| `POST` | `/api/v1/models` | Создать модель |
| `PUT` | `/api/v1/models/{id}/stats` | Обновить статистику |
| `POST` | `/api/v1/models/{id}/increment-success` | +1 успех |
| `POST` | `/api/v1/models/{id}/increment-failure` | +1 ошибка |
| `PATCH` | `/api/v1/models/{id}/active` | Вкл/выкл модель |
| `PATCH` | `/api/v1/models/{id}/availability` | Cooldown при rate limit |
| `POST` | `/api/v1/history` | Создать запись истории |
| `GET` | `/api/v1/history` | Последние записи |
| `GET` | `/api/v1/history/user/{user_id}` | История пользователя |
| `GET` | `/api/v1/history/model/{model_id}` | История модели |
| `GET` | `/api/v1/history/{id}` | Запись по ID |
| `GET` | `/api/v1/history/statistics/period` | Агрегированная статистика за период |
| `GET` | `/health` | Health check (сервис + PostgreSQL) |

### Подробная документация

| Документ | Описание |
|----------|----------|
| [docs/api/business-api.md](docs/api/business-api.md) | Business API — полное описание endpoints, schemas, middleware, rate limiting |
| [docs/api/data-api.md](docs/api/data-api.md) | Data API — полное описание endpoints, schemas, query parameters |
| [docs/api/errors.md](docs/api/errors.md) | Коды ошибок, `ErrorResponse` (F025), error classification, troubleshooting |
| [docs/api/examples.md](docs/api/examples.md) | 16+ примеров curl и Python client для всех endpoints |

### Ключевые возможности API

- **Автоматический выбор модели** по reliability score с fallback при ошибках
- **Принудительный выбор модели** через `model_id` с fallback (F019)
- **System prompt** и **JSON response format** (F011-B)
- **Per-request telemetry**: `attempts`, `fallback_used` в ответе (F023)
- **Backpressure**: HTTP 429/503 с `Retry-After` и структурированным `ErrorResponse` (F025)
- **Circuit Breaker**: автоотключение нестабильных провайдеров (F024)
- **Recent metrics**: выбор модели по данным скользящего окна (F010)
- **Request tracing**: `X-Request-ID` / `X-Correlation-ID` headers

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow the project guidelines in `CLAUDE.md`
4. Ensure tests pass and coverage ≥75%
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [AIDD-MVP Generator](.aidd/) - AI-Driven Development framework for microservices
- Free AI providers (no credit card required):
  - [Google AI Studio](https://aistudio.google.com/) - Gemini models
  - [Groq](https://groq.com/) - Ultra-fast LPU inference
  - [Cerebras](https://cerebras.ai/) - Wafer-Scale Engine, world's fastest AI
  - [SambaNova](https://sambanova.ai/) - Llama 405B access
  - [HuggingFace](https://huggingface.co/) - Free inference API
  - [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) - Serverless GPU inference

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/free-ai-selector/issues)
- **API Keys Setup**: [API Keys Setup](docs/operations/api-keys.md) - Detailed guide for getting API keys
- **Documentation**: [CLAUDE.md](CLAUDE.md) - Project guidelines and architecture
- **Framework Guide**: [.aidd/CLAUDE.md](.aidd/CLAUDE.md) - AIDD-MVP workflow

---

**Maturity Level**: Level 2 (Development Ready) - Suitable for development teams of 2-5 developers preparing for beta launch.

For production deployment (Level 4+), see [.aidd/knowledge/architecture/](.aidd/knowledge/architecture/).
