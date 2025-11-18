# Prompt for AI Manager Platform Generation

> **Use this prompt with your AI assistant (Claude, ChatGPT) to generate the complete codebase**

---

I want to use the framework in `.ai-framework/` to create an application.

## INSTRUCTIONS FOR AI:
1. First, read `.ai-framework/AGENTS.md` to understand the framework
2. Then, validate my prompt using `.ai-framework/docs/guides/prompt-validation-guide.md`
3. Ask me for any missing information before generating code
4. Only after validation passes, generate code following framework rules

---

## MY PROJECT:

### What I'm building:
**AI Manager Platform** — intelligent platform for processing prompts with automatic selection of the best AI model based on real-time reliability ratings.

**Target audience:**
- End users via Telegram bot
- Developers via REST API for integration into their applications

### Problem it solves:
Free AI APIs are unstable (rate limits, downtime, slow responses). Users and developers need a reliable system that:
1. **Automatically selects** the best available model in real-time
2. **Adapts** to changes (model down → switches to another)
3. **Provides unified API** for access to multiple AI models
4. **Monitors health** of all models and maintains up-to-date ratings

### Key features:

#### 1. **Multi-channel access**
- **Telegram bot** - regular users send prompts via Telegram
- **REST API** - external services (web/mobile apps) make HTTP requests
- **Unified business logic** - one endpoint for all clients

#### 2. **Smart AI model selection**
- Automatic selection of model with highest `reliability_score`
- **Real-time rating update** - every real request affects the rating:
  - Measures `response_time_ms`
  - Records errors (`success`/`error`)
  - Recalculates `reliability_score` using formula
- Automatic **fallback** on model unavailability (switches to next best)

#### 3. **Dual health monitoring**
- **Real-time metrics** - from real user requests (every request updates rating)
- **Synthetic monitoring** - separate background worker polls all models every hour
- **Combined rating:**
  ```
  reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

  where:
    success_rate = (successful_requests / total_requests) × 100
    speed_score = max(0, 100 - (avg_response_time_ms / 50))
  ```

#### 4. **Model management**
- Support for 10-20 free AI models (HuggingFace, Replicate, Together.ai, etc.)
- Dynamic enable/disable models (`is_active`)
- History of all requests for analytics

#### 5. **Public REST API**
- OpenAPI documentation (Swagger UI)
- API keys for authentication (`X-API-Key` header)
- Rate limiting (basic: 10 requests/minute per IP)
- CORS for web clients

### Target Maturity Level:
**Level 2: Development Ready** (~10-12 minutes)

**Justification:**
- Team of 2-5 developers
- Need observability for debugging (JSON logging, request ID, health checks)
- Preparing for beta launch
- Integration tests required (≥75% coverage)

### How complex should it be:
**Development version (Level 2)**

### Optional Modules (explicitly stated):
- ✅ **Telegram Bot** (Aiogram 3.x) — user interface for end users
- ✅ **Background Worker** (AsyncIO + APScheduler) — synthetic monitoring every hour
- ❌ **MongoDB** — not needed (PostgreSQL only)
- ❌ **Redis** — not needed for Level 2
- ❌ **RabbitMQ** — not needed (using HTTP communication)

### Additional services needed:
- **Telegram bot** (Aiogram) - for user interaction
- **Background worker** (AsyncIO) - for periodic model polling (separate service!)
- **MongoDB:** NO (not needed - using PostgreSQL only)
- **Redis:** NO (not needed for Level 2)
- **RabbitMQ:** NO (not needed - using HTTP communication)

### Open Questions & Risks:
1. **AI API Instability** - Free AI providers may have rate limits or downtime. Mitigation: use mock responses for testing, implement robust fallback mechanism.
2. **Mock Data Needed** - Real API keys may not be available initially. Mitigation: create realistic mock responses simulating different latencies and error rates.
3. **Formula Tuning** - The rating formula (`reliability_score = success_rate × 0.6 + speed_score × 0.4`) may need adjustment based on real-world usage patterns.

---

## ARCHITECTURAL REQUIREMENTS

### Microservices (4 services):

#### 1. `aimanager_telegram_bot` (Aiogram 3.x)
**Purpose:** Telegram interface for users
**Port:** N/A (long polling)

