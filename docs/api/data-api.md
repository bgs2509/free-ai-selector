# Data API Reference

> API Reference для Data API (Port 8001) — CRUD операции для AI-моделей и истории промптов.

## Base URL

```
http://localhost:8001
```

## Interactive Documentation

При запущенных сервисах:

- **Swagger UI:** <http://localhost:8001/docs>
- **ReDoc:** <http://localhost:8001/redoc>

## Authentication

Data API не имеет аутентификации — предназначен только для внутренних вызовов от Business API и Health Worker. Не должен быть доступен извне.

---

## Root Endpoints

### GET /

Информация о сервисе.

#### Response Example

```json
{
  "service": "free-ai-selector-data-postgres-api",
  "version": "1.0.0",
  "environment": "development",
  "docs": "/docs",
  "health": "/health"
}
```

---

### GET /health

Проверка здоровья сервиса и подключения к БД.

#### Response Model: `HealthCheckResponse`

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"healthy"` или `"unhealthy"` |
| `service` | string | Имя сервиса |
| `version` | string | Версия сервиса |
| `database` | string | Статус подключения к PostgreSQL |

#### Response Example

```json
{
  "status": "healthy",
  "service": "free-ai-selector-data-postgres-api",
  "version": "1.0.0",
  "database": "healthy"
}
```

---

## Models Endpoints

Prefix: `/api/v1/models`

### GET /api/v1/models

Получить список AI-моделей с опциональными recent-метриками.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `active_only` | boolean | `true` | Только активные модели |
| `available_only` | boolean | `false` | Исключить модели в cooldown (`available_at > now()`) — F012 |
| `include_recent` | boolean | `false` | Включить recent-метрики из `prompt_history` — F010 |
| `window_days` | integer | `7` | Размер окна в днях для recent-метрик (1–30) |

#### Request Examples

```bash
# Все активные модели
curl "http://localhost:8001/api/v1/models"

# С recent-метриками за 14 дней
curl "http://localhost:8001/api/v1/models?include_recent=true&window_days=14"

# Только доступные модели (без rate-limited)
curl "http://localhost:8001/api/v1/models?available_only=true"

# Все модели включая неактивные
curl "http://localhost:8001/api/v1/models?active_only=false"
```

#### Response: `List[AIModelResponse]`

```json
[
  {
    "id": 1,
    "name": "DeepSeek Chat",
    "provider": "DeepSeek",
    "api_endpoint": "https://api.deepseek.com/v1",
    "success_count": 150,
    "failure_count": 10,
    "total_response_time": 225.5,
    "request_count": 160,
    "last_checked": "2026-02-25T10:30:00Z",
    "is_active": true,
    "created_at": "2026-01-17T12:00:00Z",
    "updated_at": "2026-02-25T10:30:00Z",
    "api_format": "openai",
    "available_at": null,
    "success_rate": 0.9375,
    "average_response_time": 1.409,
    "speed_score": 0.86,
    "reliability_score": 0.9065,
    "recent_success_rate": 0.95,
    "recent_request_count": 20,
    "recent_reliability_score": 0.92,
    "effective_reliability_score": 0.92,
    "decision_reason": "recent_score"
  }
]
```

> **Примечание**: Поля `recent_*`, `effective_reliability_score` и `decision_reason` возвращают `null`, если `include_recent=false` или недостаточно данных (< 3 запросов в окне).

---

### GET /api/v1/models/{model_id}

Получить модель по ID.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Request Example

```bash
curl http://localhost:8001/api/v1/models/1
```

#### Response: `AIModelResponse`

Та же структура, что и в `GET /api/v1/models`, но без recent-метрик (всегда `null`).

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `AI model with ID {model_id} not found` |

---

### POST /api/v1/models

Создать новую AI-модель.

#### Request Body: `AIModelCreate`

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | string | **Yes** | 1–255 символов | Уникальное имя модели |
| `provider` | string | **Yes** | 1–100 символов | Имя провайдера |
| `api_endpoint` | string | **Yes** | 1–500 символов | URL API endpoint |
| `is_active` | boolean | No | — | Активна ли модель (default: `true`) |

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

#### Response: `AIModelResponse` (201 Created)

Новая модель с нулевой статистикой.

#### Errors

| Status | Description |
|--------|-------------|
| 409 | `AI model with name '{name}' already exists` |
| 422 | Validation Error — отсутствует обязательное поле |

---

### PUT /api/v1/models/{model_id}/stats

Обновить статистику модели (полная перезапись).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Request Body: `AIModelStatsUpdate`

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `success_count` | integer | No | >= 0 | Количество успешных запросов |
| `failure_count` | integer | No | >= 0 | Количество неудачных запросов |
| `total_response_time` | decimal | No | >= 0 | Суммарное время ответов (секунды) |
| `request_count` | integer | No | >= 0 | Общее количество запросов |

#### Request Example

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

#### Response: `AIModelResponse` (200 OK)

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `AI model with ID {model_id} not found` |

---

### POST /api/v1/models/{model_id}/increment-success

Инкрементировать счётчик успешных запросов (+1 success, +response_time).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `response_time` | float | **Yes** | Время ответа в секундах |

#### Request Example

```bash
curl -X POST "http://localhost:8001/api/v1/models/1/increment-success?response_time=1.5"
```

#### Response: `AIModelResponse` (200 OK)

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `AI model with ID {model_id} not found` |

---

### POST /api/v1/models/{model_id}/increment-failure

Инкрементировать счётчик неудачных запросов (+1 failure, +response_time).

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `response_time` | float | **Yes** | Время ответа в секундах |

#### Request Example

```bash
curl -X POST "http://localhost:8001/api/v1/models/1/increment-failure?response_time=5.0"
```

#### Response: `AIModelResponse` (200 OK)

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `AI model with ID {model_id} not found` |

---

### PATCH /api/v1/models/{model_id}/active

Установить статус активности модели.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `is_active` | boolean | **Yes** | Новый статус активности |

#### Request Example

```bash
curl -X PATCH "http://localhost:8001/api/v1/models/1/active?is_active=false"
```

#### Response: `AIModelResponse` (200 OK)

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `AI model with ID {model_id} not found` |

---

### PATCH /api/v1/models/{model_id}/availability

Установить cooldown для модели (F012: Rate Limit Handling).

Когда провайдер возвращает 429, устанавливается `available_at = now() + retry_after_seconds`. Модель исключается из выбора до истечения cooldown.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Query Parameters

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `retry_after_seconds` | integer | **Yes** | >= 0 | Секунд до доступности (0 = сброс cooldown) |

#### Request Example

```bash
# Установить cooldown на 60 секунд
curl -X PATCH "http://localhost:8001/api/v1/models/1/availability?retry_after_seconds=60"

