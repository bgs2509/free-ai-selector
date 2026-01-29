---
# === YAML Frontmatter (машиночитаемые метаданные) ===
feature_id: "F011-B"
feature_name: "system-prompts-json-response"
title: "Feature Plan: System Prompts & JSON Response Support"
created: "2026-01-15"
author: "AI (Architect)"
type: "feature-plan"
status: "Draft"
version: 1
mode: "FEATURE"

# Ссылки на связанные артефакты
_analysis_ref: "_analysis/2026-01-15_F011-B_system-prompts-json-response-_analysis.md"
_research_ref: "_research/2026-01-15_F011-B_system-prompts-json-response-_research.md"

# Затрагиваемые сервисы
affected_services:
  modified:
    - free-ai-selector-business-api
  created: []

# Связанные фичи
related_features:
  - F011-A  # Prerequisite: remove-non-openai-providers
approved_by: null
approved_at: null
---

# План интеграции фичи: System Prompts & JSON Response Support

**Feature ID**: F011-B
**Версия**: 1.0
**Дата**: 2026-01-15
**Автор**: AI Agent (Архитектор)
**Статус**: Draft
**Режим**: FEATURE
**Связанный PRD**: 2026-01-15_F011-B_system-prompts-json-response-_analysis.md
**Prerequisite**: F011-A (remove-non-openai-providers) - ✅ DEPLOYED

---

## 1. Обзор фичи

### 1.1 Цель

Добавить поддержку `system_prompt` и `response_format` параметров в существующий API `/process` для всех 14 OpenAI-compatible AI провайдеров, оставшихся после F011-A.

**Бизнес-ценность**:
- Пользователи смогут передавать system prompts для более точного управления поведением AI
- Поддержка structured output (JSON) для интеграций с другими системами
- Сохранение backward compatibility — существующие клиенты работают без изменений

### 1.2 Scope

**В scope:**
- Добавление `system_prompt: Optional[str]` в API endpoint `/process`
- Добавление `response_format: Optional[dict]` в API endpoint `/process`
- Модификация всех 14 AI providers для поддержки messages array с system role
- Basic support для `response_format: {"type": "json_object"}`
- Graceful degradation для провайдеров без поддержки `response_format`
- Обновление API documentation (OpenAPI)
- Unit и integration тесты

**Вне scope (для v2 или отдельных фич):**
- JSON Schema validation (`response_format.schema`)
- Полная поддержка `response_format` для всех провайдеров (только basic в v1)
- UI для ввода system prompts (Telegram Bot, Web UI)
- Capabilities endpoint (`GET /providers/{id}/capabilities`)
- Сохранение system prompts в БД (prompt_history)

---

## 2. Анализ существующей архитектуры

### 2.1 Текущая структура проекта

```
free-ai-selector/
├── services/
│   ├── free-ai-selector-business-api/    ← Будет модифицирован
│   │   ├── app/
│   │   │   ├── api/v1/
│   │   │   │   ├── endpoints/prompts.py  ← Endpoint `/process`
│   │   │   │   └── schemas.py            ← ProcessPromptRequest/Response
│   │   │   ├── application/
│   │   │   │   └── use_cases/process_prompt.py  ← Use Case
│   │   │   ├── domain/
│   │   │   │   └── models.py             ← PromptRequest/Response DTOs
│   │   │   └── infrastructure/
│   │   │       └── ai_providers/         ← 14 провайдеров
│   │   │           ├── base.py           ← AIProviderBase
│   │   │           ├── groq.py           ← Модифицировать (14 файлов)
│   │   │           ├── cerebras.py
│   │   │           ├── sambanova.py
│   │   │           ├── huggingface.py
│   │   │           ├── cloudflare.py
│   │   │           ├── deepseek.py
│   │   │           ├── openrouter.py
│   │   │           ├── github_models.py
│   │   │           ├── fireworks.py
│   │   │           ├── hyperbolic.py
│   │   │           ├── novita.py
│   │   │           ├── scaleway.py
│   │   │           ├── kluster.py
│   │   │           └── nebius.py
│   │   └── tests/                        ← Тесты
│   ├── free-ai-selector-data-postgres-api/  ← Без изменений
│   ├── free-ai-selector-telegram-bot/       ← Без изменений (v1)
│   └── free-ai-selector-health-worker/      ← Без изменений
├── docker-compose.yml                    ← Без изменений
└── ...
```

