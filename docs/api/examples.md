# API Examples

> **Free AI Selector** — примеры использования REST API.

## Base URLs

- **Business API**: `http://localhost:8000`
- **Data API**: `http://localhost:8001`

---

## Business API Examples

### 1. Process Prompt (базовый)

Отправить промпт — платформа автоматически выберет лучшую модель.

**Endpoint**: `POST /api/v1/prompts/process`

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a short poem about artificial intelligence"}'
```

**Response**:
```json
{
  "prompt": "Write a short poem about artificial intelligence",
  "response": "In circuits deep and code so bright,\nAI learns through day and night...",
  "selected_model": "DeepSeek Chat",
  "provider": "DeepSeek",
  "response_time_seconds": 2.34,
  "success": true,
  "attempts": 1,
  "fallback_used": false
}
```

### 2. Process Prompt с выбором модели (F019)

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing",
    "model_id": 3
  }'
```

Если модель #3 недоступна, система автоматически выберет fallback.

### 3. Process Prompt с system prompt (F011-B)

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is 2+2?",
    "system_prompt": "You are a math teacher. Always show your work step by step."
  }'
```

### 4. Process Prompt с JSON response format (F011-B)

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List 3 programming languages with pros and cons",
    "response_format": {"type": "json_object"}
  }'
```

### 5. Process Prompt с fallback (F023 telemetry)

Когда первая модель недоступна, система переключается на fallback:

**Response**:
```json
{
  "prompt": "Hello",
  "response": "Hi there!",
  "selected_model": "Llama 3.3 70B Versatile",
  "provider": "Groq",
  "response_time_seconds": 0.8,
  "success": true,
  "attempts": 3,
  "fallback_used": true
}
```

`attempts=3` значит что 2 модели вернули ошибку, 3-я успешна.

### 6. Обработка backpressure (F025)

**429 — все провайдеры rate-limited**:
```bash
curl -i -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# HTTP/1.1 429 Too Many Requests
# Retry-After: 30
```

```json
{
  "error": "all_rate_limited",
  "message": "All AI providers are rate limited. Please retry later.",
  "retry_after": 30,
  "attempts": 5,
  "providers_tried": 5,
  "providers_available": 0
}
```

---

### 7. Get Models Statistics

**Endpoint**: `GET /api/v1/models/stats`

**Request**:
```bash
curl http://localhost:8000/api/v1/models/stats
```

**Response**:
```json
{
  "models": [
    {
      "id": 1,
      "name": "DeepSeek Chat",
      "provider": "DeepSeek",
      "reliability_score": 0.92,
      "success_rate": 0.95,
      "average_response_time": 2.1,
      "total_requests": 150,
      "is_active": true
    },
    {
      "id": 2,
      "name": "Llama 3.3 70B Versatile",
      "provider": "Groq",
      "reliability_score": 0.93,
      "success_rate": 0.95,
      "average_response_time": 1.2,
      "total_requests": 180,
      "is_active": true
    }
  ],
  "total_models": 14
}
```

### 8. Test All Providers

