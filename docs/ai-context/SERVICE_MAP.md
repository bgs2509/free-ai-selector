# Service Map for AI Code Generation

> Карта сервисов и компонентов Free AI Selector для Claude Code.

## Service Inventory

### 1. aimanager_business_api (Port 8000)

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
| AI Providers | `app/infrastructure/ai_providers/*.py` | 6 provider implementations |
| HTTP Client | `app/infrastructure/http_clients/data_api_client.py` | Data API client |

### 2. aimanager_data_postgres_api (Port 8001)

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

### 3. aimanager_telegram_bot

**Назначение:** Telegram интерфейс для пользователей

| Component | Path | Description |
|-----------|------|-------------|
| Main | `app/main.py` | Bot entry point |
| Handlers | `app/handlers/` | Message handlers |
| Keyboards | `app/keyboards/` | Inline keyboards |

### 4. aimanager_health_worker

**Назначение:** Почасовой синтетический мониторинг AI-моделей

| Component | Path | Description |
|-----------|------|-------------|
| Main | `app/main.py` | APScheduler worker |
| Health Check | `app/tasks/` | Scheduled health checks |

### 5. aimanager_nginx (Port 8000 external)

**Назначение:** Reverse proxy с оптимизированными таймаутами для AI

---

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant User as User/Telegram
    participant Nginx as Nginx :8000
    participant Business as Business API :8000
    participant Data as Data API :8001
    participant DB as PostgreSQL :5432
    participant AI as AI Provider

    User->>Nginx: POST /api/v1/prompts/process
    Nginx->>Business: Forward request

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

    Business-->>Nginx: PromptResponse
    Nginx-->>User: JSON response
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
| Nginx | Business API | HTTP | /* | Reverse proxy |

---

## AI Providers

| Provider | Class | Model | Rate Limits |
|----------|-------|-------|-------------|
| Google Gemini | `GoogleGeminiProvider` | Gemini 2.5 Flash | 10 RPM, 250 RPD |
| Groq | `GroqProvider` | Llama 3.3 70B | 20 RPM |
| Cerebras | `CerebrasProvider` | Llama 3.3 70B | 30 RPM, 1M tokens/day |
| SambaNova | `SambanovaProvider` | Llama 3.3 70B | 20 RPM |
| HuggingFace | `HuggingFaceProvider` | Llama 3 8B | Variable |
| Cloudflare | `CloudflareProvider` | Llama 3.3 70B FP8 | 10K neurons/day |

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
DATA_API_URL=http://aimanager_data_postgres_api:8001
GOOGLE_AI_STUDIO_API_KEY=xxx
GROQ_API_KEY=xxx
CEREBRAS_API_KEY=xxx
SAMBANOVA_API_KEY=xxx
HUGGINGFACE_API_KEY=xxx
CLOUDFLARE_ACCOUNT_ID=xxx
CLOUDFLARE_API_TOKEN=xxx
```

### Data API

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/aimanager
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aimanager
POSTGRES_USER=aimanager
POSTGRES_PASSWORD=xxx
```

### Telegram Bot

```bash
TELEGRAM_BOT_TOKEN=xxx
BUSINESS_API_URL=http://aimanager_business_api:8000
BOT_ADMIN_IDS=123456,789012
```

### Health Worker

```bash
DATA_API_URL=http://aimanager_data_postgres_api:8001
HEALTH_CHECK_INTERVAL=3600
SYNTHETIC_TEST_PROMPT="Hello! Please respond with 'OK'"
```

---

## Docker Network

All services communicate via Docker network `aimanager_network`:

```yaml
networks:
  aimanager_network:
    driver: bridge
```

**Internal DNS:**
- `aimanager_business_api:8000`
- `aimanager_data_postgres_api:8001`
- `postgres:5432`
