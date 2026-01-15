---
feature_id: "F011-B"
feature_name: "system-prompts-json-response"
title: "Research Report: System Prompts & JSON Response Support"
created: "2026-01-15"
author: "AI (Researcher)"
type: "research"
status: "Draft"
version: 1.0
mode: "FEATURE"

prerequisite_features: ["F011-A"]
f011a_status: "VALIDATED"
services: ["free-ai-selector-business-api"]
files_analyzed: 8
---

# Research Report: System Prompts & JSON Response Support (F011-B)

**Feature ID**: F011-B
**Версия**: 1.0
**Дата**: 2026-01-15
**Автор**: AI Agent (Исследователь)
**Режим**: FEATURE
**Предусловия**: F011-A (VALIDATED)

---

## Executive Summary

Проведён анализ кодовой базы для реализации поддержки `system_prompt` и `response_format` параметров в free-ai-selector API. Исследование показало:

✅ **Архитектура готова** — DDD/Hexagonal разделение слоёв позволяет чисто добавить новые параметры
✅ **F011-A завершена** — 14 OpenAI-compatible провайдеров унифицированы, GoogleGemini и Cohere удалены
✅ **Базовый интерфейс расширяем** — метод `AIProviderBase.generate()` принимает `**kwargs` для новых параметров
✅ **Без breaking changes** — новые поля будут опциональными (backward compatible)
⚠️ **Требуется provider-specific логика** — не все провайдеры поддерживают `response_format`

**Основной вывод**: Реализация F011-B возможна с минимальными изменениями в 4 слоях (API → Use Case → Providers → DTO).

---

## 1. Анализ существующей архитектуры

### 1.1 Структура проекта (DDD/Hexagonal)

```
services/free-ai-selector-business-api/
├── app/
│   ├── api/v1/                      # API Layer (FastAPI endpoints)
│   │   ├── endpoints/prompts.py     # POST /api/v1/prompts/process
│   │   └── schemas.py               # Pydantic Request/Response schemas
│   │
│   ├── application/use_cases/       # Application Layer (бизнес-логика)
│   │   └── process_prompt.py        # ProcessPromptUseCase
│   │
│   ├── domain/                      # Domain Layer (DTOs)
│   │   └── models.py                # PromptRequest, PromptResponse, AIModelInfo
│   │
│   └── infrastructure/              # Infrastructure Layer
│       └── ai_providers/            # 14 AI провайдеров
│           ├── base.py              # AIProviderBase (abstract)
│           ├── registry.py          # ProviderRegistry (F008 SSOT)
│           ├── cloudflare.py        # Cloudflare (special format)
│           ├── groq.py              # Groq (OpenAI-compatible)
│           ├── sambanova.py         # SambaNova (OpenAI-compatible)
│           └── ... (11 других)      # Все OpenAI-compatible
```

**Ключевая особенность**: HTTP-only архитектура — Business API → Data API → PostgreSQL (никогда напрямую к БД).

---

### 1.2 Поток данных (AS-IS)

```
┌─────────────┐     HTTP      ┌──────────────────┐    provider     ┌───────────────┐
│   Client    │ ────────────▶ │  Business API    │ ──.generate()──▶│ AI Provider   │
│             │  POST /prompt │  (ProcessPrompt  │                 │ (Cloudflare/  │
│             │               │   UseCase)       │                 │  Groq/etc)    │
└─────────────┘               └──────────────────┘                 └───────────────┘
       │                             │                                      │
       │ JSON                        │ HTTP (Data API)                      │ HTTP
       ▼                             ▼                                      ▼
 {                             GET /models                          POST /chat/completions
   "prompt": "..."             (reliability_score)                  {
 }                                                                    "messages": [
                                                                        {"role": "user",
                                                                         "content": "..."}
                                                                      ]
                                                                    }
                                                                           ↓
                                                                      JSON response
```

**Параметры сейчас:**
- API принимает: `prompt: str` (1-10000 символов)
- Use Case вызывает: `provider.generate(prompt_text)` без дополнительных параметров
- Провайдеры используют: defaults из kwargs (`max_tokens=512`, `temperature=0.7`)

---

