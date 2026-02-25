# Business API Reference

> API Reference для Business API (Port 8000) — бизнес-логика, маршрутизация промптов и интеграция с AI-провайдерами.

## Base URL

```
http://localhost:8000
```

## Interactive Documentation

При запущенных сервисах:

- **Swagger UI:** <http://localhost:8000/docs>
- **ReDoc:** <http://localhost:8000/redoc>

## Architecture

Business API не обращается к БД напрямую — все данные получает через HTTP-вызовы к [Data API](data-api.md). Это ключевое архитектурное правило проекта.

```
Client → Business API (8000) → Data API (8001) → PostgreSQL
```

---

## Root Endpoints

### GET /

Перенаправление на веб-интерфейс.

```bash
curl -L http://localhost:8000/
# → Redirect 307 → /static/index.html
```

---

### GET /api

Информация об API. Защищён rate limiter.

#### Rate Limit

`100 requests / 60 seconds` per IP (настраивается через `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_PERIOD`).

#### Response Example (200 OK)

```json
{
  "service": "free-ai-selector-business-api",
  "version": "1.0.0",
  "environment": "development",
  "docs": "/docs",
  "health": "/health"
}
```

#### Errors

| Status | Description |
|--------|-------------|
| 429 | Rate limit exceeded (см. [ErrorResponse](errors.md#errorresponse-f025)) |

---

### GET /health

Проверка здоровья сервиса и связи с Data API.

#### Response Model: `HealthCheckResponse`

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"healthy"` или `"unhealthy"` |
| `service` | string | Имя сервиса |
| `version` | string | Версия сервиса |
| `data_api_connection` | string | Статус подключения к Data API |

#### Response Example

```json
{
  "status": "healthy",
  "service": "free-ai-selector-business-api",
  "version": "1.0.0",
  "data_api_connection": "healthy"
}
```

---

## Prompts Endpoints

Prefix: `/api/v1/prompts`

### POST /api/v1/prompts/process

Обработать промпт наиболее надёжной AI-моделью. Платформа автоматически выбирает модель по reliability score, с fallback при ошибках.

#### Request Body: `ProcessPromptRequest`

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `prompt` | string | **Yes** | 1–10000 символов | Текст промпта |
| `model_id` | integer | No | > 0 | Принудительный выбор модели. При недоступности — fallback на лучшую (F019) |
| `system_prompt` | string | No | max 5000 символов | System prompt для управления поведением AI (F011-B). Только OpenAI-совместимые провайдеры |
| `response_format` | object | No | — | Формат ответа, напр. `{"type": "json_object"}` (F011-B) |

#### Request Examples

```bash
# Базовый запрос — автоматический выбор модели
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Напиши стихотворение об AI"}'

# С принудительным выбором модели
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing",
    "model_id": 3
  }'

# С system prompt
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is 2+2?",
    "system_prompt": "You are a math teacher. Explain step by step."
  }'

# С JSON response format
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "List 3 programming languages with their use cases",
    "response_format": {"type": "json_object"}
  }'