# Сбросить cooldown
curl -X PATCH "http://localhost:8001/api/v1/models/1/availability?retry_after_seconds=0"
```

#### Response: `AIModelResponse` (200 OK)

Модель с обновлённым полем `available_at`.

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `AI model with ID {model_id} not found` |

---

## History Endpoints

Prefix: `/api/v1/history`

### POST /api/v1/history

Создать запись в истории промптов.

#### Request Body: `PromptHistoryCreate`

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `user_id` | string | **Yes** | 1–255 символов | ID пользователя (Telegram или API) |
| `prompt_text` | string | **Yes** | min 1 символ | Текст промпта |
| `selected_model_id` | integer | **Yes** | > 0 | ID выбранной модели |
| `response_text` | string | No | — | Текст ответа AI |
| `response_time` | decimal | **Yes** | >= 0 | Время ответа в секундах |
| `success` | boolean | **Yes** | — | Успешен ли запрос |
| `error_message` | string | No | — | Сообщение об ошибке |

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

#### Response: `PromptHistoryResponse` (201 Created)

```json
{
  "id": 42,
  "user_id": "telegram_123456",
  "prompt_text": "Hello AI",
  "selected_model_id": 1,
  "response_text": "Hello! How can I help?",
  "response_time": 1.5,
  "success": true,
  "error_message": null,
  "created_at": "2026-02-25T14:30:00Z"
}
```

---

### GET /api/v1/history/{history_id}

Получить запись истории по ID.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `history_id` | integer | ID записи |

#### Request Example

```bash
curl http://localhost:8001/api/v1/history/42
```

#### Response: `PromptHistoryResponse` (200 OK)

#### Errors

| Status | Description |
|--------|-------------|
| 404 | `History record with ID {history_id} not found` |

---

### GET /api/v1/history/user/{user_id}

Получить историю промптов пользователя.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | string | ID пользователя |

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `100` | 1–1000 | Максимум записей |
| `offset` | integer | `0` | >= 0 | Смещение |

#### Request Example

```bash
curl "http://localhost:8001/api/v1/history/user/telegram_123456?limit=50&offset=0"
```

#### Response: `List[PromptHistoryResponse]` (200 OK)

Записи отсортированы по `created_at DESC`.

---

### GET /api/v1/history/model/{model_id}

Получить историю промптов для конкретной модели.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | integer | ID модели |

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `100` | 1–1000 | Максимум записей |
| `offset` | integer | `0` | >= 0 | Смещение |

#### Request Example

```bash
curl "http://localhost:8001/api/v1/history/model/1?limit=100&offset=0"
```

#### Response: `List[PromptHistoryResponse]` (200 OK)

Записи отсортированы по `created_at DESC`.

---

### GET /api/v1/history

Получить последние записи истории.

#### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `100` | 1–1000 | Максимум записей |
| `success_only` | boolean | `false` | — | Только успешные запросы |

#### Request Example

```bash
curl "http://localhost:8001/api/v1/history?limit=50&success_only=true"
```

#### Response: `List[PromptHistoryResponse]` (200 OK)

Записи отсортированы по `created_at DESC`.

---

### GET /api/v1/history/statistics/period

Получить агрегированную статистику за период.

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | datetime | **Yes** | Начало периода (ISO 8601) |
| `end_date` | datetime | **Yes** | Конец периода (ISO 8601) |
| `model_id` | integer | No | Фильтр по модели |

#### Request Example

```bash
# Общая статистика за январь
curl "http://localhost:8001/api/v1/history/statistics/period?start_date=2026-01-01T00:00:00&end_date=2026-01-31T23:59:59"