## 2. Детальный анализ компонентов

### 2.1 API Layer — Pydantic Schemas

**Файл**: `app/api/v1/schemas.py`

**Текущие схемы:**

```python
class ProcessPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
```

**ProcessPromptResponse** (без изменений):
```python
class ProcessPromptResponse(BaseModel):
    prompt: str
    response: str
    selected_model: str
    provider: str
    response_time_seconds: Decimal
    success: bool
```

**Рекомендация**: Добавить опциональные поля `system_prompt` и `response_format` в `ProcessPromptRequest`.

---

### 2.2 Domain Layer — DTOs

**Файл**: `app/domain/models.py`

**Текущие dataclasses:**

```python
@dataclass
class PromptRequest:
    user_id: str
    prompt_text: str
    # Новые поля (F011-B):
    # system_prompt: Optional[str] = None
    # response_format: Optional[dict] = None

@dataclass
class PromptResponse:
    prompt_text: str
    response_text: str
    selected_model_name: str
    selected_model_provider: str
    response_time: Decimal
    success: bool
    error_message: Optional[str] = None
```

**Рекомендация**: Расширить `PromptRequest` двумя опциональными полями.

---

### 2.3 Application Layer — Use Case

**Файл**: `app/application/use_cases/process_prompt.py`

**Текущая реализация:**

```python
class ProcessPromptUseCase:
    async def execute(self, request: PromptRequest) -> PromptResponse:
        # 1. Получить активные модели
        models = await self.data_api_client.get_all_models(active_only=True)

        # 2. Выбрать лучшую (effective_reliability_score)
        best_model = self._select_best_model(models)

        # 3. Получить провайдер и вызвать generate
        provider = self._get_provider_for_model(best_model)
        response_text = await provider.generate(request.prompt_text)  # ← БЕЗ kwargs!

        # 4. Обновить статистику + записать историю
        await self.data_api_client.increment_success(...)
        await self.data_api_client.create_history(...)
```

**Точка расширения**: Вызов `provider.generate()` — передать новые параметры через kwargs.

**Рекомендация**:
```python
response_text = await provider.generate(
    prompt=request.prompt_text,
    system_prompt=request.system_prompt,  # Новый параметр
    response_format=request.response_format  # Новый параметр
)
```

---

### 2.4 Infrastructure Layer — AI Providers

**Анализ 14 провайдеров:**

| # | Провайдер | Файл | API Format | System Prompt | response_format | Примечания |
|---|-----------|------|------------|---------------|-----------------|-----------|
| 1 | Groq | `groq.py` | OpenAI | ✅* | ❓ | OpenAI-compatible, вероятно поддерживает |
| 2 | Cerebras | `cerebras.py` | OpenAI | ✅* | ❓ | OpenAI-compatible, вероятно поддерживает |
| 3 | SambaNova | `sambanova.py` | OpenAI | ✅ (док) | ✅ `json_object` | Документировано в официальной API |
| 4 | HuggingFace | `huggingface.py` | OpenAI | ✅ (док) | ❓ | Router endpoint уже поддерживает messages |
| 5 | Cloudflare | `cloudflare.py` | Cloudflare | ✅ (док) | ✅ `json_object`+`json_schema` | Полная поддержка (добавлено 25.02.2025) |
| 6 | DeepSeek | `deepseek.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |
| 7 | OpenRouter | `openrouter.py` | OpenAI | ✅ (док) | ⚠️ Workaround | Лучше через промпт |
| 8 | GitHub Models | `github_models.py` | OpenAI | ✅ (док) | ✅ `json_schema` | Полная поддержка Structured Outputs |
| 9 | Fireworks | `fireworks.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |
| 10 | Hyperbolic | `hyperbolic.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |
| 11 | Novita | `novita.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |
| 12 | Scaleway | `scaleway.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |
| 13 | Kluster | `kluster.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |
| 14 | Nebius | `nebius.py` | OpenAI | ✅* | ❓ | OpenAI-compatible |

**Легенда:**
- ✅ — Подтверждено документацией
- ✅* — Вероятная поддержка (OpenAI-compatible, не проверено)
- ⚠️ — Частичная поддержка / workaround
- ❓ — Неизвестно (требует тестирования)