**Functions:**
- Commands: `/start`, `/help`, `/stats` (model statistics)
- Processing text prompts from users
- Sending prompt to `aimanager_business_api` via HTTP
- Displaying response to user in Russian

**Example commands:**
```
/start → "Добро пожаловать! Отправьте мне любой промпт, и я обработаю его через лучшую доступную AI модель."

/stats → "📊 Статистика AI моделей:
  1. mistral-7b: 95.5 ⭐ (1234ms)
  2. llama-3-8b: 92.3 ⭐ (1456ms)
  ..."

User: "Объясни квантовые компьютеры"
Bot: "🤖 Обрабатываю через модель mistral-7b...
      [AI Response]

      Модель: mistral-7b
      Время: 1.2 сек"
```

---

#### 2. `aimanager_business_api` (FastAPI - Business Service)
**Purpose:** Business logic for prompt processing
**Port:** 8000

**Functions:**

##### A. REST API Endpoints:
```python
POST   /api/v1/prompts              # Process prompt
GET    /api/v1/models                # List models with ratings
GET    /api/v1/models/{id}/stats     # Statistics for specific model
GET    /health                       # Health check
GET    /ready                        # Readiness check
```

##### B. Prompt processing business logic:

**Algorithm:**
1. Get model with highest `reliability_score` from Data API (`GET /models/best`)
2. Send prompt to selected AI model + measure metrics (`response_time_ms`, `success`)
3. **If error** → fallback to next best model (`GET /models/best?exclude={previous_id}`)
4. **⭐ Real-time rating:** update model statistics via Data API (`POST /models/{id}/stats`)
5. Save request history (`POST /prompts/history`)
6. Return response to client

**Structure:**
```
services/aimanager_business_api/
├── src/
│   ├── api/v1/
│   │   ├── prompts_router.py      # POST /api/v1/prompts
│   │   └── models_router.py       # GET /api/v1/models
│   ├── application/
│   │   └── use_cases/
│   │       └── process_prompt.py  # Main business logic
│   ├── domain/
│   │   └── entities/
│   │       ├── ai_model.py        # Domain model
│   │       └── prompt.py
│   ├── infrastructure/
│   │   ├── http_clients/
│   │   │   └── data_api_client.py  # HTTP client to Data API
│   │   └── ai_providers/
│   │       ├── huggingface.py      # Integration with HuggingFace API
│   │       ├── replicate.py        # Integration with Replicate API
│   │       └── together_ai.py      # Integration with Together.ai API
│   ├── middleware/
│   │   ├── request_id.py           # Request ID tracking (Level 2)
│   │   └── error_handler.py        # Global error handling
│   └── core/
│       ├── config.py               # Settings
│       └── logging.py              # JSON logging
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
└── requirements.txt
```

**⚠️ IMPORTANT:** HTTP-ONLY data access — NEVER access PostgreSQL directly, only via Data API!

##### C. Authentication and security:
- **API Key validation:** simple header `X-API-Key` (for external clients)
- **Rate limiting:** `slowapi` - 10 requests/minute per IP
- **CORS:** for web clients
- **Security headers:** basic (CORS, Content-Type)

---

#### 3. `aimanager_health_worker` (AsyncIO Background Worker)
**Purpose:** Periodic polling of all AI models
**Port:** N/A (background process)

**Functions:**

##### A. Periodic health check (every hour):
**Algorithm:**
1. Get all active models from Data API (`GET /models?is_active=true`)
2. For each model:
   - Send test prompt: `"Say 'OK' if you are working."`
   - Measure `response_time_ms`
   - Record `success` (True/False)
3. Update statistics for each model via Data API (`POST /models/{id}/stats`)
4. Log results

**Technologies:**
- **APScheduler** (AsyncIOScheduler) - for periodic execution
- **AsyncIO** - for parallel model polling
- **httpx** - for HTTP requests to Data API and AI providers

