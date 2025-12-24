# Development Guide

> **Free AI Selector** - Development guide for contributors

## Prerequisites

- Docker 24.0+
- Docker Compose 2.0+
- Python 3.12+ (for local development)
- Git
- Make

## Getting Started

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/free-ai-selector.git
cd free-ai-selector

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### 2. Required API Keys

Get free API keys from (all providers require NO credit card):

- **Google AI Studio**: https://aistudio.google.com/apikey
- **Groq**: https://console.groq.com/keys
- **Cerebras**: https://cloud.cerebras.ai/
- **SambaNova**: https://cloud.sambanova.ai/
- **HuggingFace**: https://huggingface.co/settings/tokens
- **Cloudflare**: https://dash.cloudflare.com/ (need Account ID + API Token)
- **Telegram Bot**: https://t.me/BotFather

### 3. Start Development Environment

```bash
# Build all services
make build

# Start services
make up

# Initialize database
make migrate
make seed

# Verify health
make health
```

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run Data API tests only
make test-data

# Run Business API tests only
make test-business
```

**Level 2 Requirement**: >=75% code coverage

### Code Quality

```bash
# Run linters
make lint

# Format code
make format
```

Tools used:
- **ruff**: Fast Python linter and formatter
- **mypy**: Static type checker
- **bandit**: Security linter

### Database Management

```bash
# Run migrations
make migrate

# Seed initial data
make seed

# Open PostgreSQL shell
make db-shell

# Reset database (WARNING: deletes all data)
make clean
```

### Viewing Logs

```bash
# All services
make logs

# Specific service
make logs-data
make logs-business
make logs-bot
make logs-worker
```

## Project Structure

```
free-ai-selector/
├── .aidd/                      # AIDD Framework (git submodule)
├── services/
│   ├── free-ai-selector-data-postgres-api/
│   │   ├── app/
│   │   │   ├── api/v1/         # FastAPI routes
│   │   │   ├── domain/         # Domain models
│   │   │   ├── infrastructure/ # Database, repositories
│   │   │   └── main.py         # FastAPI app
│   │   ├── alembic/            # Database migrations
│   │   ├── tests/              # Unit + integration tests
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── free-ai-selector-business-api/
│   │   ├── app/
│   │   │   ├── api/v1/         # FastAPI routes
│   │   │   ├── application/    # Use cases
│   │   │   ├── domain/         # Domain models
│   │   │   ├── infrastructure/ # HTTP clients, AI providers
│   │   │   └── main.py         # FastAPI app
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── free-ai-selector-telegram-bot/
│   │   ├── app/
│   │   │   ├── handlers/       # Command handlers
│   │   │   └── main.py         # Bot entry point
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── free-ai-selector-health-worker/
│       ├── app/
│       │   └── main.py         # Worker with APScheduler
│       ├── Dockerfile
│       └── requirements.txt
│
├── docker-compose.yml          # Service orchestration
├── Makefile                    # Development commands
├── README.md                   # Project overview
└── .env.example                # Environment template
```

## Architecture Patterns

### 1. HTTP-Only Data Access

**Rule**: Business services MUST access data only via HTTP to Data API.

```python
# CORRECT: Use HTTP client
from app.infrastructure.http_clients.data_api_client import DataAPIClient

data_client = DataAPIClient()
models = await data_client.get_all_models()

# WRONG: Direct database access
from app.infrastructure.database.connection import get_db  # NO!
```

### 2. DDD/Hexagonal Architecture

**Layers** (from inside out):

1. **Domain**: Pure business logic, no dependencies
2. **Application**: Use cases, orchestrates domain + infrastructure
3. **Infrastructure**: External concerns (DB, HTTP, AI providers)
4. **API**: HTTP endpoints, request/response handling

### 3. Service Separation

Each service runs in a **separate container**:

- **free-ai-selector-data-postgres-api** (port 8001)
- **free-ai-selector-business-api** (port 8000)
- **free-ai-selector-telegram-bot** (no exposed port)
- **free-ai-selector-health-worker** (no exposed port)
- **postgres** (port 5432)

## Adding a New AI Provider

### Step 1: Create Provider Implementation

```python
# services/free-ai-selector-business-api/app/infrastructure/ai_providers/newprovider.py

from app.infrastructure.ai_providers.base import AIProviderBase

class NewProvider(AIProviderBase):
    async def generate(self, prompt: str, **kwargs) -> str:
        # Implementation here
        pass

    async def health_check(self) -> bool:
        # Implementation here
        pass

    def get_provider_name(self) -> str:
        return "NewProvider"
```

### Step 2: Register in Use Case

```python
# services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py

from app.infrastructure.ai_providers.newprovider import NewProvider

class ProcessPromptUseCase:
    def __init__(self, data_api_client: DataAPIClient):
        self.providers = {
            "GoogleGemini": GoogleGeminiProvider(),
            "Groq": GroqProvider(),
            "Cerebras": CerebrasProvider(),
            "SambaNova": SambanovaProvider(),
            "HuggingFace": HuggingFaceProvider(),
            "Cloudflare": CloudflareProvider(),
            "NewProvider": NewProvider(),  # Add your new provider here
        }
```

### Step 3: Seed Database

```python
# Add to services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py

SEED_MODELS = [
    # ... existing models ...
    {
        "name": "NewProvider Model Name",
        "provider": "NewProvider",
        "api_endpoint": "https://api.newprovider.com/v1/generate",
        "is_active": True,
    },
]
```

### Step 4: Add Environment Variable

```bash
# .env
NEW_PROVIDER_API_KEY=your_key_here
```

### Step 5: Test

```bash
make migrate
make seed
make test-business
```

## Debugging

### Access Service Shells

```bash
# Data API
make shell-data

# Business API
make shell-business

# PostgreSQL
make db-shell
```

### Check Service Health

```bash
# Via Make
make health

# Via curl
curl http://localhost:8001/health  # Data API
curl http://localhost:8000/health  # Business API
```

### View Service Logs

```bash
# Real-time logs
make logs-business

# Last 100 lines
docker-compose logs --tail=100 free-ai-selector-business-api
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Follow coding standards:
   - Type hints for all functions
   - Docstrings in Google format
   - >=75% test coverage
   - Pass all linters (ruff, mypy, bandit)
4. Commit: `git commit -m 'feat: add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Open Pull Request

## Troubleshooting

### Database Connection Errors

```bash
# Check if postgres is running
docker-compose ps postgres

# Restart postgres
docker-compose restart postgres

# View postgres logs
make logs-db
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in .env
BUSINESS_API_PORT=8080
```

### Tests Failing

```bash
# Run with verbose output
pytest -vv

# Run specific test
pytest tests/unit/test_ai_model_repository.py::TestAIModelRepository::test_create_model

# Run with coverage report
pytest --cov=app --cov-report=html
# Open htmlcov/index.html
```

## References

- [Project Documentation](../index.md)
- [AI Providers](../project/ai-providers.md)
- [API Reference](../api/business-api.md)
- [AIDD Framework](../../.aidd/CLAUDE.md)