**Ключевой вывод**: Все 14 провайдеров используют OpenAI-compatible формат → можно добавить system prompt УНИФИЦИРОВАННО.

---

#### Базовый класс AIProviderBase

**Файл**: `app/infrastructure/ai_providers/base.py`

```python
class AIProviderBase(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Args:
            prompt: User's prompt text
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            Generated response text
        """
        pass
```

**Важно**: Интерфейс уже поддерживает `**kwargs` → новые параметры не ломают API.

---

#### Пример реализации (Cloudflare)

**Файл**: `app/infrastructure/ai_providers/cloudflare.py`

**Текущий код:**
```python
async def generate(self, prompt: str, **kwargs) -> str:
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": kwargs.get("max_tokens", 512),
        "temperature": kwargs.get("temperature", 0.7),
    }
    # POST to Cloudflare Workers AI
```

**Требуемые изменения (F011-B):**
```python
async def generate(self, prompt: str, **kwargs) -> str:
    # Построить messages array с system prompt
    messages = []

    system_prompt = kwargs.get("system_prompt")
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    # Payload с messages + response_format
    payload = {
        "messages": messages,
        "max_tokens": kwargs.get("max_tokens", 512),
        "temperature": kwargs.get("temperature", 0.7),
    }

    # Добавить response_format если указан
    response_format = kwargs.get("response_format")
    if response_format:
        payload["response_format"] = response_format

    # POST запрос
```

**Паттерн для всех провайдеров:**
1. Извлечь `system_prompt` из kwargs
2. Построить messages array: `[{"role": "system", ...}, {"role": "user", ...}]`
3. Извлечь `response_format` из kwargs
4. Добавить в payload если провайдер поддерживает (graceful degradation)

---

### 2.5 Provider Registry (F008 SSOT)

**Файл**: `app/infrastructure/ai_providers/registry.py`

```python
PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    "Groq": GroqProvider,
    "Cerebras": CerebrasProvider,
    # ... (14 провайдеров)
}

class ProviderRegistry:
    _instances: dict[str, AIProviderBase] = {}

    @classmethod
    def get_provider(cls, name: str) -> Optional[AIProviderBase]:
        """Lazy initialization с кэшированием"""
        if name not in cls._instances:
            provider_class = PROVIDER_CLASSES.get(name)
            if provider_class:
                cls._instances[name] = provider_class()
        return cls._instances.get(name)
```

**Без изменений** — реестр остаётся Single Source of Truth для маппинга имён → классов.

---

## 3. Quality Cascade Checklist (7/7)

### QC-1: DRY (Don't Repeat Yourself) ✅

**Найденные компоненты для переиспользования:**

| Компонент | Расположение | Использование |
|-----------|--------------|---------------|
| `AIProviderBase` | `infrastructure/ai_providers/base.py` | Расширить сигнатуру `generate()` |
| `ProviderRegistry` | `infrastructure/ai_providers/registry.py` | Без изменений (SSOT) |
| `ProcessPromptRequest` | `api/v1/schemas.py` | Добавить 2 опциональных поля |
| `PromptRequest` | `domain/models.py` | Добавить 2 опциональных поля |

**Рекомендация**: ✅ **НЕ создавать новые классы** — расширить существующие DTO и базовый класс.

**Дублирование отсутствует**: Текущая архитектура DDD/Hexagonal уже имеет правильное разделение слоёв.

---

### QC-2: KISS (Keep It Simple, Stupid) ✅

**Анализ сложности PRD:**

| Компонент PRD | Оценка сложности | Можно упростить? |
|---------------|------------------|------------------|
| System Prompt поддержка | **Простая** | ❌ Нет — единый паттерн для всех провайдеров |
| Response Format | **Средняя** | ⚠️ Да — сначала `json_object`, потом `json_schema` |
| JSON валидация | **Сложная** | ✅ Да — отложить на v2 (опциональная фича) |
| Provider capabilities matrix | **Средняя** | ✅ Да — начать с документации, endpoint позже |

**Рекомендации по упрощению:**