**Structure:**
```
services/aimanager_health_worker/
├── src/
│   ├── workers/
│   │   └── health_checker.py       # Main polling logic
│   ├── infrastructure/
│   │   ├── http_clients/
│   │   │   └── data_api_client.py  # HTTP client to Data API
│   │   └── ai_providers/           # Same providers as in API
│   │       ├── huggingface.py
│   │       ├── replicate.py
│   │       └── together_ai.py
│   ├── core/
│   │   ├── config.py
│   │   └── logging.py
│   └── main.py                      # Entry point
├── tests/
├── Dockerfile
└── requirements.txt
```

**main.py (entry point):**
```python
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from workers.health_checker import AIHealthChecker

async def main():
    logger.info("Starting AI Health Worker")

    checker = AIHealthChecker(data_api_url="http://aimanager_data_postgres_api:8001")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        checker.check_all_models,
        trigger='interval',
        hours=1,
        id='health_check'
    )
    scheduler.start()

    # Run initial check immediately
    await checker.check_all_models()

    # Keep running forever
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
```

**⚠️ IMPORTANT:** Worker also uses HTTP-ONLY access to Data API!

---

#### 4. `aimanager_data_postgres_api` (FastAPI Data Service)
**Purpose:** Only service with direct access to PostgreSQL
**Port:** 8001

**Functions:**

##### A. CRUD for AI Models:
```python
GET    /models                         # All models
GET    /models?is_active=true          # Only active models
GET    /models/best                    # Model with highest rating
GET    /models/best?exclude={uuid}     # Best model excluding specified
GET    /models/{id}                    # Specific model
POST   /models                         # Add new model
PATCH  /models/{id}                    # Update model (is_active, etc.)
POST   /models/{id}/stats              # ⭐ Update statistics + recalculate rating
```

##### B. CRUD for Prompt History:
```python
GET    /prompts/history                # Request history (pagination)
GET    /prompts/history?user_id={id}   # History for specific user
POST   /prompts/history                # Save request
```

##### C. ⭐ Rating recalculation logic:

**Endpoint:** `POST /models/{id}/stats`

**Request Body:**
```json
{
  "response_time_ms": 1234,
  "success": true
}
```

**Logic:**
```python
# 1. Update counters
model.total_requests += 1
if stats.success:
    model.successful_requests += 1
else:
    model.failed_requests += 1

# 2. Update avg response time (rolling average)
old_total = model.total_requests - 1
model.avg_response_time_ms = (
    (model.avg_response_time_ms * old_total + stats.response_time_ms)
    / model.total_requests
)

# 3. Recalculate reliability score
success_rate = (model.successful_requests / model.total_requests) * 100

# Speed score: faster = better (max 100 points)
# < 500ms → 100 points, > 5000ms → 0 points
speed_score = max(0, 100 - (model.avg_response_time_ms / 50))

# Final score: 60% reliability + 40% speed
model.reliability_score = (success_rate * 0.6) + (speed_score * 0.4)

# 4. Update timestamp
model.last_check_at = datetime.utcnow()

await db.commit()
```

**Structure:**
```
services/aimanager_data_postgres_api/
├── src/
│   ├── api/v1/
│   │   ├── models_router.py        # Models CRUD
│   │   └── prompts_router.py       # Prompt history CRUD
│   ├── models/
│   │   ├── ai_model.py             # SQLAlchemy model
│   │   └── prompt_history.py       # SQLAlchemy model
│   ├── repositories/
│   │   ├── model_repository.py     # Database queries
│   │   └── prompt_repository.py
│   ├── core/
│   │   ├── database.py             # AsyncSession, engine
│   │   ├── config.py
│   │   └── logging.py
│   └── main.py
├── alembic/
│   └── versions/
│       └── 001_create_tables.py    # Initial migration
├── tests/
├── Dockerfile
└── requirements.txt
```

---

### PostgreSQL Database:

#### Table 1: `ai_models`
```sql
CREATE TABLE ai_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,              -- "mistral-7b", "llama-3-8b"
    provider VARCHAR(100) NOT NULL,                 -- "HuggingFace", "Replicate"
    endpoint TEXT NOT NULL,                         -- API endpoint URL
    api_key_encrypted TEXT,                         -- Encrypted API key (or NULL for public)

    -- Performance metrics
    reliability_score DECIMAL(5,2) DEFAULT 100.0,   -- 0-100 (calculated)
    avg_response_time_ms INTEGER DEFAULT 0,         -- Average response time
    error_rate_percent DECIMAL(5,2) DEFAULT 0.0,    -- (failed / total) * 100

    -- Request counters
    total_requests BIGINT DEFAULT 0,
    successful_requests BIGINT DEFAULT 0,
    failed_requests BIGINT DEFAULT 0,

    -- Status and metadata
    is_active BOOLEAN DEFAULT true,                 -- Model enabled/disabled
    last_check_at TIMESTAMP,                        -- Last health check
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast best model lookup
CREATE INDEX idx_reliability_score ON ai_models(reliability_score DESC, is_active) WHERE is_active = true;
CREATE INDEX idx_active_models ON ai_models(is_active, reliability_score DESC);
```

**Seed Data (3-5 models for testing):**
```sql
INSERT INTO ai_models (name, provider, endpoint, is_active) VALUES
  ('mistral-7b', 'HuggingFace', 'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2', true),
  ('llama-3-8b', 'Together.ai', 'https://api.together.xyz/v1/chat/completions', true),
  ('llama-2-7b', 'Replicate', 'https://api.replicate.com/v1/predictions', true);
```

---

#### Table 2: `prompt_history`
```sql
CREATE TABLE prompt_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- User
    user_telegram_id BIGINT,                        -- Telegram user ID (NULL for API users)
    username VARCHAR(100),                          -- Telegram username or API client name

    -- Prompt and response
    prompt_text TEXT NOT NULL,
    response_text TEXT,

    -- AI model
    ai_model_id UUID REFERENCES ai_models(id),
    processing_duration_ms INTEGER,

    -- Execution status
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'error', 'timeout')),
    error_message TEXT,                             -- NULL if success

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for analytics
CREATE INDEX idx_user_history ON prompt_history(user_telegram_id, created_at DESC);
CREATE INDEX idx_model_usage ON prompt_history(ai_model_id, created_at DESC);
CREATE INDEX idx_status ON prompt_history(status, created_at DESC);
```

---

## TECHNICAL REQUIREMENTS

### Technology Stack:
- **Python:** 3.12+
- **FastAPI:** 0.115+
- **Aiogram:** 3.13+
- **PostgreSQL:** 16+
- **SQLAlchemy:** 2.0+ (async)
- **Alembic:** migrations
- **APScheduler:** 3.10+ (for Worker)
- **httpx:** async HTTP client
- **pydantic:** 2.0+ (validation)
- **python-json-logger:** structured logging
- **slowapi:** rate limiting
- **Docker & Docker Compose**

### AI Provider Integrations:

**HuggingFace Inference API:**
```python
async def call_huggingface(model_name: str, prompt: str, api_key: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api-inference.huggingface.co/models/{model_name}",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": prompt},
            timeout=30.0
        )
        return response.json()[0]["generated_text"]
```

**Together.ai API:**
```python
async def call_together_ai(model_name: str, prompt: str, api_key: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return response.json()["choices"][0]["message"]["content"]
```

**Replicate API:**
```python
async def call_replicate(model_name: str, prompt: str, api_key: str) -> str:
    # Simplified - real Replicate requires prediction creation + polling
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.replicate.com/v1/predictions",
            headers={"Authorization": f"Token {api_key}"},
            json={"version": model_name, "input": {"prompt": prompt}}
        )
        return response.json()["output"]
```

**⚠️ Mocks:** If no real API keys available, create mock responses for testing.

---

### Languages and Style:
- **UI (Telegram bot):** Russian language
- **API Documentation (Swagger):** English
- **Code, comments, docstrings:** English
- **Logs:** JSON format, English

**Log example:**
```json
{
  "timestamp": "2025-01-17T10:30:45Z",
  "level": "INFO",
  "service": "aimanager_business_api",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Prompt processed successfully",
  "user_id": "telegram_123456",
  "model_used": "mistral-7b",
  "processing_time_ms": 1234
}
```

---

### Quality Requirements:

#### Type Safety:
- **Full type hints** (mypy strict mode)
- No `Any` types without justification
- Pydantic models for all DTOs

#### Testing:
- **Coverage:** ≥75% (Level 2 requirement)
- **Unit tests:** domain, application layers
- **Integration tests:** API endpoints with testcontainers
- **Mocking:** external AI APIs in tests

