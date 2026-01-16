# API Errors

> Документация по ошибкам API Free AI Selector.

## HTTP Status Codes

### Success Codes

| Code | Description |
|------|-------------|
| 200 | OK - Запрос выполнен успешно |
| 201 | Created - Ресурс создан |

### Client Error Codes

| Code | Description | Example |
|------|-------------|---------|
| 400 | Bad Request | Некорректный JSON |
| 404 | Not Found | Модель не найдена |
| 422 | Validation Error | Отсутствует обязательное поле |

### Server Error Codes

| Code | Description | Example |
|------|-------------|---------|
| 500 | Internal Server Error | Непредвиденная ошибка |
| 503 | Service Unavailable | Все AI провайдеры недоступны |

---

## Error Response Format

### Standard Error

```json
{
  "detail": "Error message here"
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

---

## Business API Errors

### POST /prompts/process

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| All AI providers failed | 503 | Все провайдеры вернули ошибку | Проверить API ключи, попробовать позже |
| No active models | 503 | Нет активных моделей в БД | Запустить `make seed` |
| Field required | 422 | Отсутствует поле `prompt` | Добавить поле в запрос |

### Response при ошибке провайдера

Если запрос к провайдеру неудачен, но fallback сработал:

```json
{
  "prompt_text": "Hello",
  "response_text": "Hi there!",
  "selected_model_name": "Llama 3.3 70B (Groq)",
  "selected_model_provider": "Groq",
  "response_time_seconds": 0.8,
  "success": true,
  "error_message": null
}
```

Если все провайдеры неудачны:

```json
{
  "detail": "All AI providers failed: Rate limit exceeded"
}
```

---

## Data API Errors

### GET /models/{model_id}

| Error | Status | Cause |
|-------|--------|-------|
| Model not found | 404 | ID не существует |

### POST /models

| Error | Status | Cause |
|-------|--------|-------|
| Name already exists | 400 | Модель с таким именем уже есть |
| Field required | 422 | Отсутствует обязательное поле |

---

## AI Provider Errors

### Rate Limit (429)

```json
{
  "detail": "Rate limit exceeded for DeepSeek"
}
```

**Решение:** Подождать или использовать другую модель (автоматически через fallback).

### Authentication (401)

```json
{
  "detail": "Invalid API key for Groq"
}
```

**Решение:** Проверить API ключ в `.env`.

### Timeout

```json
{
  "detail": "Request timeout for Cerebras"
}
```

**Решение:** Провайдер медленный, система переключится на fallback.

---

## Error Handling in Code

### Business API

```python
# services/free-ai-selector-business-api/app/api/v1/prompts.py

from fastapi import HTTPException, status

@router.post("/process")
async def process_prompt(request: ProcessPromptRequest):
    try:
        response = await use_case.execute(domain_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All AI providers failed: {str(e)}",
        )
    return response
```

### Client-side Handling

```python
import httpx

async def process_prompt(prompt: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/v1/prompts/process",
                json={"prompt": prompt},
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            print("All providers are down, try later")
        elif e.response.status_code == 422:
            print("Invalid request:", e.response.json())
        raise
    except httpx.TimeoutException:
        print("Request timed out")
        raise
```

---

## Troubleshooting

### Ошибка 503: All AI providers failed

1. Проверить API ключи в `.env`
2. Проверить доступность провайдеров: `curl -X POST http://localhost:8000/api/v1/providers/test`
3. Проверить логи: `make logs-business`

### Ошибка 422: Validation Error

1. Проверить формат запроса
2. Убедиться что все обязательные поля присутствуют
3. Проверить типы данных

### Ошибка 500: Internal Server Error

1. Проверить логи: `make logs`
2. Проверить подключение к Data API
3. Проверить подключение к БД

---

## Related Documentation

- [Business API](business-api.md) - API Reference
- [Data API](data-api.md) - Data API Reference
- [../operations/troubleshooting.md](../operations/troubleshooting.md) - Troubleshooting Guide