### 2.2 Затрагиваемые сервисы

| Сервис | Тип изменения | Влияние |
|--------|--------------|---------|
| free-ai-selector-business-api | Модификация | Высокое (API layer, Use Case, 14 providers) |
| free-ai-selector-data-postgres-api | Без изменений | — |
| free-ai-selector-telegram-bot | Без изменений | Без влияния (v1) |
| free-ai-selector-health-worker | Без изменений | Без влияния |

### 2.3 Существующие паттерны

**Архитектурные паттерны в проекте:**
- **HTTP-only доступ к данным**: Business API → Data API (HTTP) → PostgreSQL
- **DDD/Hexagonal структура**: `api/` → `application/` → `domain/` → `infrastructure/`
- **Async-first подход**: Все I/O операции используют `async/await`
- **F008 SSOT (Provider Registry)**: ProviderRegistry как единый источник правды для провайдеров
- **F010 Rolling Window Reliability**: Динамический reliability score на основе истории

**Соглашения о коде:**
- Python 3.11+ с полными type hints
- Pydantic для валидации API schemas
- Dataclasses для Domain DTOs
- structlog для логирования
- `**kwargs` в `AIProviderBase.generate()` для расширяемости

**Важно**: Новый код ДОЛЖЕН следовать существующим паттернам.

---

## 3. Матрица влияния

### 3.1 Влияние на существующие компоненты

| Компонент | Тип влияния | Риск | Описание |
|-----------|-------------|------|----------|
| `ProcessPromptRequest` schema | Расширение | Низкий | Добавление опциональных полей (backward compatible) |
| `PromptRequest` DTO | Расширение | Низкий | Добавление опциональных полей |
| `ProcessPromptUseCase` | Модификация | Низкий | Передача новых параметров в providers |
| 14 AI providers | Модификация | Средний | Построение messages array вместо простого prompt |
| `AIProviderBase` | Документирование | Низкий | Уточнить kwargs в docstring |
| Endpoint `/process` | Backward compatible | Низкий | Новые поля опциональные |
| OpenAPI docs | Обновление | Низкий | Добавить новые параметры в документацию |

### 3.2 Зависимости

| Зависимость | Тип | Статус | Действие |
|-------------|-----|--------|----------|
| F011-A (remove-non-openai-providers) | Prerequisite | ✅ DEPLOYED | 14 OpenAI-compatible провайдеров готовы |
| OpenAI Python SDK patterns | Внешняя | Ready | messages array format уже используется |
| Pydantic v2 | Пакет | Ready | Используется для schemas |
| httpx | Пакет | Ready | HTTP клиент для провайдеров |

**Блокеры**: Нет

### 3.3 Обратная совместимость

| Аспект | Совместим? | Действие если нет |
|--------|------------|-------------------|
| API контракты | ✅ Да | Новые поля опциональные (`Optional[str]`, `Optional[dict]`) |
| Схема БД | ✅ Да | Изменения БД не требуются (v1 не сохраняет system prompts) |
| Конфигурация | ✅ Да | Новые env-переменные не требуются |
| Существующие тесты | ✅ Да | Тесты без новых полей должны продолжать работать |

**Важно**: 100% backward compatible — существующие клиенты работают без изменений.

---

## 4. План интеграции

### Stage 4.1: Расширение API Layer (Pydantic Schemas)

**Цель**: Добавить новые параметры в API request schema

**Задачи**:

| # | Задача | Файл | Требование |
|---|--------|------|------------|
| 4.1.1 | Добавить `system_prompt` в `ProcessPromptRequest` | `app/api/v1/schemas.py` | FR-001, FR-002 |
| 4.1.2 | Добавить `response_format` в `ProcessPromptRequest` | `app/api/v1/schemas.py` | FR-003, FR-004 |
| 4.1.3 | Обновить docstrings для новых полей | `app/api/v1/schemas.py` | — |

