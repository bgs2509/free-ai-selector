# API Errors

> Документация по ошибкам API Free AI Selector.

## HTTP Status Codes

### Success Codes

| Code | Description |
|------|-------------|
| 200 | OK — запрос выполнен успешно |
| 201 | Created — ресурс создан |
| 307 | Temporary Redirect — перенаправление (GET / → веб-интерфейс) |

### Client Error Codes

| Code | Description | Когда возникает |
|------|-------------|-----------------|
| 404 | Not Found | Модель или запись истории не найдена |
| 409 | Conflict | Модель с таким именем уже существует |
| 422 | Validation Error | Невалидные данные в запросе |
| 429 | Too Many Requests | Rate limit клиента или все провайдеры rate-limited (F025) |

### Server Error Codes

| Code | Description | Когда возникает |
|------|-------------|-----------------|
| 500 | Internal Server Error | Все AI-провайдеры вернули ошибку; непредвиденная ошибка |
| 503 | Service Unavailable | Нет активных моделей; Data API недоступен (F025) |

---

## Error Response Formats

### Standard Error (FastAPI HTTPException)

Используется для 404, 409, 500:

```json
{
  "detail": "AI model with ID 999 not found"
}
```

### Validation Error (422)

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "prompt"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### Unhandled Exception (500)

Перехватывается middleware:

```json
{
  "detail": "Internal server error",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "error_type": "ValueError"
}
```

### Process Prompt Error (500)

Все провайдеры вернули ошибку:

```json
{
  "detail": "Failed to process prompt [ProviderError]: All providers returned errors"
}
```

Формат: `Failed to process prompt [{ErrorType}]: {message}`

---

## ErrorResponse (F025)

Структурированный формат ошибки для HTTP 429 и 503. Включает заголовок `Retry-After`.

### Schema

```python
class ErrorResponse(BaseModel):
    error: str          # Код ошибки
    message: str        # Человекочитаемое описание
    retry_after: int    # Секунд до retry (также в Retry-After header)
    attempts: int       # Количество попыток обращения к провайдерам
    providers_tried: int    # Сколько провайдеров вернули ошибку
    providers_available: int # Сколько провайдеров сконфигурировано
```

### Error Codes

| `error` | HTTP | Description |
|---------|------|-------------|
| `all_rate_limited` | 429 | Все AI-провайдеры вернули 429 (rate limited) |
| `client_rate_limited` | 429 | Клиент превысил rate limit slowapi |
| `service_unavailable` | 503 | Сервис недоступен (нет моделей, Data API down) |

### Response Headers

| Header | Value | Description |
|--------|-------|-------------|
| `Retry-After` | integer | Секунд до повторного запроса |

### Example: All Providers Rate Limited (429)

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
Content-Type: application/json

{
  "error": "all_rate_limited",
  "message": "All AI providers are rate limited. Please retry later.",
  "retry_after": 30,
  "attempts": 5,
  "providers_tried": 5,
  "providers_available": 0
}
```

### Example: Client Rate Limited (429)

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "error": "client_rate_limited",
  "message": "Rate limit exceeded: 100 per 1 minute",
  "retry_after": 60,
  "attempts": 0,
  "providers_tried": 0,
  "providers_available": 0
}
```

### Example: Service Unavailable (503)