1. **Фаза 1 (v1.0)**: Только `{"type": "json_object"}` (без schema validation)
2. **Фаза 2 (v1.1)**: Добавить `{"type": "json_schema", "schema": {...}}` если потребуется
3. **Отложить**: JSON Schema validation (FR-020) — ресурсоёмкая операция

**Упрощённый scope v1.0:**
- FR-001 ✅ System Prompt
- FR-002 ✅ System Message в messages array
- FR-003 ✅ Response Format параметр
- FR-004 ✅ Cloudflare поддержка
- FR-005 ⚪ JSON валидация (опционально, WARNING логи)
- FR-006 ✅ Обратная совместимость
- FR-007 ✅ OpenAI-compatible провайдеры

---

### QC-3: YAGNI (You Aren't Gonna Need It) ✅

**Компоненты "на будущее" из PRD:**

| # | Компонент | Нужен сейчас? | Решение |
|---|-----------|---------------|---------|
| 1 | Full JSON Schema validation | ❌ Нет | ✅ Исключить из v1.0 (FR-020) |
| 2 | Provider capabilities endpoint | ❌ Нет | ✅ Начать с документации, endpoint в v2 |
| 3 | Graceful degradation | ✅ Да | ✅ Включить — критично для backward compatibility |
| 4 | Fallback JSON extraction | ⚠️ Возможно | ✅ Включить — regex парсинг `json...` если модель вернула markdown |

**Фильтрация scope:**

✅ **Включить в v1.0:**
- System prompts (FR-001, FR-002)
- Response format basic (`json_object`) (FR-003, FR-004)
- Graceful degradation (NF-031)
- Backward compatibility (FR-006)

❌ **Исключить из v1.0:**
- JSON Schema validation (FR-020) — отложить на v2
- Provider capabilities API endpoint (UI-002) — отложить на v2
- Advanced response_format (`json_schema` с полной валидацией) — отложить на v1.1+

---

### QC-4: SoC (Separation of Concerns) ✅

**Архитектура существующих модулей:**

| Слой | Ответственность | Границы |
|------|----------------|---------|
| **API Layer** (`api/v1/`) | HTTP запросы/ответы, Pydantic валидация | FastAPI endpoints, schemas |
| **Application Layer** (`application/`) | Бизнес-логика (выбор модели, fallback, статистика) | Use Cases |
| **Domain Layer** (`domain/`) | Легкие DTOs для передачи данных | Dataclasses без логики |
| **Infrastructure Layer** (`infrastructure/`) | Интеграции с внешними системами (AI providers, Data API) | Providers, HTTP clients |

**Точки интеграции для F011-B:**

1. **API → Application**: Передать `system_prompt` и `response_format` из Request в Use Case
2. **Application → Infrastructure**: Передать параметры в `provider.generate()` через kwargs
3. **Infrastructure**: Провайдеры строят messages array и добавляют response_format в payload

**Ответственности НЕ смешиваются** — каждый слой делает своё:
- API: парсинг HTTP
- Use Case: выбор модели
- Providers: построение LLM-specific payload

---

### QC-5: SSoT (Single Source of Truth) ✅

**Источники данных в проекте:**

| Тип данных | Файл-источник | Примечания |
|------------|---------------|-----------|
| **Список провайдеров** | `infrastructure/ai_providers/registry.py` | F008 SSOT — единое место маппинга |
| **Модели AI** | Data API → PostgreSQL | HTTP-only доступ, сид в `seed.py` |
| **API токены** | `.env` → Environment variables | Никогда не хардкодить |
| **Pydantic schemas** | `api/v1/schemas.py` | API Request/Response |
| **Domain DTOs** | `domain/models.py` | Бизнес-логика |
| **Конфигурация** | `app/config.py` | Settings (если существует) |

**Рекомендации:**
- ✅ Использовать `ProcessPromptRequest` schema как SSoT для API parameters
- ✅ Использовать `PromptRequest` DTO как SSoT для domain logic
- ✅ Провайдеры регистрируются ТОЛЬКО в `registry.py` (F008)
- ❌ НЕ дублировать валидацию в разных слоях — Pydantic делает в API Layer