**Изменения в schemas**:

```python
# app/api/v1/schemas.py

class ProcessPromptRequest(BaseModel):
    """Schema for prompt processing request."""

    prompt: str = Field(..., min_length=1, max_length=10000, description="User's prompt text")

    # NEW: F011-B
    system_prompt: Optional[str] = Field(
        None,
        max_length=5000,
        description="Optional system prompt to guide AI behavior (OpenAI-compatible providers only)"
    )

    # NEW: F011-B
    response_format: Optional[dict] = Field(
        None,
        description="Optional response format specification. Example: {'type': 'json_object'}"
    )
```

**Критерии завершения**:
- [ ] Новые поля добавлены с корректными type hints
- [ ] Валидация длины для `system_prompt` (max 5000 символов)
- [ ] Docstrings обновлены
- [ ] OpenAPI schema автоматически обновляется

---

### Stage 4.2: Расширение Domain Layer (DTOs)

**Цель**: Добавить новые поля в domain models

**Задачи**:

| # | Задача | Файл | Требование |
|---|--------|------|------------|
| 4.2.1 | Добавить поля в `PromptRequest` DTO | `app/domain/models.py` | FR-001, FR-003 |

**Изменения в models**:

```python
# app/domain/models.py

@dataclass
class PromptRequest:
    """
    Prompt processing request DTO.

    Represents a user's request to process a prompt.
    """

    user_id: str
    prompt_text: str

    # NEW: F011-B
    system_prompt: Optional[str] = None     # System prompt for AI guidance
    response_format: Optional[dict] = None  # Structured output specification
```

**Критерии завершения**:
- [ ] Новые поля добавлены с default values
- [ ] Type hints корректны (`Optional[str]`, `Optional[dict]`)
- [ ] Docstrings обновлены

---

### Stage 4.3: Расширение Application Layer (Use Case)

**Цель**: Передать новые параметры от API к infrastructure layer

**Задачи**:

| # | Задача | Файл | Требование |
|---|--------|------|------------|
| 4.3.1 | Передать `system_prompt` в `provider.generate()` | `app/application/use_cases/process_prompt.py` | FR-001, FR-002 |
| 4.3.2 | Передать `response_format` в `provider.generate()` | `app/application/use_cases/process_prompt.py` | FR-003, FR-004 |

**Изменения в use_case**:

```python
# app/application/use_cases/process_prompt.py

class ProcessPromptUseCase:
    async def execute(self, request: PromptRequest) -> PromptResponse:
        # ... existing model selection logic ...

        try:
            # NEW: передать kwargs в generate()
            response_text = await provider.generate(
                prompt=request.prompt_text,
                system_prompt=request.system_prompt,      # NEW: F011-B
                response_format=request.response_format    # NEW: F011-B
            )

            # ... existing response handling ...
```

**Критерии завершения**:
- [ ] Новые параметры передаются в `provider.generate()` как kwargs
- [ ] Существующая логика не нарушена
- [ ] Логирование обновлено (log system_prompt presence, response_format type)

---

### Stage 4.4: Расширение Infrastructure Layer (14 AI Providers)

**Цель**: Модифицировать все провайдеры для поддержки messages array и response_format

**Задачи**:

