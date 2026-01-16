# Data API Reference

> API Reference для Data API (Port 8001)

## Base URL

```
http://localhost:8001/api/v1
```

## Interactive Documentation

При запущенных сервисах:

- **Swagger UI:** <http://localhost:8002/docs> (external port)
- **ReDoc:** <http://localhost:8002/redoc>

---

## Models Endpoints

### GET /models

Получить список AI-моделей.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `active_only` | boolean | false | Только активные модели |

#### Request Example

```bash
curl "http://localhost:8001/api/v1/models?active_only=true"
```

#### Response Example

```json
{
  "models": [
    {
      "id": 1,
      "name": "DeepSeek Chat",
      "provider": "DeepSeek",
      "api_endpoint": "https://api.deepseek.com/v1",
      "success_count": 150,
      "failure_count": 10,
      "total_response_time": 225.5,
      "request_count": 160,
      "last_checked": "2025-01-20T10:30:00Z",
      "is_active": true,
      "reliability_score": 0.92,
      "success_rate": 0.9375,
      "average_response_time": 1.409
    }
  ],
  "total": 6
}
```

---

### GET /models/{model_id}

Получить модель по ID.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Request Example

```bash
curl http://localhost:8001/api/v1/models/1
```

#### Response Example

```json
{
  "id": 1,
  "name": "DeepSeek Chat",
  "provider": "DeepSeek",
  "api_endpoint": "https://api.deepseek.com/v1",
  "success_count": 150,
  "failure_count": 10,
  "total_response_time": 225.5,
  "request_count": 160,
  "last_checked": "2025-01-20T10:30:00Z",
  "is_active": true,
  "reliability_score": 0.92,
  "success_rate": 0.9375,
  "average_response_time": 1.409,
  "created_at": "2025-01-17T12:00:00Z",
  "updated_at": "2025-01-20T10:30:00Z"
}
```

#### Errors

| Status | Description |
|--------|-------------|
| 404 | Model not found |

---

### POST /models

Создать новую AI-модель.

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Уникальное имя модели |
| `provider` | string | Yes | Имя провайдера |
| `api_endpoint` | string | Yes | URL API |
| `is_active` | boolean | No | Активна ли (default: true) |

#### Request Example

```bash
curl -X POST http://localhost:8001/api/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Model",
    "provider": "NewProvider",
    "api_endpoint": "https://api.newprovider.com/v1",
    "is_active": true
  }'
```

#### Response Example

```json
{
  "id": 7,
  "name": "New Model",
  "provider": "NewProvider",
  "api_endpoint": "https://api.newprovider.com/v1",
  "success_count": 0,
  "failure_count": 0,
  "total_response_time": 0.0,
  "request_count": 0,
  "last_checked": null,
  "is_active": true,
  "reliability_score": 0.4,
  "success_rate": 0.0,
  "average_response_time": 0.0,
  "created_at": "2025-01-20T12:00:00Z",
  "updated_at": "2025-01-20T12:00:00Z"
}
```

---

### POST /models/{model_id}/increment-success

Увеличить счётчик успешных запросов.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `response_time` | number | No | Время ответа в секундах |

#### Request Example

```bash
curl -X POST http://localhost:8001/api/v1/models/1/increment-success \
  -H "Content-Type: application/json" \
  -d '{"response_time": 1.5}'
```

#### Response

```json
{"status": "success"}
```

---

### POST /models/{model_id}/increment-failure

Увеличить счётчик неудачных запросов.

#### Request Example

```bash
curl -X POST http://localhost:8001/api/v1/models/1/increment-failure
```

#### Response

```json
{"status": "success"}
```

---

### PATCH /models/{model_id}/active

Установить статус активности модели.

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `is_active` | boolean | Yes | Новый статус |

#### Request Example

```bash
curl -X PATCH http://localhost:8001/api/v1/models/1/active \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

---

## History Endpoints

### POST /history

Создать запись в истории промптов.

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | Yes | ID пользователя |
| `prompt_text` | string | Yes | Текст промпта |
| `selected_model_id` | integer | Yes | ID модели |
| `response_text` | string | No | Текст ответа |
| `response_time` | number | Yes | Время ответа |
| `success` | boolean | Yes | Успешен ли |
| `error_message` | string | No | Сообщение об ошибке |

#### Request Example

```bash
curl -X POST http://localhost:8001/api/v1/history \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "telegram_123456",
    "prompt_text": "Hello AI",
    "selected_model_id": 1,
    "response_text": "Hello! How can I help?",
    "response_time": 1.5,
    "success": true
  }'
```

---

### GET /history/user/{user_id}

Получить историю пользователя.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Количество записей |
| `offset` | integer | 0 | Смещение |

#### Request Example

```bash
curl "http://localhost:8001/api/v1/history/user/telegram_123456?limit=5"
```

---

### GET /history/model/{model_id}

Получить историю для модели.

#### Request Example

```bash
curl "http://localhost:8001/api/v1/history/model/1?limit=10"
```

---

### GET /history

Получить последние записи истории.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Количество записей |
| `success_only` | boolean | false | Только успешные |

---

### GET /history/statistics/period

Получить статистику за период.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | datetime | Yes | Начало периода |
| `end_date` | datetime | Yes | Конец периода |

#### Request Example

```bash
curl "http://localhost:8001/api/v1/history/statistics/period?start_date=2025-01-01&end_date=2025-01-31"
```

---

## Health Endpoint

### GET /health

```bash
curl http://localhost:8001/health
```

```json
{
  "status": "healthy",
  "service": "data-api",
  "database": "connected"
}
```

---

## Related Documentation

- [Business API Reference](business-api.md) - API для обработки промптов
- [Errors](errors.md) - Коды ошибок
- [../project/database-schema.md](../project/database-schema.md) - Схема БД