#### Code Quality:
- **Linting:** Ruff (modern replacement for flake8 + black)
- **Security:** Bandit scan
- **Pre-commit hooks** (optional)

#### Observability (Level 2):
- ✅ **Structured logging** (JSON format via python-json-logger)
- ✅ **Request ID tracking** (middleware for log correlation)
- ✅ **Health check endpoints** (`/health`, `/ready`)
- ✅ **OpenAPI documentation** (Swagger UI auto-generated)

---

## DOCKER COMPOSE CONFIGURATION

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    container_name: ai_manager_postgres
    environment:
      POSTGRES_DB: ai_manager_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Data Service (PostgreSQL API)
  aimanager_data_postgres_api:
    build: ./services/aimanager_data_postgres_api
    container_name: aimanager_data_postgres_api
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/ai_manager_db
      LOG_LEVEL: INFO
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Business API
  aimanager_business_api:
    build: ./services/aimanager_business_api
    container_name: aimanager_business_api
    ports:
      - "8000:8000"
    environment:
      DATA_API_URL: http://aimanager_data_postgres_api:8001
      GOOGLE_AI_STUDIO_API_KEY: ${GOOGLE_AI_STUDIO_API_KEY:-mock}
      GROQ_API_KEY: ${GROQ_API_KEY:-mock}
      CEREBRAS_API_KEY: ${CEREBRAS_API_KEY:-mock}
      SAMBANOVA_API_KEY: ${SAMBANOVA_API_KEY:-mock}
      HUGGINGFACE_API_KEY: ${HUGGINGFACE_API_KEY:-mock}
      CLOUDFLARE_ACCOUNT_ID: ${CLOUDFLARE_ACCOUNT_ID:-mock}
      CLOUDFLARE_API_TOKEN: ${CLOUDFLARE_API_TOKEN:-mock}
      API_KEY: ${API_KEY:-default-api-key-change-me}
      LOG_LEVEL: INFO
    depends_on:
      aimanager_data_postgres_api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Health Worker (Background)
  aimanager_health_worker:
    build: ./services/aimanager_health_worker
    container_name: aimanager_health_worker
    environment:
      DATA_API_URL: http://aimanager_data_postgres_api:8001
      GOOGLE_AI_STUDIO_API_KEY: ${GOOGLE_AI_STUDIO_API_KEY:-mock}
      GROQ_API_KEY: ${GROQ_API_KEY:-mock}
      CEREBRAS_API_KEY: ${CEREBRAS_API_KEY:-mock}
      SAMBANOVA_API_KEY: ${SAMBANOVA_API_KEY:-mock}
      HUGGINGFACE_API_KEY: ${HUGGINGFACE_API_KEY:-mock}
      CLOUDFLARE_ACCOUNT_ID: ${CLOUDFLARE_ACCOUNT_ID:-mock}
      CLOUDFLARE_API_TOKEN: ${CLOUDFLARE_API_TOKEN:-mock}
      LOG_LEVEL: INFO
    depends_on:
      aimanager_data_postgres_api:
        condition: service_healthy
    restart: unless-stopped

  # Telegram Bot
  aimanager_telegram_bot:
    build: ./services/aimanager_telegram_bot
    container_name: aimanager_telegram_bot
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      AI_MANAGER_API_URL: http://aimanager_business_api:8000
      LOG_LEVEL: INFO
    depends_on:
      aimanager_business_api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
```

**`.env.example`:**
```env
# AI Provider API Keys (6 verified free-tier providers - NO credit card required)
GOOGLE_AI_STUDIO_API_KEY=your_google_ai_studio_key_here
GROQ_API_KEY=your_groq_api_key_here
CEREBRAS_API_KEY=your_cerebras_api_key_here
SAMBANOVA_API_KEY=your_sambanova_api_key_here
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxx
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# API Security
API_KEY=your-secret-api-key-change-me