| # | Задача | Файлы | Требование |
|---|--------|-------|------------|
| 4.4.1 | Обновить `base.py` docstring для kwargs | `app/infrastructure/ai_providers/base.py` | — |
| 4.4.2 | Модифицировать Groq provider | `app/infrastructure/ai_providers/groq.py` | FR-002, FR-004 |
| 4.4.3 | Модифицировать Cerebras provider | `app/infrastructure/ai_providers/cerebras.py` | FR-002, FR-004 |
| 4.4.4 | Модифицировать SambaNova provider | `app/infrastructure/ai_providers/sambanova.py` | FR-002, FR-004 |
| 4.4.5 | Модифицировать HuggingFace provider | `app/infrastructure/ai_providers/huggingface.py` | FR-002, FR-004 |
| 4.4.6 | Модифицировать Cloudflare provider | `app/infrastructure/ai_providers/cloudflare.py` | FR-002, FR-004 |
| 4.4.7 | Модифицировать DeepSeek provider | `app/infrastructure/ai_providers/deepseek.py` | FR-002, FR-004 |
| 4.4.8 | Модифицировать OpenRouter provider | `app/infrastructure/ai_providers/openrouter.py` | FR-002, FR-004 |
| 4.4.9 | Модифицировать GitHub Models provider | `app/infrastructure/ai_providers/github_models.py` | FR-002, FR-004 |
| 4.4.10 | Модифицировать Fireworks provider | `app/infrastructure/ai_providers/fireworks.py` | FR-002, FR-004 |
| 4.4.11 | Модифицировать Hyperbolic provider | `app/infrastructure/ai_providers/hyperbolic.py` | FR-002, FR-004 |
| 4.4.12 | Модифицировать Novita provider | `app/infrastructure/ai_providers/novita.py` | FR-002, FR-004 |
| 4.4.13 | Модифицировать Scaleway provider | `app/infrastructure/ai_providers/scaleway.py` | FR-002, FR-004 |
| 4.4.14 | Модифицировать Kluster provider | `app/infrastructure/ai_providers/kluster.py` | FR-002, FR-004 |
| 4.4.15 | Модифицировать Nebius provider | `app/infrastructure/ai_providers/nebius.py` | FR-002, FR-004 |

**Паттерн изменений (единый для всех провайдеров)**:

```python
# app/infrastructure/ai_providers/{provider}.py

class {Provider}Provider(AIProviderBase):
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using {Provider} API.

        Args:
            prompt: User's prompt text
            **kwargs: Additional parameters
                - system_prompt (str, optional): System prompt for AI guidance
                - response_format (dict, optional): Response format (e.g., {"type": "json_object"})
                - max_tokens (int, optional): Maximum tokens to generate
                - temperature (float, optional): Sampling temperature
        """
        # NEW: Extract kwargs (F011-B)
        system_prompt = kwargs.get("system_prompt")
        response_format = kwargs.get("response_format")
        max_tokens = kwargs.get("max_tokens", 1000)
        temperature = kwargs.get("temperature", 0.7)

        # NEW: Build messages array (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": self.model_name,
            "messages": messages,  # Changed from "prompt" to "messages"
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # NEW: Add response_format if supported and provided (F011-B)
        if response_format:
            # Provider-specific support check
            if self._supports_response_format():
                payload["response_format"] = response_format
            else:
                # Graceful degradation: log warning, continue without format
                logger.warning(
                    "response_format_not_supported",
                    provider=self.get_provider_name(),
                    requested_format=response_format
                )

        # ... existing HTTP request logic ...

    def _supports_response_format(self) -> bool:
        """Check if provider supports response_format parameter."""
        # Providers with confirmed support (from Research):
        # - Cloudflare: json_object, json_schema
        # - SambaNova: json_object
        # - GitHub Models: json_schema
        # Others: TBD or graceful degradation
        return False  # Override in specific providers
```

**Provider-specific overrides**:

```python
# cloudflare.py
def _supports_response_format(self) -> bool:
    return True  # Supports both json_object and json_schema

# sambanova.py
def _supports_response_format(self) -> bool:
    return True  # Supports json_object

# github_models.py
def _supports_response_format(self) -> bool:
    return True  # Supports json_schema
```

**Критерии завершения**:
- [ ] Все 14 провайдеров модифицированы единообразно
- [ ] Messages array построен корректно (system → user)
- [ ] response_format поддержан для 3 провайдеров (Cloudflare, SambaNova, GitHub Models)
- [ ] Graceful degradation для остальных провайдеров (warning log, продолжение без format)
- [ ] Существующие тесты не сломаны (backward compatibility)

---

### Stage 4.5: Тестирование

**Цель**: Покрыть новый функционал тестами и убедиться в отсутствии регрессий

**Задачи**:

