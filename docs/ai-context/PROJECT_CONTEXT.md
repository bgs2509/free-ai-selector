# Project Context for AI Code Generation

> Этот файл предоставляет контекст для Claude Code при генерации кода в проекте Free AI Selector.

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Project** | Free AI Selector |
| **Language** | Python 3.12+ |
| **Framework** | FastAPI, aiogram 3.x |
| **Architecture** | DDD/Hexagonal |
| **Database** | PostgreSQL 16 (async) |
| **ORM** | SQLAlchemy 2.0 async |
| **Testing** | pytest, coverage >= 75% |
| **Linting** | ruff, mypy, bandit |
| **Containers** | Docker Compose |

## Core Business Logic

**Формула расчёта надёжности модели:**

```python
reliability_score = (success_rate * 0.6) + (speed_score * 0.4)
```

- `success_rate` = success_count / request_count (0.0 - 1.0)
- `speed_score` = max(0, 1.0 - avg_response_time / 10.0) (baseline 10 секунд)

---

## General Patterns (ссылки на .aidd/)

Эти паттерны описаны в фреймворке AIDD и НЕ ДОЛЖНЫ дублироваться:

| Тема | Файл | Описание |
|------|------|----------|
| DDD/Hexagonal | [.aidd/knowledge/architecture/ddd-hexagonal.md](../../.aidd/knowledge/architecture/ddd-hexagonal.md) | Слои, зависимости, Domain Models |
| Структура проекта | [.aidd/knowledge/architecture/project-structure.md](../../.aidd/knowledge/architecture/project-structure.md) | Стандартная структура сервисов |
| HTTP-only доступ | [.aidd/knowledge/architecture/data-access.md](../../.aidd/knowledge/architecture/data-access.md) | Паттерн HTTP-only |
| Coding Standards | [.aidd/conventions.md](../../.aidd/conventions.md) | Naming, imports, docstrings |
| Testing | [.aidd/knowledge/quality/testing/](../../.aidd/knowledge/quality/testing/) | pytest, fixtures, mocking |
| FastAPI patterns | [.aidd/knowledge/services/fastapi/](../../.aidd/knowledge/services/fastapi/) | Routing, DI, error handling |
| Logging | [.aidd/knowledge/quality/logging/](../../.aidd/knowledge/quality/logging/) | Structured logging |

---

## Project-Specific Rules

### 1. HTTP-Only Data Access (КРИТИЧНО!)

Business API **НИКОГДА** не обращается к БД напрямую. Только через HTTP к Data API.

```python
# CORRECT - Use HTTP client for data access
from app.infrastructure.http_clients.data_api_client import DataAPIClient

client = DataAPIClient()
models = await client.get_all_models(active_only=True)
await client.increment_success(model_id=1)
await client.create_history(history_data)


# WRONG - NEVER access DB directly from Business API!
from app.infrastructure.database import Session  # FORBIDDEN!
from sqlalchemy import select  # FORBIDDEN in Business API!
```

### 2. Directory Structure

```
services/aimanager_business_api/
├── app/
│   ├── api/v1/           # FastAPI routers (HTTP endpoints)
│   ├── application/      # Use cases (business logic orchestration)
│   ├── domain/           # Domain models (pure Python DTOs)
│   └── infrastructure/   # External dependencies
│       ├── ai_providers/ # AI provider implementations
│       └── http_clients/ # HTTP clients to other services
├── tests/
│   ├── unit/             # Unit tests (mocked dependencies)
│   └── integration/      # Integration tests
└── Dockerfile

services/aimanager_data_postgres_api/
├── app/
│   ├── api/v1/           # FastAPI routers (CRUD endpoints)
│   ├── domain/           # Domain models with business logic
│   └── infrastructure/
│       ├── database/     # SQLAlchemy models, migrations
│       └── repositories/ # Repository pattern
├── tests/
└── Dockerfile
```

### 3. AI Provider Pattern

Все AI провайдеры наследуют от `AIProviderBase`:

```python
from app.infrastructure.ai_providers.base import AIProviderBase

class NewProvider(AIProviderBase):
    """New AI provider implementation."""

    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate AI response for given prompt."""
        # Implementation here
        pass

    async def health_check(self) -> bool:
        """Check if provider is available."""
        # Implementation here
        pass

    def get_provider_name(self) -> str:
        """Return provider name for logging/stats."""
        return "NewProvider"
```

### 4. Use Case Pattern

Бизнес-логика инкапсулирована в Use Cases:

```python
class ProcessPromptUseCase:
    """Use case for processing user prompts."""

    def __init__(self, data_api_client: DataAPIClient):
        self.data_api_client = data_api_client
        self.providers = {
            "GoogleGemini": GoogleGeminiProvider(),
            # ... other providers
        }

    async def execute(self, request: PromptRequest) -> PromptResponse:
        """Execute prompt processing.

        Steps:
            1. Fetch active models from Data API
            2. Select best model by reliability_score
            3. Generate response with selected provider
            4. Update statistics in Data API
            5. Record history
        """
        pass
```

---

## Generation Checklist

При генерации кода убедитесь:

- [ ] Type hints на всех функциях и методах
- [ ] Docstrings в Google-стиле (на русском для этого проекта)
- [ ] Async/await для всех I/O операций
- [ ] Error handling с логированием
- [ ] HTTP-only доступ к данным из Business API
- [ ] Тесты с coverage >= 75%
- [ ] Импорты сгруппированы (stdlib, third-party, local)

---

## Environment Variables

Ключевые переменные окружения:

| Variable | Service | Description |
|----------|---------|-------------|
| `DATA_API_URL` | Business API | URL Data API (http://aimanager_data_postgres_api:8001) |
| `DATABASE_URL` | Data API | PostgreSQL connection string |
| `GOOGLE_AI_STUDIO_API_KEY` | Business API | Google Gemini API key |
| `GROQ_API_KEY` | Business API | Groq API key |
| `CEREBRAS_API_KEY` | Business API | Cerebras API key |
| `SAMBANOVA_API_KEY` | Business API | SambaNova API key |
| `HUGGINGFACE_API_KEY` | Business API | HuggingFace token |
| `CLOUDFLARE_ACCOUNT_ID` | Business API | Cloudflare Account ID |
| `CLOUDFLARE_API_TOKEN` | Business API | Cloudflare API Token |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot | Bot token from @BotFather |

---

## Related Documentation

- [SERVICE_MAP.md](SERVICE_MAP.md) - Карта компонентов и потоков данных
- [EXAMPLES.md](EXAMPLES.md) - Примеры кода
- [../project/ai-providers.md](../project/ai-providers.md) - Детали AI провайдеров
- [../api/business-api.md](../api/business-api.md) - API Reference
