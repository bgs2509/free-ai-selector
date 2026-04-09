# Service Map for AI Code Generation

> Карта сервисов и компонентов Free AI Selector для Claude Code.

## Service Inventory

### 1. free-ai-selector-business-api (Port 8020)

**Назначение:** Выбор лучшей AI-модели и генерация ответов

| Component | Path | Description |
|-----------|------|-------------|
| Main app | `app/main.py` | FastAPI app, middleware, lifespan |
| Prompts API | `app/api/v1/prompts.py` | POST /prompts/process |
| Models API | `app/api/v1/models.py` | GET /models/stats |
| Providers API | `app/api/v1/providers.py` | POST /providers/test |
| ProcessPrompt UC | `app/application/use_cases/process_prompt.py` | Core business logic |
| TestProviders UC | `app/application/use_cases/test_all_providers.py` | Provider testing |
| Domain Models | `app/domain/models.py` | PromptRequest, PromptResponse, AIModelInfo |
| AI Providers | `app/infrastructure/ai_providers/*.py` | 14 provider implementations |
| Provider Registry | `app/infrastructure/ai_providers/registry.py` | SSOT for provider mapping, tags |
| HTTP Client | `app/infrastructure/http_clients/data_api_client.py` | Data API client |

### 2. free-ai-selector-data-postgres-api (Port 8021 host / 8001 internal)

**Назначение:** CRUD операции для AI-моделей и истории промптов

| Component | Path | Description |
|-----------|------|-------------|
| Main app | `app/main.py` | FastAPI app |
| Models API | `app/api/v1/models.py` | CRUD for AI models |
| History API | `app/api/v1/history.py` | Prompt history endpoints |
| Schemas | `app/api/v1/schemas.py` | Pydantic request/response models |
| Domain Models | `app/domain/models.py` | AIModel, PromptHistory (with business logic) |
| Repository | `app/infrastructure/repositories/ai_model_repository.py` | DB operations |
| DB Models | `app/infrastructure/database/models.py` | SQLAlchemy ORM models |
| Seed | `app/infrastructure/database/seed.py` | Initial AI models data |
| Migrations | `alembic/versions/` | Database migrations |

### 3. free-ai-selector-telegram-bot

**Назначение:** Telegram интерфейс для пользователей

| Component | Path | Description |
|-----------|------|-------------|
| Main | `app/main.py` | Bot entry point |
| Handlers | `app/handlers/` | Message handlers |
| Keyboards | `app/keyboards/` | Inline keyboards |

### 4. free-ai-selector-health-worker

**Назначение:** Почасовой синтетический мониторинг AI-моделей

| Component | Path | Description |
|-----------|------|-------------|
| Main | `app/main.py` | APScheduler worker |
| Health Check | `app/tasks/` | Scheduled health checks |

---

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant User as User/Telegram
    participant Proxy as nginx-proxy (VPS)
    participant Business as Business API :8020
    participant Data as Data API :8021
    participant DB as PostgreSQL :5432
    participant AI as AI Provider

    User->>Proxy: POST /free-ai-selector/api/v1/prompts/process
    Proxy->>Business: Forward request

    Note over Business: ProcessPromptUseCase.execute()

    Business->>Data: GET /api/v1/models?active_only=true
    Data->>DB: SELECT * FROM ai_models WHERE is_active=true
    DB-->>Data: models[]
    Data-->>Business: models[]

    Note over Business: Select best model by reliability_score

    Business->>AI: generate(prompt)
    AI-->>Business: response

    par Update Statistics
        Business->>Data: POST /models/{id}/increment-success
        Data->>DB: UPDATE ai_models SET success_count=success_count+1
    and Record History
        Business->>Data: POST /api/v1/history
        Data->>DB: INSERT INTO prompt_history
    end

    Business-->>Proxy: PromptResponse
    Proxy-->>User: JSON response