| # | Задача | Файлы | Покрытие |
|---|--------|-------|----------|
| 4.5.1 | Unit-тесты для ProcessPromptRequest schema | `tests/unit/test_schemas.py` | Валидация новых полей |
| 4.5.2 | Unit-тесты для PromptRequest DTO | `tests/unit/test_domain_models.py` | Новые поля в DTO |
| 4.5.3 | Unit-тесты для ProcessPromptUseCase | `tests/unit/test_process_prompt_use_case.py` | Передача kwargs |
| 4.5.4 | Unit-тесты для providers (representative sample) | `tests/unit/test_ai_providers.py` | Messages array, response_format |
| 4.5.5 | Integration-тесты для `/process` endpoint | `tests/integration/test_prompts_endpoint.py` | E2E с новыми параметрами |
| 4.5.6 | Regression-тесты (без новых полей) | Существующие тесты | Backward compatibility |

**Тестовые сценарии**:

```python
# tests/unit/test_schemas.py

def test_process_prompt_request_with_system_prompt():
    """Test ProcessPromptRequest with system_prompt."""
    data = {
        "prompt": "Hello AI",
        "system_prompt": "You are a helpful assistant"
    }
    request = ProcessPromptRequest(**data)
    assert request.system_prompt == "You are a helpful assistant"

def test_process_prompt_request_with_response_format():
    """Test ProcessPromptRequest with response_format."""
    data = {
        "prompt": "Generate JSON",
        "response_format": {"type": "json_object"}
    }
    request = ProcessPromptRequest(**data)
    assert request.response_format == {"type": "json_object"}

def test_process_prompt_request_backward_compatible():
    """Test backward compatibility - старые клиенты без новых полей."""
    data = {"prompt": "Hello"}
    request = ProcessPromptRequest(**data)
    assert request.system_prompt is None
    assert request.response_format is None
```

```python
# tests/unit/test_ai_providers.py

@pytest.mark.asyncio
async def test_provider_messages_array_with_system_prompt(groq_provider):
    """Test that provider builds messages array correctly."""
    with patch.object(groq_provider, '_make_request') as mock_request:
        mock_request.return_value = {"choices": [{"message": {"content": "Response"}}]}

        await groq_provider.generate(
            prompt="User query",
            system_prompt="You are helpful"
        )

        # Verify messages array
        call_args = mock_request.call_args[0][0]  # payload
        assert "messages" in call_args
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0] == {"role": "system", "content": "You are helpful"}
        assert call_args["messages"][1] == {"role": "user", "content": "User query"}

@pytest.mark.asyncio
async def test_provider_graceful_degradation_unsupported_format(groq_provider):
    """Test graceful degradation for unsupported response_format."""
    with patch.object(groq_provider, '_make_request') as mock_request:
        with patch('app.infrastructure.ai_providers.groq.logger') as mock_logger:
            mock_request.return_value = {"choices": [{"message": {"content": "Response"}}]}

            await groq_provider.generate(
                prompt="Generate JSON",
                response_format={"type": "json_object"}
            )

            # Verify warning logged
            mock_logger.warning.assert_called_once()
            # Verify request continued without format
            call_args = mock_request.call_args[0][0]
            assert "response_format" not in call_args
```

**Критерии завершения**:
- [ ] Coverage ≥ 75% для нового кода
- [ ] Все существующие тесты проходят (0 regression failures)
- [ ] Unit-тесты покрывают все новые параметры
- [ ] Integration-тесты покрывают E2E flow
- [ ] Graceful degradation протестирован

---

## 5. Порядок выполнения

```
Stage 4.1 (API Layer - Schemas)
    │
    ▼
Stage 4.2 (Domain Layer - DTOs)
    │
    ▼
Stage 4.3 (Application Layer - Use Case)
    │
    ▼
Stage 4.4 (Infrastructure Layer - 14 Providers)
    │  ├── 4.4.1 base.py docstring
    │  ├── 4.4.2-4.4.15 providers (можно параллельно)
    │  └── Graceful degradation logic
    ▼
Stage 4.5 (Testing)
    ├── Unit tests
    ├── Integration tests
    └── Regression tests
```