**SSoT для новых параметров:**
- `system_prompt: Optional[str]` — определить в `ProcessPromptRequest` schema
- `response_format: Optional[dict]` — определить в `ProcessPromptRequest` schema
- Провайдеры извлекают из `kwargs` (никакого дублирования)

---

### QC-6: CoC (Convention over Configuration) ✅

**Выявленные конвенции проекта:**

#### Именование

```python
# Классы: PascalCase
class ProcessPromptUseCase
class AIProviderBase

# Методы: snake_case
async def execute(...)
async def generate(...)

# Константы: UPPER_SNAKE_CASE
PROVIDER_CLASSES = {...}
```

#### Структура провайдеров

Все 14 провайдеров следуют единому паттерну:

```python
class {Provider}Provider(AIProviderBase):
    def __init__(self, api_key: Optional[str] = None, ...):
        self.api_key = api_key or os.getenv("{PROVIDER}_API_KEY", "")
        self.model = model or "{default-model}"
        self.api_url = "{provider-api-url}"
        self.timeout = 30.0

    async def generate(self, prompt: str, **kwargs) -> str:
        # 1. Валидация credentials
        # 2. Построение headers (Authorization)
        # 3. Построение payload (messages, max_tokens, temperature)
        # 4. POST запрос с httpx.AsyncClient
        # 5. Парсинг response (choices[0].message.content)

    async def health_check(self) -> bool:
        # Проверка доступности API

    def get_provider_name(self) -> str:
        return "{Provider}"
```

#### Messages Array формат

**Стандарт OpenAI:**
```python
messages = [
    {"role": "system", "content": "system instructions"},
    {"role": "user", "content": "user prompt"}
]
```

**Рекомендация**: Следовать этому паттерну для всех 14 провайдеров (уже OpenAI-compatible).

#### Error Handling

```python
try:
    response = await client.post(...)
except Exception as e:
    sanitized_error = sanitize_error_message(str(e))
    logger.error(f"Provider {self.get_provider_name()} failed: {sanitized_error}")
    raise
```

**Конвенции для F011-B:**
1. System prompt → `messages[0]` с `role="system"`
2. User prompt → `messages[1]` с `role="user"`
3. Response format → `payload["response_format"]` если поддерживается
4. Graceful degradation → игнорировать unsupported параметры (НЕ raise Exception)

---

### QC-7: Security ✅

**Выявленные security-практики:**

#### 1. Secrets Management

```python
# ✅ CORRECT — из environment variables
self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

# ❌ WRONG — хардкод
self.api_key = "sk-..."
```

**Конвенция**: Все API ключи ТОЛЬКО из env-переменных.

#### 2. Error Sanitization

```python
from app.utils.security import sanitize_error_message

try:
    response = await client.post(...)
except Exception as e:
    sanitized_error = sanitize_error_message(str(e))  # Удаляет токены
    logger.error(f"Error: {sanitized_error}")
```

**F011-B**: System prompts и responses НЕ содержат токены, но всё равно логировать через sanitize.

#### 3. Input Validation

```python
class ProcessPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
```

**Рекомендация для F011-B:**
```python
class ProcessPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    system_prompt: Optional[str] = Field(None, max_length=5000)  # Ограничить длину
    response_format: Optional[dict] = Field(None)  # Валидировать структуру
```

#### 4. Graceful Degradation (Security + Reliability)

```python
# Если провайдер не поддерживает response_format → игнорировать (НЕ падать)
if response_format and self.supports_response_format:
    payload["response_format"] = response_format
```

**Security-риски F011-B:**

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| System prompt injection | Low | Medium | Валидация длины (max_length=5000), логирование |
| Response format manipulation | Low | Low | Pydantic валидация словаря |
| JSON parsing DoS (большие responses) | Medium | Medium | Timeout 30s, response size limit |
| API token leakage в логах | Low | High | sanitize_error_message() везде |

---

## 4. Технические ограничения

### 4.1 Ограничения провайдеров