**Endpoint**: `POST /api/v1/providers/test`

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/providers/test
```

**Response**:
```json
{
  "total_providers": 14,
  "successful": 12,
  "failed": 2,
  "results": [
    {
      "provider": "Cerebras",
      "model": "Llama 3.3 70B",
      "status": "success",
      "response_time": 0.87,
      "error": null
    },
    {
      "provider": "HuggingFace",
      "model": "Meta-Llama-3-8B-Instruct",
      "status": "error",
      "response_time": null,
      "error": "HTTPError: 503 Model is currently loading"
    }
  ]
}
```

### 9. Health Check

**Endpoint**: `GET /health`

**Request**:
```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "free-ai-selector-business-api",
  "version": "1.0.0",
  "data_api_connection": "healthy"
}
```

### 10. API Info

**Endpoint**: `GET /api`

**Request**:
```bash
curl http://localhost:8000/api
```

**Response**:
```json
{
  "service": "free-ai-selector-business-api",
  "version": "1.0.0",
  "environment": "development",
  "docs": "/docs",
  "health": "/health"
}
```

---

## Data API Examples

### 1. List All AI Models

**Endpoint**: `GET /api/v1/models`

**Request**:
```bash
curl "http://localhost:8001/api/v1/models?active_only=true"
```

**Response**:
```json
[
  {
    "id": 1,
    "name": "DeepSeek Chat",
    "provider": "DeepSeek",
    "api_endpoint": "https://api.deepseek.com/v1",
    "success_count": 143,
    "failure_count": 7,
    "total_response_time": 315.5,
    "request_count": 150,
    "last_checked": "2026-02-25T14:30:00Z",
    "is_active": true,
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-02-25T14:30:00Z",
    "api_format": "openai",
    "available_at": null,
    "success_rate": 0.953,
    "average_response_time": 2.103,
    "speed_score": 0.790,
    "reliability_score": 0.888,
    "recent_success_rate": null,
    "recent_request_count": null,
    "recent_reliability_score": null,
    "effective_reliability_score": null,
    "decision_reason": null
  }
]
```

### 2. List Models with Recent Metrics (F010)

**Request**:
```bash
curl "http://localhost:8001/api/v1/models?include_recent=true&window_days=7"
```

**Response** (модель с достаточными recent данными):
```json
[
  {
    "id": 1,
    "name": "DeepSeek Chat",
    "provider": "DeepSeek",
    "reliability_score": 0.888,
    "recent_success_rate": 0.95,
    "recent_request_count": 20,
    "recent_reliability_score": 0.92,
    "effective_reliability_score": 0.92,
    "decision_reason": "recent_score"
  }
]
```

**Response** (модель с недостаточными recent данными < 3):
```json
[
  {
    "id": 5,
    "name": "Some Model",
    "reliability_score": 0.75,
    "recent_success_rate": null,
    "recent_request_count": 1,
    "recent_reliability_score": null,
    "effective_reliability_score": 0.75,
    "decision_reason": "fallback"
  }
]
```

### 3. List Available Models Only (F012)

Исключить модели с активным rate limit cooldown:

**Request**:
```bash
curl "http://localhost:8001/api/v1/models?available_only=true"
```

### 4. Get Specific Model

**Endpoint**: `GET /api/v1/models/{model_id}`

**Request**:
```bash
curl http://localhost:8001/api/v1/models/1
```

### 5. Create Model

**Endpoint**: `POST /api/v1/models`

**Request**:
```bash
curl -X POST http://localhost:8001/api/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Model",
    "provider": "NewProvider",
    "api_endpoint": "https://api.newprovider.com/v1"
  }'
```

### 6. Update Model Statistics

**Endpoint**: `PUT /api/v1/models/{model_id}/stats`

**Request**:
```bash
curl -X PUT http://localhost:8001/api/v1/models/1/stats \
  -H "Content-Type: application/json" \
  -d '{
    "success_count": 150,
    "failure_count": 10,
    "total_response_time": 320.5,
    "request_count": 160
  }'
```

### 7. Increment Success/Failure

**Request**:
```bash
# Успех
curl -X POST "http://localhost:8001/api/v1/models/1/increment-success?response_time=2.5"

# Ошибка
curl -X POST "http://localhost:8001/api/v1/models/1/increment-failure?response_time=5.0"
```

### 8. Set Model Active Status

**Request**:
```bash
curl -X PATCH "http://localhost:8001/api/v1/models/1/active?is_active=false"
```

### 9. Set Model Cooldown (F012)

**Request**:
```bash
# Установить cooldown 60 секунд
curl -X PATCH "http://localhost:8001/api/v1/models/1/availability?retry_after_seconds=60"

# Сбросить cooldown
curl -X PATCH "http://localhost:8001/api/v1/models/1/availability?retry_after_seconds=0"
```

### 10. Get Prompt History

**Endpoint**: `GET /api/v1/history`

**Request**:
```bash
curl "http://localhost:8001/api/v1/history?limit=10&success_only=false"
```

**Response**:
```json
[
  {
    "id": 1,
    "user_id": "api_user",
    "prompt_text": "Write a short poem about AI",
    "selected_model_id": 1,
    "response_text": "In circuits deep...",
    "response_time": 2.34,
    "success": true,
    "error_message": null,
    "created_at": "2026-02-25T14:25:00Z"
  }
]
```

### 11. Get User History

**Endpoint**: `GET /api/v1/history/user/{user_id}`

**Request**:
```bash
curl "http://localhost:8001/api/v1/history/user/telegram_123456?limit=50"
```

### 12. Get Model History

**Endpoint**: `GET /api/v1/history/model/{model_id}`

**Request**:
```bash
curl "http://localhost:8001/api/v1/history/model/1?limit=100"
```

### 13. Create Prompt History

**Endpoint**: `POST /api/v1/history`

**Request**:
```bash
curl -X POST http://localhost:8001/api/v1/history \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "prompt_text": "Test prompt",
    "selected_model_id": 1,
    "response_text": "Test response",
    "response_time": 2.5,
    "success": true,
    "error_message": null
  }'