**Оценка времени**: ~4-5 часов (14 providers × 15 мин + тесты)

---

## 6. Файлы для создания/изменения

### 6.1 Новые файлы

**Тесты**:
```
services/free-ai-selector-business-api/tests/
├── unit/
│   └── test_system_prompts.py                 ← Новый (специфичные тесты для F011-B)
└── integration/
    └── test_process_with_system_prompt.py     ← Новый (E2E тесты)
```

### 6.2 Изменяемые файлы

**Основной код**:
```
services/free-ai-selector-business-api/
├── app/
│   ├── api/v1/
│   │   └── schemas.py                         ← Добавить 2 поля
│   ├── domain/
│   │   └── models.py                          ← Добавить 2 поля
│   ├── application/use_cases/
│   │   └── process_prompt.py                  ← Передать kwargs
│   └── infrastructure/ai_providers/
│       ├── base.py                            ← Обновить docstring
│       ├── groq.py                            ← Messages array + response_format
│       ├── cerebras.py                        ← Messages array + response_format
│       ├── sambanova.py                       ← Messages array + response_format (supports format)
│       ├── huggingface.py                     ← Messages array + response_format
│       ├── cloudflare.py                      ← Messages array + response_format (supports format)
│       ├── deepseek.py                        ← Messages array + response_format
│       ├── openrouter.py                      ← Messages array + response_format
│       ├── github_models.py                   ← Messages array + response_format (supports format)
│       ├── fireworks.py                       ← Messages array + response_format
│       ├── hyperbolic.py                      ← Messages array + response_format
│       ├── novita.py                          ← Messages array + response_format
│       ├── scaleway.py                        ← Messages array + response_format
│       ├── kluster.py                         ← Messages array + response_format
│       └── nebius.py                          ← Messages array + response_format
```

**Тесты (изменения)**:
```
services/free-ai-selector-business-api/tests/
├── unit/
│   ├── test_schemas.py                        ← Тесты для новых полей
│   ├── test_domain_models.py                  ← Тесты для PromptRequest
│   ├── test_process_prompt_use_case.py        ← Тесты для kwargs
│   └── test_ai_providers.py                   ← Тесты для messages array
└── conftest.py                                ← Новые fixtures (если нужно)
```

**Итого**:
- **Изменяемых файлов**: 18 (4 core + 14 providers)
- **Новых файлов**: 2 (тесты)
- **Новых зависимостей**: 0

---

## 7. Трассировка требований

| Требование | Stage | Задача | Файл | Тест |
|------------|-------|--------|------|------|
| FR-001 (system_prompt param) | 4.1, 4.2, 4.3 | 4.1.1, 4.2.1, 4.3.1 | schemas.py, models.py, process_prompt.py | test_schemas.py |
| FR-002 (system_prompt in providers) | 4.4 | 4.4.2-4.4.15 | 14 provider files | test_ai_providers.py |
| FR-003 (response_format param) | 4.1, 4.2, 4.3 | 4.1.2, 4.2.1, 4.3.2 | schemas.py, models.py, process_prompt.py | test_schemas.py |
| FR-004 (response_format support) | 4.4 | 4.4.2-4.4.15 | cloudflare.py, sambanova.py, github_models.py | test_ai_providers.py |
| FR-005 (graceful degradation) | 4.4 | 4.4.2-4.4.15 | All providers | test_ai_providers.py |
| FR-006 (backward compatibility) | 4.1-4.5 | Все | Все файлы | Regression tests |
| FR-007 (OpenAPI update) | 4.1 | Auto | Auto-generated | — |

---

## 8. Риски интеграции

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Сломать существующий `/process` endpoint | Средняя | Высокое | 100% backward compatible (опциональные поля), regression тесты |
| Провайдеры не поддерживают messages array | Низкая | Высокое | Все 14 провайдеров OpenAI-compatible (подтверждено в Research) |
| Провайдеры отклоняют response_format | Средняя | Среднее | Graceful degradation: log warning, продолжить без format |
| Деградация производительности | Низкая | Среднее | Бенчмарк до/после для типичных запросов |
| Несовместимость с health checks | Низкая | Среднее | Health checks НЕ передают system_prompt/response_format |
| Изменения нарушат F010 (rolling window) | Низкая | Среднее | F010 работает на prompt_history, не затрагивается |

