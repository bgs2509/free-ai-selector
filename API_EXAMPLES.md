# API Examples

> **Free AI Selector** - REST API usage examples

## Base URLs

- **Business API**: `http://localhost:8000`
- **Data API**: `http://localhost:8001`

## Business API Examples

### 1. Process Prompt

Send a prompt and get AI-generated response with automatic model selection.

**Endpoint**: `POST /api/v1/prompts/process`

**Request**:
```bash
curl -X POST http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a short poem about artificial intelligence"
  }'
```

**Response**:
```json
{
  "prompt": "Write a short poem about artificial intelligence",
  "response": "In circuits deep and code so bright,\nAI learns through day and night...",
  "selected_model": "HuggingFace Meta-Llama-3-8B-Instruct",
  "provider": "HuggingFace",
  "response_time_seconds": 2.34,
  "success": true
}
```

### 2. Get Models Statistics

View reliability scores and performance metrics for all AI models.

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
      "name": "HuggingFace Meta-Llama-3-8B-Instruct",
      "provider": "HuggingFace",
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
  "total_models": 2
}
```

### 3. Health Check

Check if Business API is healthy and can reach Data API.

**Endpoint**: `GET /health`

**Request**:
```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "aimanager_business_api",
  "version": "1.0.0",
  "data_api_connection": "healthy"
}
```

## Data API Examples

### 1. List All AI Models

Get all AI models with statistics.

**Endpoint**: `GET /api/v1/models`

**Request**:
```bash
curl http://localhost:8001/api/v1/models?active_only=true
```

**Response**:
```json
[
  {
    "id": 1,
    "name": "HuggingFace Meta-Llama-3-8B-Instruct",
    "provider": "HuggingFace",
    "api_endpoint": "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct",
    "success_count": 143,
    "failure_count": 7,
    "total_response_time": 315.5,
    "request_count": 150,
    "last_checked": "2025-01-17T14:30:00Z",
    "is_active": true,
    "created_at": "2025-01-17T10:00:00Z",
    "updated_at": "2025-01-17T14:30:00Z",
    "success_rate": 0.953,
    "average_response_time": 2.103,
    "speed_score": 0.790,
    "reliability_score": 0.888
  }
]
```

### 2. Get Specific Model

Fetch a single model by ID.

**Endpoint**: `GET /api/v1/models/{model_id}`

**Request**:
```bash
curl http://localhost:8001/api/v1/models/1
```

**Response**: Same structure as above, single object.

### 3. Update Model Statistics

Manually update model statistics (normally done automatically).

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

### 4. Increment Success Count

Record a successful request (used by Business API internally).

**Endpoint**: `POST /api/v1/models/{model_id}/increment-success`

**Request**:
```bash
curl -X POST "http://localhost:8001/api/v1/models/1/increment-success?response_time=2.5"
```

### 5. Increment Failure Count

Record a failed request.

**Endpoint**: `POST /api/v1/models/{model_id}/increment-failure`

**Request**:
```bash
curl -X POST "http://localhost:8001/api/v1/models/1/increment-failure?response_time=5.0"
```

### 6. Get Prompt History

View recent prompt processing history.

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
    "created_at": "2025-01-17T14:25:00Z"
  }
]
```

### 7. Get User History

View prompt history for a specific user.

**Endpoint**: `GET /api/v1/history/user/{user_id}`

**Request**:
```bash
curl "http://localhost:8001/api/v1/history/user/telegram_123456?limit=50"
```

### 8. Get Model History

View all prompts processed by a specific model.

**Endpoint**: `GET /api/v1/history/model/{model_id}`

**Request**:
```bash
curl "http://localhost:8001/api/v1/history/model/1?limit=100"
```

### 9. Create Prompt History

Manually create a history record (normally done by Business API).

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

## Python Client Examples

### Using httpx

```python
import asyncio
import httpx

async def process_prompt(prompt: str):
    """Process a prompt using Business API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/prompts/process",
            json={"prompt": prompt},
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()

async def get_models_stats():
    """Get models statistics."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/v1/models/stats")
        response.raise_for_status()
        return response.json()

# Usage
async def main():
    result = await process_prompt("Explain quantum computing in simple terms")
    print(f"Response: {result['response']}")
    print(f"Model used: {result['selected_model']}")
    print(f"Time: {result['response_time_seconds']}s")

    stats = await get_models_stats()
    print(f"Total models: {stats['total_models']}")

asyncio.run(main())
```

## Error Handling

### Common Error Responses

**400 Bad Request**:
```json
{
  "detail": "Prompt text is required"
}
```

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

**500 Internal Server Error**:
```json
{
  "detail": "Failed to process prompt: All AI providers failed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "error_type": "Exception"
}
```

**503 Service Unavailable**:
```json
{
  "detail": "No active AI models available"
}
```

## Rate Limiting

Business API has rate limiting enabled (configurable via `.env`):

- **Default**: 100 requests per 60 seconds per IP
- **Header**: `X-RateLimit-Remaining` shows remaining requests
- **429 Response**: When limit exceeded

```bash
curl -i http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# Response headers:
# X-RateLimit-Remaining: 99
```

## Request Tracing

All requests are tracked with a request ID for debugging:

```bash
curl -H "X-Request-ID: my-custom-id-123" \
  http://localhost:8000/api/v1/prompts/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'

# Response includes same request ID in header:
# X-Request-ID: my-custom-id-123
```

Check logs to trace the request:
```bash
docker-compose logs | grep "my-custom-id-123"
```

## OpenAPI Documentation

Interactive API documentation available at:

- **Business API Swagger**: http://localhost:8000/docs
- **Business API ReDoc**: http://localhost:8000/redoc
- **Data API Swagger**: http://localhost:8001/docs
- **Data API ReDoc**: http://localhost:8001/redoc

## Telegram Bot Commands

**Start bot**: `/start`
**Get help**: `/help`
**View stats**: `/stats`
**Process prompt**: Just send any text message

Example:
```
User: Write a haiku about programming
Bot: Code flows like a stream,
     Bugs dance in moonlit night,
     Debug until dawn.

     🤖 Model: HuggingFace Meta-Llama-3-8B-Instruct
     🔧 Provider: HuggingFace
     ⚡ Time: 2.1 sec
```