# Database (auto-configured in docker-compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/ai_manager_db
```

---

## SCOPE BOUNDARIES

### ✅ In scope:
- Automatic AI model selection by rating
- Real-time rating update (every request affects rating)
- Synthetic monitoring (separate worker polls models every hour)
- Telegram interface (Russian language)
- Public REST API (English documentation)
- API keys (simple validation via header)
- Rate limiting (basic - 10 req/min per IP)
- History of all requests
- Support for 10-20 models (start with 3-5)
- CORS for web clients
- Fallback mechanism (automatic switch to next model)

### ❌ Out of scope:
- Payments and billing
- OAuth 2.0 (only API keys)
- RBAC (roles and permissions)
- Web interface (only API + Telegram)
- Multi-tenancy
- ELK stack, Prometheus, Grafana (Level 3+)
- Kubernetes deployment (only Docker Compose)
- CI/CD pipelines (Level 4)

---

## EXPECTED DELIVERABLES

### 1. Infrastructure:
- ✅ `docker-compose.yml` (complete configuration for 5 services)
- ✅ `.env.example` (environment variables template)
- ✅ `Makefile` (development commands)

### 2. Microservices (4 services):
```
services/
├── aimanager_telegram_bot/           # Telegram Bot (Aiogram)
├── aimanager_business_api/            # Business API (FastAPI)
├── aimanager_health_worker/          # Background Worker (AsyncIO)
└── aimanager_data_postgres_api/      # Data Service (FastAPI)
```

### 3. Database:
- ✅ Alembic migrations (`001_create_tables.py`)
- ✅ Seed data (3-5 AI models for testing)

### 4. Tests:
- ✅ Unit tests (domain, application layers)
- ✅ Integration tests (API endpoints with testcontainers)
- ✅ Coverage ≥75%

### 5. Documentation:
- ✅ `README.md` (Quick Start, Architecture Overview)
- ✅ OpenAPI spec (auto-generated Swagger UI)
- ✅ Request examples (curl, Python requests)

---

## ACCEPTANCE CRITERIA

### Infrastructure:
1. ✅ `docker-compose up` → all 5 services start
2. ✅ All services healthy (`docker-compose ps` shows "healthy")
3. ✅ PostgreSQL migrations applied automatically

### Telegram Bot:
4. ✅ `/start` → welcome message (Russian)
5. ✅ User sends prompt → bot returns AI response
6. ✅ `/stats` → shows model statistics

### REST API:
7. ✅ Swagger UI available: `http://localhost:8000/docs`
8. ✅ `curl -X POST http://localhost:8000/api/v1/prompts` (with API key) → success
9. ✅ `GET /api/v1/models` → list of models with ratings
10. ✅ CORS works (preflight requests pass)

### Background Worker:
11. ✅ Worker starts without errors
12. ✅ Initial health check runs immediately after start
13. ✅ Scheduled health checks every hour (verify in logs)

### Smart AI Selection:
14. ✅ Model with highest rating selected automatically
15. ✅ Fallback works (if model unavailable → next best)
16. ✅ Real-time rating updates after each request

### Data Persistence:
17. ✅ Prompt history saved in PostgreSQL
18. ✅ Model statistics updated correctly
19. ✅ `reliability_score` calculated using formula

### Quality:
20. ✅ All tests pass: `pytest --cov=src`
21. ✅ Coverage ≥75%
22. ✅ Linting pass: `ruff check .`
23. ✅ Type checking pass: `mypy .`
24. ✅ Security scan pass: `bandit -r .`

---

## USAGE EXAMPLES

### Example 1: Telegram Bot

```
User: /start

Bot: Добро пожаловать в AI Manager Platform! 🤖

Я обрабатываю ваши промпты через лучшую доступную AI модель.
Просто отправьте мне текст, и я дам ответ.

Команды:
/stats - статистика моделей
/help - справка

---

User: Объясни квантовые компьютеры простыми словами

Bot: 🤖 Обрабатываю через модель "mistral-7b"...

Квантовые компьютеры — это компьютеры, которые используют принципы квантовой механики...
[full AI response]

✅ Модель: mistral-7b
⏱ Время обработки: 1.2 сек
⭐ Рейтинг модели: 95.5

---

User: /stats

Bot: 📊 Статистика AI моделей:

1. mistral-7b (HuggingFace)
   ⭐ Рейтинг: 95.5
   ⏱ Ср. время: 1234 мс
   ✅ Успешно: 98.5%

2. llama-3-8b (Together.ai)
   ⭐ Рейтинг: 92.3
   ⏱ Ср. время: 1456 мс
   ✅ Успешно: 96.2%

3. llama-2-7b (Replicate)
   ⭐ Рейтинг: 88.7
   ⏱ Ср. время: 1678 мс
   ✅ Успешно: 94.1%

Обновлено: 2025-01-17 10:30 UTC
```