---

## 9. Quality Cascade Checklist (16/16)

> **Принцип**: Архитектурные ошибки — самые дорогие. Проверяем качество ДО реализации.

### QC-1: DRY ✅

- [x] План сверен с Research Report
- [x] Переиспользуется `AIProviderBase.generate(**kwargs)`
- [x] Единый паттерн messages array для всех 14 провайдеров

**Обоснование**: Используем существующий `**kwargs` механизм, избегаем дублирования логики через единый паттерн.

---

### QC-2: KISS ✅

- [x] Минимизировано до 18 файлов (4 core + 14 providers)
- [x] Нет новых абстракций
- [x] Простая структура: schema → DTO → use case → provider

**Обоснование**: Следуем существующей архитектуре, добавляем только минимально необходимое.

---

### QC-3: YAGNI ✅

- [x] JSON Schema validation исключён из v1 (отложен на v2)
- [x] Capabilities endpoint исключён из v1
- [x] Сохранение system prompts в БД исключено из v1
- [x] UI для system prompts исключён из v1

**Обоснование**: Реализуем только FR-001 до FR-007, откладываем "nice-to-have" фичи.

---

### QC-4: SRP ✅

- [x] `schemas.py`: Только валидация API
- [x] `models.py`: Только domain DTOs
- [x] `process_prompt.py`: Только оркестрация use case
- [x] `{provider}.py`: Только интеграция с конкретным провайдером

**Обоснование**: Каждый модуль имеет единственную ответственность, соответствующую слою DDD.

---

### QC-5: OCP ✅

- [x] Новые параметры добавляются через `**kwargs` (без изменения сигнатуры)
- [x] Провайдеры расширяются без изменения базового класса
- [x] Graceful degradation позволяет добавлять новые провайдеры

**Обоснование**: Существующие клиенты работают без изменений, новые параметры добавляются опционально.

---

### QC-6: ISP ✅

- [x] `AIProviderBase.generate()` остаётся минимальным (prompt + kwargs)
- [x] API schema добавляет только необходимые поля
- [x] Нет "толстых" интерфейсов

**Обоснование**: Интерфейсы минимальны, новые параметры опциональны.

---

### QC-7: DIP ✅

- [x] Use case зависит от `AIProviderBase` (абстракция), а не от конкретных провайдеров
- [x] Провайдеры заменяемы через ProviderRegistry (F008)

**Обоснование**: Инверсия зависимостей сохраняется (высокоуровневые модули зависят от абстракций).

---

### QC-8: SoC ✅

- [x] API Layer: валидация входных данных
- [x] Domain Layer: бизнес-объекты (DTOs)
- [x] Application Layer: оркестрация (use case)
- [x] Infrastructure Layer: внешние интеграции (providers)

**Обоснование**: Чёткое разделение по слоям DDD/Hexagonal сохраняется.

---

### QC-9: SSoT ✅

- [x] `ProcessPromptRequest` — единственный источник для API parameters
- [x] F008 ProviderRegistry — SSOT для провайдеров (сохраняется)
- [x] Нет дублирования констант

**Обоснование**: SSoT принципы соблюдаются, новые данные добавляются в существующие источники.

---

### QC-10: LoD ✅

- [x] Use case не знает детали HTTP-клиентов провайдеров
- [x] Провайдеры не знают детали Pydantic валидации
- [x] Минимальная связанность между слоями

**Обоснование**: Law of Demeter соблюдается через слоистую архитектуру.

---

### QC-11: CoC ✅

- [x] Именование следует существующим паттернам (`ProcessPromptRequest`, `PromptRequest`)
- [x] Структура файлов соответствует DDD (`api/`, `domain/`, `application/`, `infrastructure/`)
- [x] Конвенции из Research Report учтены (messages array, **kwargs)

