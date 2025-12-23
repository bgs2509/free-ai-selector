# Business API Reference

> API Reference для Business API (Port 8000)

## Base URL

```
http://localhost:8000/api/v1
```

## Interactive Documentation

При запущенных сервисах:

- **Swagger UI:** <http://localhost:8000/docs>
- **ReDoc:** <http://localhost:8000/redoc>

---

## Endpoints

### POST /prompts/process

Обработать промпт и получить ответ от лучшей AI-модели.

#### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Текст промпта |
| `user_id` | string | No | ID пользователя (default: "anonymous") |

#### Request Example

```bash
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Напиши короткое стихотворение об AI",
    "user_id": "telegram_123456"
  }'
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `prompt_text` | string | Исходный промпт |
| `response_text` | string | Ответ AI |
| `selected_model_name` | string | Имя выбранной модели |
| `selected_model_provider` | string | Провайдер |
| `response_time_seconds` | number | Время ответа (секунды) |
| `success` | boolean | Успешность |
| `error_message` | string | Сообщение об ошибке (если есть) |

#### Response Example (Success)

```json
{
  "prompt_text": "Напиши короткое стихотворение об AI",
  "response_text": "В мире битов и цифр живёт разум стальной...",
  "selected_model_name": "Gemini 2.5 Flash",
  "selected_model_provider": "GoogleGemini",
  "response_time_seconds": 1.234,
  "success": true,
  "error_message": null
}
```

#### Response Example (Error)

```json
{
  "prompt_text": "Test",
  "response_text": null,
  "selected_model_name": "Gemini 2.5 Flash",
  "selected_model_provider": "GoogleGemini",
  "response_time_seconds": 5.678,
  "success": false,
  "error_message": "API rate limit exceeded"
}
```

#### Errors

| Status | Description |
|--------|-------------|
| 503 | All AI providers failed |
| 422 | Validation error (invalid request) |

---

### GET /models/stats

Получить статистику надёжности всех AI-моделей.

#### Request

Параметры отсутствуют.

#### Request Example

```bash
curl http://localhost:8000/api/v1/models/stats
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `models` | array | Список моделей со статистикой |
| `total_models` | integer | Общее количество моделей |

Каждая модель:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | ID модели |
| `name` | string | Имя модели |
| `provider` | string | Провайдер |
| `reliability_score` | number | Оценка надёжности (0.0 - 1.0) |
| `success_rate` | number | Процент успешных запросов |
| `average_response_time` | number | Среднее время ответа (сек) |
| `is_active` | boolean | Активна ли модель |

#### Response Example

```json
{
  "models": [
    {
      "id": 1,
      "name": "Gemini 2.5 Flash",
      "provider": "GoogleGemini",
      "reliability_score": 0.92,
      "success_rate": 0.95,
      "average_response_time": 1.5,
      "is_active": true
    },
    {
      "id": 2,
      "name": "Llama 3.3 70B (Groq)",
      "provider": "Groq",
      "reliability_score": 0.88,
      "success_rate": 0.90,
      "average_response_time": 0.8,
      "is_active": true
    }
  ],
  "total_models": 6
}
```

---

### POST /providers/test

Протестировать все AI-провайдеры и обновить статистику.

#### Request

Параметры отсутствуют.

#### Request Example

```bash
curl -X POST http://localhost:8000/api/v1/providers/test
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `results` | array | Результаты тестирования |
| `total_tested` | integer | Количество протестированных |
| `successful` | integer | Количество успешных |
| `failed` | integer | Количество неудачных |

Каждый результат:

| Field | Type | Description |
|-------|------|-------------|
| `provider` | string | Имя провайдера |
| `model_name` | string | Имя модели |
| `success` | boolean | Успешен ли тест |
| `response_time` | number | Время ответа (если успех) |
| `error` | string | Ошибка (если неудача) |

#### Response Example

```json
{
  "results": [
    {
      "provider": "GoogleGemini",
      "model_name": "Gemini 2.5 Flash",
      "success": true,
      "response_time": 1.234,
      "error": null
    },
    {
      "provider": "Groq",
      "model_name": "Llama 3.3 70B (Groq)",
      "success": true,
      "response_time": 0.567,
      "error": null
    },
    {
      "provider": "HuggingFace",
      "model_name": "Llama 3 8B (HuggingFace)",
      "success": false,
      "response_time": null,
      "error": "Model is currently loading"
    }
  ],
  "total_tested": 6,
  "successful": 5,
  "failed": 1
}
```

---

### GET /health

Проверка здоровья сервиса.

#### Request Example

```bash
curl http://localhost:8000/health
```

#### Response Example

```json
{
  "status": "healthy",
  "service": "business-api",
  "version": "1.0.0"
}
```

---

## Python Client Example

```python
import httpx


async def process_prompt(prompt: str, user_id: str = "anonymous") -> dict:
    """Обработать промпт через Business API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/prompts/process",
            json={"prompt": prompt, "user_id": user_id},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()


async def get_models_stats() -> dict:
    """Получить статистику моделей."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/v1/models/stats",
        )
        response.raise_for_status()
        return response.json()


# Использование
import asyncio

result = asyncio.run(process_prompt("Hello, AI!"))
print(result["response_text"])
```

---

## Related Documentation

- [Data API Reference](data-api.md) - API для работы с данными
- [Errors](errors.md) - Коды ошибок
- [../project/ai-providers.md](../project/ai-providers.md) - AI провайдеры