| Провайдер | System Prompt | response_format | Ограничения |
|-----------|---------------|-----------------|-------------|
| Cloudflare | ✅ | ✅ `json_object`, `json_schema` | Полная поддержка |
| SambaNova | ✅ | ✅ `json_object` | Без `json_schema` |
| GitHub Models | ✅ | ✅ `json_schema` | Полная поддержка Structured Outputs |
| HuggingFace | ✅ | ❓ | Response format требует тестирования |
| OpenRouter | ✅ | ⚠️ Workaround | Лучше JSON инструкции в промпте |
| Остальные 9 | ✅* | ❓ | OpenAI-compatible, требуется тестирование |

**Вывод**: Graceful degradation обязателен — не все провайдеры поддерживают `response_format`.

### 4.2 Архитектурные ограничения

1. **HTTP-only архитектура** — Business API НЕ обращается к БД напрямую
   - ✅ Сохраняется — новые параметры НЕ требуют изменений в Data API

2. **Базовый интерфейс `AIProviderBase.generate()`** — уже принимает `**kwargs`
   - ✅ Расширяем без breaking changes

3. **Async/Await везде** — все провайдеры асинхронные
   - ✅ Сохраняется

4. **F008 SSOT для провайдеров** — реестр в `registry.py`
   - ✅ Без изменений

### 4.3 Совместимость

**Обратная совместимость (FR-006):**

```python
# До F011-B (работает)
POST /api/v1/prompts/process
{
  "prompt": "Hello, AI!"
}

# После F011-B (тоже работает)
POST /api/v1/prompts/process
{
  "prompt": "Hello, AI!",
  "system_prompt": "You are helpful assistant",  # Опционально
  "response_format": {"type": "json_object"}      # Опционально
}
```

**Гарантия**: Все существующие API consumers продолжают работать.

---

## 5. Рекомендации по реализации

### 5.1 Фазирование

#### Фаза 1: System Prompt (High Priority)

**Изменения:**
1. `ProcessPromptRequest` — добавить `system_prompt: Optional[str] = Field(None, max_length=5000)`
2. `PromptRequest` DTO — добавить `system_prompt: Optional[str] = None`
3. `ProcessPromptUseCase.execute()` — передать в `provider.generate(system_prompt=...)`
4. Все 14 провайдеров — построение messages array с system role

**Сложность**: 🟢 Низкая (единый паттерн для всех провайдеров)

#### Фаза 2: Response Format Basic (Medium Priority)

**Изменения:**
1. `ProcessPromptRequest` — добавить `response_format: Optional[dict] = None`
2. `PromptRequest` DTO — добавить `response_format: Optional[dict] = None`
3. Провайдеры с поддержкой — добавить в payload:
   - Cloudflare: `{"type": "json_object"}` и `{"type": "json_schema"}`
   - SambaNova: `{"type": "json_object"}`
   - GitHub Models: `{"type": "json_schema"}`
4. Провайдеры без поддержки — игнорировать (graceful degradation)

**Сложность**: 🟡 Средняя (provider-specific логика)

#### Фаза 3: JSON Validation (Optional)

**Изменения:**
1. Добавить опциональную валидацию JSON responses
2. Логировать WARNING если response невалидный JSON
3. НЕ падать — вернуть как есть

**Сложность**: 🟢 Низкая (опциональная фича)

---

### 5.2 Приоритизация провайдеров для тестирования

| Приоритет | Провайдер | Причина |
|-----------|-----------|---------|
| P0 | Cloudflare | Reference implementation, полная поддержка |
| P1 | SambaNova | Документированная поддержка `json_object` |
| P1 | GitHub Models | Structured Outputs с `json_schema` |
| P2 | Groq, Cerebras | Популярные, OpenAI-compatible |
| P2 | OpenRouter | Workaround через промпт |
| P3 | Остальные 9 | Тестирование после основных |

---

### 5.3 Точки интеграции (файлы для изменения)

| # | Файл | Изменения | Сложность |
|---|------|-----------|-----------|
| 1 | `app/api/v1/schemas.py` | Добавить 2 поля в `ProcessPromptRequest` | 🟢 Тривиально |
| 2 | `app/domain/models.py` | Добавить 2 поля в `PromptRequest` dataclass | 🟢 Тривиально |
| 3 | `app/application/use_cases/process_prompt.py` | Передать kwargs в `provider.generate()` | 🟢 Тривиально |
| 4 | `app/infrastructure/ai_providers/base.py` | Документировать новые kwargs | 🟢 Тривиально |
| 5-18 | `app/infrastructure/ai_providers/{provider}.py` | Построение messages + response_format | 🟡 Средне (14 файлов) |