**Обоснование**: Следуем существующим конвенциям проекта, не вводим новых правил.

---

### QC-12: Fail Fast ✅

- [x] Валидация на границе системы (Pydantic schemas)
- [x] Валидация длины `system_prompt` (max 5000)
- [x] Type hints для раннего обнаружения ошибок

**Обоснование**: Валидация на API layer, ошибки обнаруживаются рано.

---

### QC-13: Explicit > Implicit ✅

- [x] API контракты явно описаны (Pydantic schemas с docstrings)
- [x] Kwargs явно документированы в provider docstrings
- [x] Graceful degradation логируется явно (warning)

**Обоснование**: Контракты явные, нет магического поведения.

---

### QC-14: Composition > Inheritance ✅

- [x] Иерархия наследования минимальна (только `AIProviderBase`)
- [x] Новые функции добавляются через композицию (kwargs), а не новые методы

**Обоснование**: Минимальное наследование, расширение через композицию.

---

### QC-15: Testability ✅

- [x] Каждый слой тестируется изолированно (unit tests)
- [x] Провайдеры мокаются через `patch`
- [x] Нет зависимостей от глобального состояния

**Обоснование**: Архитектура позволяет изолированное тестирование всех компонентов.

---

### QC-16: Security ✅

- [x] Валидация длины входных данных (`max_length` для `system_prompt`)
- [x] Secrets не логируются (existing `sanitize_error_message`)
- [x] Нет SQL injection (нет изменений БД)

**Обоснование**: Security меры сохранены, новые входные данные валидируются.

---

## 10. Чек-лист перед реализацией

### FEATURE_PLAN_READY Checklist

**Анализ:**
- [x] Существующая архитектура изучена (Research Report)
- [x] Затрагиваемые сервисы определены (1 сервис: business-api)
- [x] Матрица влияния заполнена (18 файлов)
- [x] Обратная совместимость проверена (100% backward compatible)

**Планирование:**
- [x] Все stages определены (4.1-4.5)
- [x] Задачи детализированы (20 задач)
- [x] Новые/изменяемые файлы перечислены (18 existing, 2 new)
- [x] Требования трассируются к задачам (FR-001 до FR-007)

**Качество:**
- [x] Quality Cascade (16/16) пройден
- [x] Breaking changes: Нет (100% backward compatible)
- [x] Миграции БД: Не требуются

**Риски:**
- [x] Риски интеграции оценены (6 рисков)
- [x] Митигации определены

---

## 11. Подтверждение пользователя

> **ВНИМАНИЕ**: План требует подтверждения пользователя перед реализацией.

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  ОЖИДАЕТСЯ ПОДТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЯ                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Пожалуйста, подтвердите:                                       │
│                                                                 │
│  1. ✅ Scope фичи корректен (system_prompt + response_format)   │
│  2. ✅ Затрагиваемые файлы определены верно (18 existing, 2 new)│
│  3. ✅ Матрица влияния соответствует ожиданиям                  │
│  4. ✅ Backward compatibility 100% (опциональные параметры)     │
│  5. ✅ Риски приемлемы (6 рисков, все митигированы)            │
│  6. ✅ Миграции БД не требуются                                 │
│  7. ✅ Оценка времени: ~4-5 часов                               │
│                                                                 │
│  После подтверждения будет установлено:                         │
│  gates.PLAN_APPROVED.passed = true                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Вопросы для подтверждения:**

1. **Согласны ли вы с исключениями из v1 scope?**
   - JSON Schema validation (→ v2)
   - Capabilities endpoint (→ отдельная фича)
   - Сохранение system prompts в БД (→ v2)
   - UI для ввода system prompts (→ отдельная фича)

2. **Подтверждаете ли вы план модификации 14 провайдеров?**
   - Единый паттерн messages array
   - Graceful degradation для unsupported response_format

3. **Готовы ли начать реализацию?**
   - После подтверждения: `/aidd-generate`

---

**Статус**: ⏸️ **ОЖИДАНИЕ УТВЕРЖДЕНИЯ ПОЛЬЗОВАТЕЛЯ**