```http
HTTP/1.1 503 Service Unavailable
Retry-After: 60
Content-Type: application/json

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

## Errors by Endpoint

### Business API

#### POST /api/v1/prompts/process

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| `all_rate_limited` | 429 | Все провайдеры rate-limited | Retry после `Retry-After` секунд |
| `service_unavailable` | 503 | Нет активных моделей | `make seed` или проверить Data API |
| `Failed to process prompt` | 500 | Все провайдеры вернули ошибку | Проверить API ключи, `make logs-business` |
| Validation Error | 422 | Отсутствует `prompt` или невалидные данные | Проверить формат запроса |

#### GET /api

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| `client_rate_limited` | 429 | Превышен rate limit клиента | Подождать `retry_after` секунд |

#### GET /api/v1/models/stats

| Error | Status | Cause |
|-------|--------|-------|
| `Failed to fetch models statistics` | 500 | Data API недоступен |

#### POST /api/v1/providers/test

| Error | Status | Cause |
|-------|--------|-------|
| `Failed to test providers` | 500 | Критическая ошибка тестирования |

### Data API

#### GET /api/v1/models/{model_id}

| Error | Status | Cause |
|-------|--------|-------|
| `AI model with ID {id} not found` | 404 | ID не существует |

#### POST /api/v1/models

| Error | Status | Cause |
|-------|--------|-------|
| `AI model with name '{name}' already exists` | 409 | Дубликат имени модели |
| Validation Error | 422 | Отсутствует обязательное поле |

#### PUT /api/v1/models/{model_id}/stats

| Error | Status | Cause |
|-------|--------|-------|
| `AI model with ID {id} not found` | 404 | ID не существует |

#### POST /api/v1/models/{model_id}/increment-success, increment-failure

| Error | Status | Cause |
|-------|--------|-------|
| `AI model with ID {id} not found` | 404 | ID не существует |

#### PATCH /api/v1/models/{model_id}/active, availability

| Error | Status | Cause |
|-------|--------|-------|
| `AI model with ID {id} not found` | 404 | ID не существует |

#### GET /api/v1/history/{history_id}

| Error | Status | Cause |
|-------|--------|-------|
| `History record with ID {id} not found` | 404 | ID не существует |

---

## AI Provider Errors (Internal)

Эти ошибки обрабатываются внутри Business API и не возвращаются клиенту напрямую — система переключается на fallback-модель.

### Error Classification (F022)

| HTTP Code | Классификация | Retryable | Description |
|-----------|--------------|-----------|-------------|
| 401 | `AuthError` | No | Невалидный API ключ |
| 402 | `PaymentRequired` | No | Требуется оплата |
| 403 | `AuthError` | No | Доступ запрещён |
| 404 | `NotFound` | No | Модель/endpoint не найден |
| 429 | `RateLimited` | Yes | Rate limit провайдера |
| 500 | `ProviderError` | Yes | Ошибка сервера провайдера |
| 502 | `ProviderError` | Yes | Bad Gateway |
| 503 | `ProviderError` | Yes | Сервис провайдера недоступен |

### Resilience Features

| Feature | Description |
|---------|-------------|
| **Fallback** (F014) | При ошибке — переключение на следующую модель по reliability score |
| **Exponential Backoff** (F023) | Увеличивающиеся задержки при retry |
| **Cooldown** (F012, F023) | Временное исключение провайдера после ошибок |
| **Circuit Breaker** (F024) | Паттерн CLOSED/OPEN/HALF-OPEN для нестабильных провайдеров |
| **Payload Protection** (F022) | Обрезка payload > 6000 символов |
| **Per-request Telemetry** (F023) | Поля `attempts` и `fallback_used` в ответе |

---

## Client Error Handling

### Python (httpx)

```python
import httpx


async def process_with_retry(prompt: str, max_retries: int = 3):
    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            response = await client.post(
                "http://localhost:8000/api/v1/prompts/process",
                json={"prompt": prompt},
                timeout=60.0,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 30))
                data = response.json()
                print(f"Rate limited ({data['error']}). Waiting {retry_after}s...")
                await asyncio.sleep(retry_after)
                continue

            if response.status_code == 503:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"Service unavailable. Waiting {retry_after}s...")
                await asyncio.sleep(retry_after)
                continue

            if response.status_code == 422:
                print(f"Invalid request: {response.json()}")
                raise ValueError("Invalid request")

            response.raise_for_status()

    raise RuntimeError(f"Failed after {max_retries} retries")
```

### curl

```bash
# Запрос с проверкой Retry-After
response=$(curl -s -w "\n%{http_code}" -X POST \
  http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}')

http_code=$(echo "$response" | tail -1)
body=$(echo "$response" | head -1)

if [ "$http_code" = "429" ]; then
  echo "Rate limited: $body"
elif [ "$http_code" = "503" ]; then
  echo "Service unavailable: $body"
elif [ "$http_code" = "200" ]; then
  echo "Success: $body"
fi
```

---

## Troubleshooting

### Ошибка 429: All Providers Rate Limited

1. Подождать `Retry-After` секунд
2. Проверить cooldown моделей: `curl "http://localhost:8001/api/v1/models?active_only=true"` — поле `available_at`
3. Проверить логи: `make logs-business | grep "backpressure_applied"`

### Ошибка 500: All AI Providers Failed

1. Проверить API ключи в `.env`
2. Протестировать провайдеров: `curl -X POST http://localhost:8000/api/v1/providers/test`
3. Проверить логи: `make logs-business`

### Ошибка 503: Service Unavailable

1. Проверить что Data API работает: `curl http://localhost:8001/health`
2. Проверить что есть активные модели: `curl http://localhost:8001/api/v1/models`
3. Запустить seed при необходимости: `make seed`

### Ошибка 422: Validation Error

1. Проверить формат JSON
2. Убедиться что все обязательные поля присутствуют
3. Проверить constraints (длина строк, диапазоны чисел)

### Ошибка 409: Conflict

1. Модель с таким именем уже существует
2. Выбрать другое имя или обновить существующую

---

## Related Documentation

- [Business API](business-api.md) — API Reference
- [Data API](data-api.md) — Data API Reference
- [Examples](examples.md) — Примеры использования
- [../operations/troubleshooting.md](../operations/troubleshooting.md) — Troubleshooting Guide