```

### 14. Get Statistics for Period

**Endpoint**: `GET /api/v1/history/statistics/period`

**Request**:
```bash
curl "http://localhost:8001/api/v1/history/statistics/period?start_date=2026-02-01T00:00:00&end_date=2026-02-28T23:59:59"
```

**Response**:
```json
{
  "total_requests": 500,
  "successful_requests": 475,
  "failed_requests": 25,
  "success_rate": 0.95
}
```

### 15. Statistics for Specific Model

**Request**:
```bash
curl "http://localhost:8001/api/v1/history/statistics/period?start_date=2026-02-01T00:00:00&end_date=2026-02-28T23:59:59&model_id=1"
```

### 16. Data API Health Check

**Request**:
```bash
curl http://localhost:8001/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "free-ai-selector-data-postgres-api",
  "version": "1.0.0",
  "database": "healthy"
}
```

---

## Python Client Examples

### Using httpx (async)

```python
import asyncio
import httpx


async def process_prompt(
    prompt: str,
    model_id: int | None = None,
    system_prompt: str | None = None,
) -> dict:
    """Process a prompt using Business API."""
    payload = {"prompt": prompt}
    if model_id:
        payload["model_id"] = model_id
    if system_prompt:
        payload["system_prompt"] = system_prompt

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/prompts/process",
            json=payload,
            timeout=60.0,
        )

        # F025: Handle backpressure
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"Rate limited. Retry after {retry_after}s")
            await asyncio.sleep(retry_after)
            # Retry once
            response = await client.post(
                "http://localhost:8000/api/v1/prompts/process",
                json=payload,
                timeout=60.0,
            )

        response.raise_for_status()
        return response.json()


async def get_models_stats() -> dict:
    """Get models statistics."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/models/stats")
        response.raise_for_status()
        return response.json()


async def main():
    result = await process_prompt("Explain quantum computing in simple terms")
    print(f"Response: {result['response']}")
    print(f"Model used: {result['selected_model']} ({result['provider']})")
    print(f"Time: {result['response_time_seconds']}s")
    print(f"Attempts: {result['attempts']}, Fallback: {result['fallback_used']}")

    stats = await get_models_stats()
    print(f"\nTotal models: {stats['total_models']}")
    for model in stats["models"]:
        print(f"  {model['name']}: reliability={model['reliability_score']:.2f}")


asyncio.run(main())
```

---

## Error Handling

### Common Error Responses

**404 Not Found**:
```json
{
  "detail": "AI model with ID 999 not found"
}
```

**409 Conflict**:
```json
{
  "detail": "AI model with name 'Duplicate Model' already exists"
}
```

**422 Validation Error**:
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "prompt"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ]
}
```

**429 Rate Limited (F025)**:
```json
{
  "error": "all_rate_limited",
  "message": "All AI providers are rate limited. Please retry later.",
  "retry_after": 30,
  "attempts": 5,
  "providers_tried": 5,
  "providers_available": 0
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Failed to process prompt [ProviderError]: Connection refused"
}
```

**503 Service Unavailable (F025)**:
```json
{
  "error": "service_unavailable",
  "message": "No active AI models available",
  "retry_after": 60,
  "attempts": 0,
  "providers_tried": 0,
  "providers_available": 0
}
```

---

## Rate Limiting

Business API имеет rate limiting (настраивается через `.env`):

- **Default**: 100 requests per 60 seconds per IP
- **Response**: 429 с `ErrorResponse` и `Retry-After` header

```bash
curl -i http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# При превышении:
# HTTP/1.1 429 Too Many Requests
# Retry-After: 60
```

---

## Request Tracing

Все запросы трассируются через `X-Request-ID`:

```bash
curl -H "X-Request-ID: my-custom-id-123" \
  -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# Response header: X-Request-ID: my-custom-id-123
```

Поиск в логах:
```bash
docker compose logs | grep "my-custom-id-123"
```

---

## OpenAPI Documentation

Interactive API documentation:

- **Business API Swagger**: http://localhost:8000/docs
- **Business API ReDoc**: http://localhost:8000/redoc
- **Data API Swagger**: http://localhost:8001/docs
- **Data API ReDoc**: http://localhost:8001/redoc

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Запуск бота |
| `/help` | Справка |
| `/stats` | Статистика моделей |
| *любой текст* | Обработка промпта |

**Example**:
```
User: Write a haiku about programming
Bot: Code flows like a stream,
     Bugs dance in moonlit night,
     Debug until dawn.

     Model: DeepSeek Chat
     Provider: DeepSeek
     Time: 2.1 sec
```