```

#### Response: `ProcessPromptResponse` (200 OK)

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string | Исходный текст промпта |
| `response` | string | Ответ от AI |
| `selected_model` | string | Имя выбранной модели |
| `provider` | string | Имя провайдера |
| `response_time_seconds` | decimal | Время ответа (секунды) |
| `success` | boolean | Успешность (`true`) |
| `attempts` | integer | Количество попыток до успеха (F023) |
| `fallback_used` | boolean | Был ли использован fallback (F023) |

#### Response Example (Success)

```json
{
  "prompt": "Напиши стихотворение об AI",
  "response": "В мире битов и цифр живёт разум стальной...",
  "selected_model": "DeepSeek Chat",
  "provider": "DeepSeek",
  "response_time_seconds": 1.234,
  "success": true,
  "attempts": 1,
  "fallback_used": false
}
```

#### Response Example (Fallback)

```json
{
  "prompt": "Hello",
  "response": "Hi there! How can I help you?",
  "selected_model": "Llama 3.3 70B Versatile",
  "provider": "Groq",
  "response_time_seconds": 0.8,
  "success": true,
  "attempts": 3,
  "fallback_used": true
}
```

#### Error Responses

| Status | Model | Headers | Description |
|--------|-------|---------|-------------|
| 200 | `ProcessPromptResponse` | — | Успех (возможно через fallback) |
| 422 | Validation Error | — | Невалидный запрос |
| 429 | [`ErrorResponse`](errors.md#errorresponse-f025) | `Retry-After: N` | Все провайдеры rate-limited (F025) |
| 500 | `{"detail": "..."}` | — | Все провайдеры вернули ошибку |
| 503 | [`ErrorResponse`](errors.md#errorresponse-f025) | `Retry-After: N` | Сервис недоступен (F025) |

#### Error Example: 429 All Providers Rate Limited

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

#### Error Example: 500 All Providers Failed

```json
{
  "detail": "Failed to process prompt [ProviderError]: All providers returned errors"
}
```

#### Error Example: 503 Service Unavailable

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

## Models Endpoints

Prefix: `/api/v1/models`

### GET /api/v1/models/stats

Получить статистику надёжности всех AI-моделей.

#### Request

Параметры отсутствуют.

#### Request Example

```bash
curl http://localhost:8000/api/v1/models/stats
```

#### Response: `ModelsStatsResponse` (200 OK)

| Field | Type | Description |
|-------|------|-------------|
| `models` | array | Список моделей со статистикой |
| `total_models` | integer | Общее количество моделей |

Каждая модель (`AIModelStatsResponse`):

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | ID модели |
| `name` | string | Имя модели |
| `provider` | string | Провайдер |
| `reliability_score` | float | Reliability score (0.0–1.0) |
| `success_rate` | float | Success rate (0.0–1.0) |
| `average_response_time` | float | Среднее время ответа (сек) |
| `total_requests` | integer | Общее количество запросов |
| `is_active` | boolean | Активна ли модель |

#### Response Example

```json
{
  "models": [
    {
      "id": 1,
      "name": "DeepSeek Chat",
      "provider": "DeepSeek",
      "reliability_score": 0.92,
      "success_rate": 0.95,
      "average_response_time": 1.5,
      "total_requests": 150,
      "is_active": true
    },
    {
      "id": 2,
      "name": "Llama 3.3 70B Versatile",
      "provider": "Groq",
      "reliability_score": 0.93,
      "success_rate": 0.95,
      "average_response_time": 0.8,
      "total_requests": 180,
      "is_active": true
    }
  ],
  "total_models": 14
}
```

#### Errors

| Status | Description |
|--------|-------------|
| 500 | `Failed to fetch models statistics: ...` |

---

## Providers Endpoints

Prefix: `/api/v1/providers`

### POST /api/v1/providers/test

Протестировать все AI-провайдеры простым промптом. Обновляет статистику в БД (increment-success/increment-failure).

#### Request

Параметры отсутствуют.

#### Request Example

```bash
curl -X POST http://localhost:8000/api/v1/providers/test
```

#### Response (200 OK)

| Field | Type | Description |
|-------|------|-------------|
| `total_providers` | integer | Количество протестированных провайдеров |
| `successful` | integer | Количество успешных |
| `failed` | integer | Количество неудачных |
| `results` | array | Результаты по каждому провайдеру |

Каждый результат:

| Field | Type | Description |
|-------|------|-------------|
| `provider` | string | Имя провайдера |
| `model` | string | Имя модели |
| `status` | string | `"success"` или `"error"` |
| `response_time` | float / null | Время ответа (секунды). `null` при ошибке |
| `error` | string / null | Описание ошибки. `null` при успехе |

#### Response Example

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

Результаты отсортированы по `response_time` (fastest first).

#### Errors

| Status | Description |
|--------|-------------|
| 500 | `Failed to test providers: ...` |

---

## Middleware

### Rate Limiting

Business API использует [slowapi](https://github.com/laurentS/slowapi) для rate limiting по IP.

| Endpoint | Limit | Настройка |
|----------|-------|-----------|
| `GET /api` | `100/60s` | `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_PERIOD` |
| `POST /api/v1/prompts/process` | `100/minute` | `PROCESS_RATE_LIMIT` |

При превышении лимита возвращается **429** с `ErrorResponse`:

```json
{
  "error": "client_rate_limited",
  "message": "Rate limit exceeded: 100 per 1 minute",
  "retry_after": 60,
  "attempts": 0,
  "providers_tried": 0,
  "providers_available": 0
}
```

### CORS

Настраивается через `CORS_ORIGINS` (default: `http://localhost:3000,http://localhost:8000`).

### Request Tracing

Все запросы получают `X-Request-ID` (генерируется автоматически или передаётся клиентом).

| Header | Direction | Description |
|--------|-----------|-------------|
| `X-Request-ID` | Request / Response | ID запроса для трассировки |
| `X-Correlation-ID` | Request | ID корреляции для cross-service tracing |

```bash
curl -H "X-Request-ID: my-trace-123" \
  -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'
# Response header: X-Request-ID: my-trace-123
```

### Error Handling Middleware

Необработанные исключения перехватываются middleware и возвращаются как:

```json
{
  "detail": "Internal server error",
  "request_id": "abc123",
  "error_type": "ValueError"
}
```

---

## Python Client Example

```python
import asyncio
from decimal import Decimal

import httpx


async def process_prompt(
    prompt: str,
    model_id: int | None = None,
    system_prompt: str | None = None,
) -> dict:
    """Обработать промпт через Business API."""
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

        # F025: Обработка backpressure
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"Rate limited. Retry after {retry_after}s")
            return response.json()

        if response.status_code == 503:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"Service unavailable. Retry after {retry_after}s")
            return response.json()

        response.raise_for_status()
        return response.json()


async def get_models_stats() -> dict:
    """Получить статистику моделей."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/models/stats")
        response.raise_for_status()
        return response.json()


async def main():
    result = await process_prompt("Explain quantum computing in simple terms")
    print(f"Response: {result['response']}")
    print(f"Model: {result['selected_model']} ({result['provider']})")
    print(f"Time: {result['response_time_seconds']}s")
    print(f"Attempts: {result['attempts']}, Fallback: {result['fallback_used']}")


asyncio.run(main())
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_API_URL` | `http://localhost:8001` | URL Data API |
| `ENVIRONMENT` | `development` | Окружение |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | CORS origins |
| `RATE_LIMIT_REQUESTS` | `100` | Лимит запросов |
| `RATE_LIMIT_PERIOD` | `60` | Период лимита (секунды) |
| `PROCESS_RATE_LIMIT` | `100/minute` | Rate limit для `/process` |
| `ROOT_PATH` | `` | Prefix для reverse proxy |

---

## Related Documentation

- [Data API Reference](data-api.md) — CRUD для моделей и истории
- [Errors](errors.md) — Коды ошибок, ErrorResponse, troubleshooting
- [Examples](examples.md) — Примеры использования
- [../project/ai-providers.md](../project/ai-providers.md) — AI провайдеры