---

### Example 2: REST API

**Send prompt:**
```bash
curl -X POST http://localhost:8000/api/v1/prompts \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "prompt": "Explain quantum computing in simple terms",
    "user_id": "api_client_123",
    "max_tokens": 500
  }'

# Response (200 OK):
{
  "response": "Quantum computing is a type of computing that uses quantum mechanics...",
  "model_used": {
    "id": "uuid-1",
    "name": "mistral-7b",
    "provider": "HuggingFace",
    "reliability_score": 95.5
  },
  "processing_time_ms": 1234,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Get model list:**
```bash
curl http://localhost:8000/api/v1/models

# Response (200 OK):
[
  {
    "id": "uuid-1",
    "name": "mistral-7b",
    "provider": "HuggingFace",
    "reliability_score": 95.5,
    "avg_response_time_ms": 1234,
    "error_rate_percent": 1.5,
    "total_requests": 1543,
    "is_active": true,
    "last_check_at": "2025-01-17T10:30:00Z"
  },
  {
    "id": "uuid-2",
    "name": "llama-3-8b",
    "provider": "Together.ai",
    "reliability_score": 92.3,
    "avg_response_time_ms": 1456,
    "error_rate_percent": 3.8,
    "total_requests": 987,
    "is_active": true,
    "last_check_at": "2025-01-17T10:30:00Z"
  }
]
```

**Model statistics:**
```bash
curl http://localhost:8000/api/v1/models/uuid-1/stats

# Response (200 OK):
{
  "model_id": "uuid-1",
  "name": "mistral-7b",
  "total_requests": 1543,
  "successful_requests": 1521,
  "failed_requests": 22,
  "success_rate": 98.5,
  "avg_response_time_ms": 1234,
  "reliability_score": 95.5,
  "last_24h_requests": 234,
  "last_check_at": "2025-01-17T10:30:00Z"
}
```

---

## ADDITIONAL NOTES

### Implementation Priorities (recommended order):

**Phase 1: Infrastructure + Data Service** (~2-3 min)
- Docker Compose setup
- PostgreSQL service
- Data API (CRUD endpoints)
- Alembic migrations
- Seed data

**Phase 2: AI Manager API** (~3-4 min)
- Business logic
- AI provider integrations
- HTTP client to Data API
- Process prompt use case

**Phase 3: Telegram Bot** (~2 min)
- Aiogram setup
- Command handlers
- HTTP client to AI Manager API

**Phase 4: Health Worker** (~2 min)
- APScheduler setup
- Health check logic
- HTTP client to Data API

**Phase 5: API Features** (~1-2 min)
- Rate limiting
- CORS
- API key validation
- OpenAPI docs

**Phase 6: Tests + Documentation** (~2-3 min)
- Unit tests
- Integration tests
- Coverage report
- README

### Recommended AI Models for integration:

**Free/accessible:**
1. **HuggingFace Inference API:**
   - `mistralai/Mistral-7B-Instruct-v0.2`
   - `meta-llama/Llama-2-7b-chat-hf`
   - Free tier: 1000 requests/day

2. **Together.ai:**
   - `meta-llama/Llama-3-8b-chat-hf`
   - Free trial: $25 credit

3. **Replicate:**
   - `meta/llama-2-7b-chat`
   - Pay-per-use (cheap)

**For testing:**
- Create mock responses if no API keys available
- Simulate different latency and error rates

---

### Development Commands (Makefile):

```makefile
.PHONY: up down logs test lint migrate seed

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose exec aimanager_business_api pytest --cov=src

lint:
	docker-compose exec aimanager_business_api ruff check .
	docker-compose exec aimanager_business_api mypy .

migrate:
	docker-compose exec aimanager_data_postgres_api alembic upgrade head

seed:
	docker-compose exec aimanager_data_postgres_api python -m scripts.seed_data
```

---

**Ready to start generation!** 🚀