# Статистика для модели #1
curl "http://localhost:8001/api/v1/history/statistics/period?start_date=2026-02-01T00:00:00&end_date=2026-02-28T23:59:59&model_id=1"
```

#### Response: `ModelStatisticsResponse` (200 OK)

```json
{
  "total_requests": 500,
  "successful_requests": 475,
  "failed_requests": 25,
  "success_rate": 0.95
}
```

---

## Schemas Reference

### AIModelResponse

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | ID модели |
| `name` | string | Имя модели |
| `provider` | string | Имя провайдера |
| `api_endpoint` | string | URL API endpoint |
| `success_count` | integer | Кумулятивное количество успехов |
| `failure_count` | integer | Кумулятивное количество ошибок |
| `total_response_time` | decimal | Суммарное время ответов (сек) |
| `request_count` | integer | Общее количество запросов |
| `last_checked` | datetime / null | Время последней проверки health |
| `is_active` | boolean | Модель активна |
| `created_at` | datetime | Дата создания |
| `updated_at` | datetime | Дата обновления |
| `api_format` | string | Формат API: `openai`, `gemini`, `cohere`, `huggingface`, `cloudflare` (F008) |
| `available_at` | datetime / null | Время окончания cooldown (F012). `null` = доступна |
| **Computed (long-term)** | | |
| `success_rate` | float | Доля успешных запросов (0.0–1.0) |
| `average_response_time` | float | Среднее время ответа (сек) |
| `speed_score` | float | Оценка скорости (0.0–1.0) |
| `reliability_score` | float | Оценка надёжности: `success_rate × 0.6 + speed_score × 0.4` |
| **Recent metrics (F010)** | | |
| `recent_success_rate` | float / null | Success rate за окно (null если < 3 запросов) |
| `recent_request_count` | integer / null | Количество запросов в окне |
| `recent_reliability_score` | float / null | Reliability score за окно |
| `effective_reliability_score` | float / null | Score используемый для выбора модели |
| `decision_reason` | string / null | `"recent_score"` или `"fallback"` |

### PromptHistoryResponse

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | ID записи |
| `user_id` | string | ID пользователя |
| `prompt_text` | string | Текст промпта |
| `selected_model_id` | integer | ID выбранной модели |
| `response_text` | string / null | Текст ответа AI |
| `response_time` | decimal | Время ответа (сек) |
| `success` | boolean | Успешность |
| `error_message` | string / null | Сообщение об ошибке |
| `created_at` | datetime | Дата создания |

### ModelStatisticsResponse

| Field | Type | Description |
|-------|------|-------------|
| `total_requests` | integer | Общее количество запросов |
| `successful_requests` | integer | Успешных запросов |
| `failed_requests` | integer | Неудачных запросов |
| `success_rate` | float | Доля успешных (0.0–1.0) |

---

## Request Tracing

Все запросы поддерживают трассировку через заголовки:

| Header | Direction | Description |
|--------|-----------|-------------|
| `X-Request-ID` | Request / Response | ID запроса (генерируется если не передан) |
| `X-Correlation-ID` | Request | ID корреляции для cross-service tracing |

```bash
curl -H "X-Request-ID: my-trace-123" http://localhost:8001/api/v1/models
# Response header: X-Request-ID: my-trace-123
```

---

## Related Documentation

- [Business API Reference](business-api.md) — API для обработки промптов
- [Errors](errors.md) — Коды ошибок и ErrorResponse
- [Examples](examples.md) — Примеры использования API
- [../project/database-schema.md](../project/database-schema.md) — Схема БД
