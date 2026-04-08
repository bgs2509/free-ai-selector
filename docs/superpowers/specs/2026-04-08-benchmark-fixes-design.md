# Benchmark Fixes: Парсинг + Маршрутизация (Фазы 1+2)

**Дата:** 2026-04-08
**Источник:** `docs/research/2026-04-08-benchmark-action-plan.md`

---

## Фаза 1: Критические баги (4 задачи)

### 1.1 OpenRouter reasoning fallback

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:_parse_response`

OpenRouter возвращает reasoning в поле `reasoning` (не `reasoning_content`). При `content: null` текущий код не находит ответ.

**Изменение:** Добавить fallback-цепочку: `content` → `reasoning_content` → `reasoning`.

### 1.2 Fireworks proprietary tags

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`

Fireworks GPT-OSS-20B возвращает reasoning в `content` с тегами `<|channel|>analysis<|message|>...<|end|><|start|>assistant`.

**Изменение:** Override `_parse_response()` в `FireworksProvider`:
- Если `<|channel|>` в content — извлечь текст после `<|end|><|start|>assistant`
- Fallback: текст между `<|message|>` и `<|end|>`

### 1.3 Названия моделей в seed.py

**Файл:** `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

Несовпадение имён с реальными API model ID:
- Cerebras: `"Llama 3.3 70B"` → `"Llama 3.1 8B"` (реальный: `llama3.1-8b`)
- Fireworks: `"Llama 3.1 70B (Fireworks)"` → `"GPT-OSS-20B (Fireworks)"` (реальный: `gpt-oss-20b`)
- Novita: `"Llama 3.1 70B (Novita)"` → `"Llama 3.1 8B Instruct (Novita)"` (реальный: `llama-3.1-8b-instruct`)

### 1.4 Fireworks max_tokens cap

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`

Fireworks без стриминга возвращает 400 при `max_tokens > 4096`.

**Изменение:** Override `_build_payload()` — ограничить `max_tokens` до 4096.

---

## Фаза 2: Расширение маршрутизации (5 задач)

### 2.1 Теги моделей в ClassVar провайдеров

Добавить `TAGS: ClassVar[set[str]]` в каждый провайдер:

| Провайдер | Теги |
|-----------|------|
| Groq | `fast`, `json`, `code`, `russian`, `tools` |
| Cerebras | `fast`, `json`, `russian`, `lightweight` |
| HuggingFace | `russian`, `lightweight` |
| Cloudflare | `json`, `code`, `russian` |
| OpenRouter | `code`, `reasoning`, `russian`, `tools` |
| GitHub | `fast`, `json`, `russian`, `tools` |
| Fireworks | `json`, `code`, `russian` |
| Novita | `json`, `russian`, `lightweight` |

Добавить `ProviderRegistry.get_tags(provider_name) -> set[str]`.

### 2.2 MAX_OUTPUT_TOKENS per-provider

`ClassVar[int]` в каждом провайдере, используется в `_build_payload()` вместо хардкода 2048:

| Провайдер | MAX_OUTPUT_TOKENS |
|-----------|-------------------|
| Base (default) | 2048 |
| Groq | 32768 |
| Cerebras | 8192 |
| HuggingFace | 8192 |
| Cloudflare | 4096 |
| OpenRouter | 16384 |
| GitHub | 16384 |
| Fireworks | 4096 |
| Novita | 16384 |

`_build_payload()` использует `self.MAX_OUTPUT_TOKENS` как дефолт вместо хардкода 2048.

### 2.3 API-параметр tags в PromptRequest

Добавить `tags: Optional[list[str]] = None` в `PromptRequest`.

В `process_prompt.py`: если `tags` задан — фильтровать модели через `ProviderRegistry.get_tags()`, оставляя только модели с ВСЕМИ запрошенными тегами. Если после фильтрации список пуст — fallback на все модели.

### 2.4 Таймаут для reasoning моделей

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/openrouter.py`

OpenRouter DeepSeek R1 отвечает 50-120с на длинных промптах. Дефолт 30с недостаточен.

**Изменение:** `TIMEOUT: ClassVar[float] = 180.0` в `OpenRouterProvider`.

### 2.5 SambaNova, DeepSeek, Hyperbolic, Scaleway

Провайдеры не участвовали в бенчмарке — теги и MAX_OUTPUT_TOKENS не назначаются. Оставить дефолтные значения из base class (`TAGS = set()`, `MAX_OUTPUT_TOKENS = 2048`).