**Оценка трудоёмкости**: 14 провайдеров × 15 минут = **~3.5 часа** на все изменения провайдеров.

---

## 6. Риски и митигации

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Модели игнорируют `response_format` | Medium | High | Fallback JSON extraction (regex `json...`) |
| 2 | Breaking change для старых клиентов | Low | High | Опциональные поля (backward compatible) |
| 3 | Провайдеры по-разному обрабатывают system prompts | High | Medium | Provider-specific адаптеры, graceful degradation |
| 4 | JSON validation overhead > 10ms | Low | Medium | Сделать опциональным (WARNING логи, НЕ fail) |
| 5 | System prompt injection | Low | Medium | Валидация длины, sanitize в логах |

---

## 7. Зависимости и блокеры

### 7.1 Предусловия (✅ Выполнены)

- ✅ **F011-A VALIDATED** — GoogleGemini и Cohere удалены
- ✅ 14 OpenAI-compatible провайдеров унифицированы
- ✅ F008 SSOT — ProviderRegistry в `registry.py`
- ✅ F010 Rolling Window Reliability — effective_reliability_score

### 7.2 Блокирующие зависимости

**Нет блокирующих зависимостей** — можно начинать реализацию.

---

## 8. Выводы и следующие шаги

### 8.1 Ключевые выводы

1. ✅ **Архитектура готова** — DDD/Hexagonal разделение позволяет чисто добавить параметры
2. ✅ **F011-A завершена** — 14 OpenAI-compatible провайдеров значительно упрощают реализацию
3. ✅ **Backward compatible** — новые поля опциональные, старые клиенты работают
4. ⚠️ **Provider-specific логика** — не все поддерживают `response_format` (graceful degradation)
5. 🟢 **Низкая сложность** — System prompts универсальны для всех провайдеров

### 8.2 Рекомендации

**Начать с:**
1. System Prompt (FR-001, FR-002) — единый паттерн для всех 14 провайдеров
2. Response Format basic (FR-003, FR-004) — Cloudflare, SambaNova, GitHub Models
3. Graceful degradation (NF-031) — игнорировать unsupported параметры

**Отложить на v2:**
- JSON Schema validation (FR-020)
- Provider capabilities API endpoint (UI-002)

**Тестирование:**
- Приоритет P0: Cloudflare
- Приоритет P1: SambaNova, GitHub Models
- Приоритет P2: Groq, Cerebras, OpenRouter
- Приоритет P3: Остальные 9 провайдеров

### 8.3 Следующий шаг

➡️ `/aidd-feature-plan` — создать детальный Implementation Plan для F011-B

---

## Приложения

### A. Список проанализированных файлов (8 файлов)

1. `services/free-ai-selector-business-api/app/api/v1/endpoints/prompts.py`
2. `services/free-ai-selector-business-api/app/api/v1/schemas.py`
3. `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`
4. `services/free-ai-selector-business-api/app/domain/models.py`
5. `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py`
6. `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`
7. `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cloudflare.py`
8. `services/free-ai-selector-business-api/app/infrastructure/ai_providers/groq.py`

**Дополнительно**: Все 14 провайдеров проанализированы через Explore-агента.

### B. Связанные документы

| Документ | Путь |
|----------|------|
| PRD F011-B | `ai-docs/docs/prd/2026-01-15_F011-B_system-prompts-json-response-prd.md` |
| PRD F011-A | `ai-docs/docs/prd/2026-01-15_F011-A_remove-non-openai-providers-prd.md` |
| Pipeline State | `.pipeline-state.json` |
| CLAUDE.md | `./CLAUDE.md` |

---

**Статус**: ✅ Research завершён
**Ворота**: RESEARCH_DONE готов к прохождению
**Следующий этап**: `/aidd-feature-plan` для создания Implementation Plan