```

---

## Inter-Service Communication

| From | To | Protocol | Endpoint | Purpose |
|------|-----|----------|----------|---------|
| Business API | Data API | HTTP | GET /api/v1/models | Fetch AI models |
| Business API | Data API | HTTP | POST /models/{id}/increment-success | Update success count |
| Business API | Data API | HTTP | POST /models/{id}/increment-failure | Update failure count |
| Business API | Data API | HTTP | POST /api/v1/history | Record prompt history |
| Business API | AI Providers | HTTPS | Various | Generate AI responses |
| Telegram Bot | Business API | HTTP | POST /api/v1/prompts/process | Process user prompts |
| Health Worker | Data API | HTTP | Various | Update health stats |
| nginx-proxy (VPS) | Business API | HTTP | /* | Reverse proxy (to localhost:8020) |

---

## AI Providers

**Существующие провайдеры (7 шт.)**:

| Provider | Class | Model | Tags | Rate Limits |
|----------|-------|-------|------|-------------|
| Groq | `GroqProvider` | Llama 3.3 70B | fast, json, code, tools | 20 RPM |
| Cerebras | `CerebrasProvider` | Llama 3.1 8B | fast, json, lightweight | 30 RPM, 1M tokens/day |
| SambaNova | `SambanovaProvider` | Llama 3.3 70B | — | 20 RPM |
| HuggingFace | `HuggingFaceProvider` | Llama 3 8B | lightweight | Variable |
| Cloudflare | `CloudflareProvider` | Llama 3.3 70B FP8 | json, code | 10K neurons/day |
| CloudflareGemma3 | `CloudflareGemma3Provider` | Gemma 3 12B IT | fast, json, code, russian | 10K neurons/day |
| CloudflareQwen3 | `CloudflareQwen3Provider` | Qwen3 30B A3B FP8 | fast, json, code, russian | 10K neurons/day |

**F003 провайдеры (7 шт.)**:

| Provider | Class | Model | Tags | Rate Limits |
|----------|-------|-------|------|-------------|
| DeepSeek | `DeepSeekProvider` | DeepSeek Chat | — | 60 RPM |
| OpenRouter | `OpenRouterProvider` | DeepSeek R1 | code, reasoning, russian, tools | 20 RPM |
| GitHub Models | `GitHubModelsProvider` | GPT-4o Mini | fast, json, russian, tools | 15 RPM, 150 RPD |
| Fireworks | `FireworksProvider` | GPT-OSS-20B | json, code | $1 free credits |
| Hyperbolic | `HyperbolicProvider` | Llama 3.3 70B | — | Free tier |
| Novita | `NovitaProvider` | Llama 3.1 8B | json, lightweight | Free tier |
| Scaleway | `ScalewayProvider` | Llama 3.1 70B | — | Free tier |

---

## Database Schema

### Table: ai_models

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | VARCHAR(255) | Model name (unique) |
| provider | VARCHAR(100) | Provider name |
| api_endpoint | VARCHAR(500) | API endpoint URL |
| success_count | INTEGER | Total successful requests |
| failure_count | INTEGER | Total failed requests |
| total_response_time | NUMERIC(10,3) | Sum of response times |
| request_count | INTEGER | Total requests |
| last_checked | TIMESTAMP | Last health check |
| is_active | BOOLEAN | Model availability |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

**Indexes:** `ix_ai_models_name` (unique), `ix_ai_models_provider`, `ix_ai_models_is_active`

### Table: prompt_history

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | VARCHAR(255) | User identifier |
| prompt_text | TEXT | User's prompt |
| selected_model_id | INTEGER | Selected AI model |
| response_text | TEXT | AI response |
| response_time | NUMERIC(10,3) | Response time (seconds) |
| success | BOOLEAN | Success flag |
| error_message | TEXT | Error details |
| created_at | TIMESTAMP | Creation time |

**Indexes:** `ix_prompt_history_user_id`, `ix_prompt_history_selected_model_id`, `ix_prompt_history_success`, `ix_prompt_history_created_at`

---

## Environment Variables by Service

### Business API

```bash
DATA_API_URL=http://localhost:8021
# Существующие провайдеры (5)
GROQ_API_KEY=xxx
CEREBRAS_API_KEY=xxx
SAMBANOVA_API_KEY=xxx
HUGGINGFACE_API_KEY=xxx
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_API_TOKEN=xxx
# Новые провайдеры F003 (7)
DEEPSEEK_API_KEY=xxx
OPENROUTER_API_KEY=xxx
GITHUB_TOKEN=xxx
FIREWORKS_API_KEY=xxx
HYPERBOLIC_API_KEY=xxx
NOVITA_API_KEY=xxx
SCALEWAY_API_KEY=xxx
```

### Data API

```bash
DATABASE_URL=postgresql+asyncpg://free_ai_selector_user:pass@postgres:5432/free_ai_selector_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=free_ai_selector_db
POSTGRES_USER=free_ai_selector_user
POSTGRES_PASSWORD=xxx
```

### Telegram Bot

```bash
TELEGRAM_BOT_TOKEN=xxx
BUSINESS_API_URL=http://localhost:8020
BOT_ADMIN_IDS=123456,789012
```

### Health Worker

```bash
DATA_API_URL=http://localhost:8021
HEALTH_CHECK_INTERVAL=3600
SYNTHETIC_TEST_PROMPT="Hello! Please respond with 'OK'"
```

---

## Docker Network

Services use a mix of host and bridge networking:

- **Business API, Telegram Bot, Health Worker**: `network_mode: host` (доступны на localhost)
- **Data API, PostgreSQL**: bridge network (`free-ai-selector-network`)

```yaml
networks:
  free-ai-selector-network:
    driver: bridge
    # Сеть для Data API и PostgreSQL
```

**Host-accessible ports:**
- `localhost:8020` — Business API (host network)
- `localhost:8021` — Data API (bridge, port mapping 8021:8001)
- `localhost:5432` — PostgreSQL (bridge, port mapping)
