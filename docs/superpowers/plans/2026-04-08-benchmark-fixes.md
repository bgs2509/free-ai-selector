# Benchmark Fixes (Фазы 1+2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Исправить критические баги парсинга ответов провайдеров и расширить инфраструктуру маршрутизации (теги, per-provider лимиты, таймауты).

**Architecture:** 9 задач в 2 фазах. Фаза 1 — баги парсинга в base.py, fireworks.py, seed.py. Фаза 2 — ClassVar `TAGS`/`MAX_OUTPUT_TOKENS` в провайдерах, `tags` параметр в API, таймаут reasoning.

**Tech Stack:** Python 3.11+, pytest, httpx, FastAPI, Pydantic

---

## Task 1: OpenRouter reasoning fallback

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:170-180`
- Test: `services/free-ai-selector-business-api/tests/unit/test_new_providers.py`

- [ ] **Step 1: Write failing test**

В файле `tests/unit/test_new_providers.py` добавить тест в конец файла:

```python
@pytest.mark.unit
class TestBaseProviderReasoningFallback:
    """Tests for _parse_response reasoning field fallback."""

    def test_parse_response_reasoning_field_fallback(self):
        """OpenRouter returns 'reasoning' instead of 'reasoning_content'."""
        from app.infrastructure.ai_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning": "The user wants hello. I should say Hello.",
                }
            }]
        }
        response = provider._parse_response(result)
        assert response == "The user wants hello. I should say Hello."

    def test_parse_response_reasoning_content_still_works(self):
        """Existing reasoning_content fallback still works."""
        from app.infrastructure.ai_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "thinking...",
                }
            }]
        }
        response = provider._parse_response(result)
        assert response == "thinking..."

    def test_parse_response_content_takes_priority(self):
        """When content exists, reasoning fields are ignored."""
        from app.infrastructure.ai_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Hello!",
                    "reasoning": "thinking...",
                }
            }]
        }
        response = provider._parse_response(result)
        assert response == "Hello!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestBaseProviderReasoningFallback -v`
Expected: `test_parse_response_reasoning_field_fallback` FAILS (returns empty string)

- [ ] **Step 3: Implement fix**

В `base.py:_parse_response`, заменить блок fallback (строки 172-180):

```python
            # Fallback to reasoning_content / reasoning for reasoning models
            if not content:
                reasoning = (
                    message.get("reasoning_content", "")
                    or message.get("reasoning", "")
                )
                if reasoning:
                    content = str(reasoning).strip()
                    logger.info(
                        "using_reasoning_content",
                        provider=self.PROVIDER_NAME,
                        reasoning_chars=len(content),
                    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestBaseProviderReasoningFallback -v`
Expected: ALL 3 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py services/free-ai-selector-business-api/tests/unit/test_new_providers.py
git commit -m "fix: add 'reasoning' field fallback for OpenRouter R1 parsing"
```

---

## Task 2: Fireworks proprietary tags parsing

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`
- Test: `services/free-ai-selector-business-api/tests/unit/test_new_providers.py`

- [ ] **Step 1: Write failing test**

В файле `tests/unit/test_new_providers.py` добавить:

```python
@pytest.mark.unit
class TestFireworksReasoningTags:
    """Tests for Fireworks GPT-OSS-20B proprietary tag stripping."""

    def test_parse_strips_channel_tags_with_assistant(self):
        """Fireworks content with <|channel|> tags extracts text after <|start|>assistant."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '<|channel|>analysis<|message|>Some reasoning here.<|end|><|start|>assistant Hello!',
                }
            }]
        }
        response = provider._parse_response(result)
        assert response == "Hello!"

    def test_parse_strips_channel_tags_fallback_to_message(self):
        """When no <|start|>assistant, extract from <|message|> content."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '<|channel|>analysis<|message|>The answer is 42.<|end|>',
                }
            }]
        }
        response = provider._parse_response(result)
        assert response == "The answer is 42."

    def test_parse_normal_content_unchanged(self):
        """Normal content without tags passes through."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {"role": "assistant", "content": "Hello!"}
            }]
        }
        response = provider._parse_response(result)
        assert response == "Hello!"

    def test_parse_empty_after_assistant_tag_uses_message(self):
        """When text after <|start|>assistant is empty, fall back to <|message|>."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        result = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '<|channel|>analysis<|message|>User wants hello.<|end|><|start|>assistant',
                }
            }]
        }
        response = provider._parse_response(result)
        assert response == "User wants hello."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestFireworksReasoningTags -v`
Expected: `test_parse_strips_channel_tags_with_assistant` FAILS

- [ ] **Step 3: Implement fix**

Заменить содержимое `fireworks.py`:

```python
"""
Fireworks AI Provider integration

Интеграция с Fireworks API для генерации текста.
Бесплатный tier: $1 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

import re
from typing import Any

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class FireworksProvider(OpenAICompatibleProvider):
    """
    Fireworks API провайдер (OpenAI-compatible).

    Использует Fireworks API для генерации текста.
    Бесплатно: $1 кредитов, без кредитной карты.
    """

    PROVIDER_NAME = "Fireworks"
    BASE_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
    MODELS_URL = "https://api.fireworks.ai/inference/v1/models"
    DEFAULT_MODEL = "accounts/fireworks/models/gpt-oss-20b"
    API_KEY_ENV = "FIREWORKS_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = True  # Supports {"type": "json_object"}

    def _parse_response(self, result: dict[str, Any]) -> str:
        """Strip proprietary reasoning tags from gpt-oss-20b responses."""
        content = super()._parse_response(result)
        if "<|channel|>" in content:
            # Extract text after last <|start|>assistant
            match = re.search(
                r"<\|end\|><\|start\|>assistant\s*(.*)", content, re.DOTALL
            )
            if match and match.group(1).strip():
                return match.group(1).strip()
            # Fallback: extract text between <|message|> and <|end|>
            match = re.search(r"<\|message\|>(.*?)<\|end\|>", content, re.DOTALL)
            if match:
                return match.group(1).strip()
        return content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestFireworksReasoningTags -v`
Expected: ALL 4 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py services/free-ai-selector-business-api/tests/unit/test_new_providers.py
git commit -m "fix: strip Fireworks GPT-OSS-20B proprietary reasoning tags"
```

---

## Task 3: Fireworks max_tokens cap

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`
- Test: `services/free-ai-selector-business-api/tests/unit/test_new_providers.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestFireworksMaxTokensCap:
    """Tests for Fireworks max_tokens cap at 4096."""

    def test_build_payload_caps_max_tokens(self):
        """max_tokens > 4096 is capped to 4096."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        payload = provider._build_payload("hello", max_tokens=8192)
        assert payload["max_tokens"] == 4096

    def test_build_payload_keeps_lower_max_tokens(self):
        """max_tokens <= 4096 is unchanged."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        payload = provider._build_payload("hello", max_tokens=2048)
        assert payload["max_tokens"] == 2048

    def test_build_payload_default_max_tokens(self):
        """Default max_tokens (2048) is unchanged."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        payload = provider._build_payload("hello")
        assert payload["max_tokens"] == 2048
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestFireworksMaxTokensCap -v`
Expected: `test_build_payload_caps_max_tokens` FAILS (returns 8192)

- [ ] **Step 3: Implement fix**

В `fireworks.py` добавить метод `_build_payload` перед `_parse_response`:

```python
    def _build_payload(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Cap max_tokens at 4096 (Fireworks non-streaming limit)."""
        payload = super()._build_payload(prompt, **kwargs)
        if payload.get("max_tokens", 0) > 4096:
            payload["max_tokens"] = 4096
        return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestFireworksMaxTokensCap -v`
Expected: ALL 3 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py services/free-ai-selector-business-api/tests/unit/test_new_providers.py
git commit -m "fix: cap Fireworks max_tokens at 4096 for non-streaming"
```

---

## Task 4: Fix model names in seed.py

**Files:**
- Modify: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`
- Test: `services/free-ai-selector-data-postgres-api/tests/unit/test_domain_models.py` (если есть) или новый тест

- [ ] **Step 1: Write failing test**

Создать/добавить в `services/free-ai-selector-data-postgres-api/tests/unit/test_seed_data.py`:

```python
"""Tests for seed data correctness."""

import pytest


@pytest.mark.unit
class TestSeedModelNames:
    """Verify seed model names match actual API model IDs."""

    def test_cerebras_model_name_is_8b(self):
        """Cerebras uses llama3.1-8b, not 70B."""
        from app.infrastructure.database.seed import SEED_MODELS

        cerebras = next(m for m in SEED_MODELS if m["provider"] == "Cerebras")
        assert "8B" in cerebras["name"], f"Cerebras name should contain '8B', got: {cerebras['name']}"
        assert "70B" not in cerebras["name"]

    def test_fireworks_model_name_is_gpt_oss(self):
        """Fireworks uses gpt-oss-20b, not Llama 70B."""
        from app.infrastructure.database.seed import SEED_MODELS

        fireworks = next(m for m in SEED_MODELS if m["provider"] == "Fireworks")
        assert "GPT-OSS" in fireworks["name"], f"Fireworks name should contain 'GPT-OSS', got: {fireworks['name']}"

    def test_novita_model_name_is_8b(self):
        """Novita uses llama-3.1-8b-instruct, not 70B."""
        from app.infrastructure.database.seed import SEED_MODELS

        novita = next(m for m in SEED_MODELS if m["provider"] == "Novita")
        assert "8B" in novita["name"], f"Novita name should contain '8B', got: {novita['name']}"
        assert "70B" not in novita["name"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_seed_data.py -v`
Expected: ALL 3 FAIL

- [ ] **Step 3: Fix seed.py**

В `seed.py` изменить 3 записи:

Cerebras: `"name": "Llama 3.3 70B"` → `"name": "Llama 3.1 8B"`

Fireworks: `"name": "Llama 3.1 70B (Fireworks)"` → `"name": "GPT-OSS-20B (Fireworks)"`

Novita: `"name": "Llama 3.1 70B (Novita)"` → `"name": "Llama 3.1 8B Instruct (Novita)"`

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_seed_data.py -v`
Expected: ALL 3 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py services/free-ai-selector-data-postgres-api/tests/unit/test_seed_data.py
git commit -m "fix: correct model names in seed.py (Cerebras=8B, Fireworks=GPT-OSS-20B, Novita=8B)"
```

---

## Task 5: Add TAGS ClassVar to providers

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:85-92`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/groq.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cerebras.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/huggingface.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cloudflare.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/openrouter.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/github_models.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/novita.py`
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`
- Test: `services/free-ai-selector-business-api/tests/unit/test_new_providers.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestProviderTags:
    """Tests for TAGS ClassVar on providers."""

    def test_groq_tags(self):
        from app.infrastructure.ai_providers.groq import GroqProvider
        assert GroqProvider.TAGS == {"fast", "json", "code", "russian", "tools"}

    def test_cerebras_tags(self):
        from app.infrastructure.ai_providers.cerebras import CerebrasProvider
        assert CerebrasProvider.TAGS == {"fast", "json", "russian", "lightweight"}

    def test_huggingface_tags(self):
        from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
        assert HuggingFaceProvider.TAGS == {"russian", "lightweight"}

    def test_openrouter_tags(self):
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
        assert OpenRouterProvider.TAGS == {"code", "reasoning", "russian", "tools"}

    def test_github_tags(self):
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
        assert GitHubModelsProvider.TAGS == {"fast", "json", "russian", "tools"}

    def test_fireworks_tags(self):
        from app.infrastructure.ai_providers.fireworks import FireworksProvider
        assert FireworksProvider.TAGS == {"json", "code", "russian"}

    def test_novita_tags(self):
        from app.infrastructure.ai_providers.novita import NovitaProvider
        assert NovitaProvider.TAGS == {"json", "russian", "lightweight"}

    def test_base_tags_empty(self):
        from app.infrastructure.ai_providers.base import OpenAICompatibleProvider
        assert OpenAICompatibleProvider.TAGS == set()

    def test_registry_get_tags(self):
        from app.infrastructure.ai_providers.registry import ProviderRegistry
        tags = ProviderRegistry.get_tags("Groq")
        assert tags == {"fast", "json", "code", "russian", "tools"}

    def test_registry_get_tags_unknown(self):
        from app.infrastructure.ai_providers.registry import ProviderRegistry
        tags = ProviderRegistry.get_tags("Unknown")
        assert tags == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestProviderTags -v`
Expected: FAILS (no attribute TAGS)

- [ ] **Step 3: Implement**

В `base.py` строка 92 после `TIMEOUT`, добавить:

```python
    TAGS: ClassVar[set[str]] = set()
```

В каждый провайдер добавить `TAGS` после последнего ClassVar:

**groq.py:**
```python
    TAGS = {"fast", "json", "code", "russian", "tools"}
```

**cerebras.py:**
```python
    TAGS = {"fast", "json", "russian", "lightweight"}
```

**huggingface.py:**
```python
    TAGS = {"russian", "lightweight"}
```

**cloudflare.py** — найти ClassVar секцию и добавить:
```python
    TAGS = {"json", "code", "russian"}
```

**openrouter.py:**
```python
    TAGS = {"code", "reasoning", "russian", "tools"}
```

**github_models.py:**
```python
    TAGS = {"fast", "json", "russian", "tools"}
```

**fireworks.py:**
```python
    TAGS = {"json", "code", "russian"}
```

**novita.py:**
```python
    TAGS = {"json", "russian", "lightweight"}
```

В `registry.py` добавить метод `get_tags`:

```python
    @classmethod
    def get_tags(cls, name: str) -> set[str]:
        """Get provider tags without creating an instance."""
        provider_class = PROVIDER_CLASSES.get(name)
        if provider_class and hasattr(provider_class, "TAGS"):
            return provider_class.TAGS
        return set()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestProviderTags -v`
Expected: ALL 10 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/ services/free-ai-selector-business-api/tests/unit/test_new_providers.py
git commit -m "feat: add TAGS ClassVar to all providers and ProviderRegistry.get_tags()"
```

---

## Task 6: Add MAX_OUTPUT_TOKENS per-provider

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:90-92, 141`
- Modify: all provider files (groq, cerebras, huggingface, cloudflare, openrouter, github_models, fireworks, novita)
- Test: `services/free-ai-selector-business-api/tests/unit/test_new_providers.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestMaxOutputTokens:
    """Tests for MAX_OUTPUT_TOKENS per-provider."""

    def test_groq_max_output_tokens(self):
        from app.infrastructure.ai_providers.groq import GroqProvider
        assert GroqProvider.MAX_OUTPUT_TOKENS == 32768

    def test_cerebras_max_output_tokens(self):
        from app.infrastructure.ai_providers.cerebras import CerebrasProvider
        assert CerebrasProvider.MAX_OUTPUT_TOKENS == 8192

    def test_huggingface_max_output_tokens(self):
        from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
        assert HuggingFaceProvider.MAX_OUTPUT_TOKENS == 8192

    def test_openrouter_max_output_tokens(self):
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
        assert OpenRouterProvider.MAX_OUTPUT_TOKENS == 16384

    def test_github_max_output_tokens(self):
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
        assert GitHubModelsProvider.MAX_OUTPUT_TOKENS == 16384

    def test_fireworks_max_output_tokens(self):
        from app.infrastructure.ai_providers.fireworks import FireworksProvider
        assert FireworksProvider.MAX_OUTPUT_TOKENS == 4096

    def test_novita_max_output_tokens(self):
        from app.infrastructure.ai_providers.novita import NovitaProvider
        assert NovitaProvider.MAX_OUTPUT_TOKENS == 16384

    def test_base_default(self):
        from app.infrastructure.ai_providers.base import OpenAICompatibleProvider
        assert OpenAICompatibleProvider.MAX_OUTPUT_TOKENS == 2048

    def test_payload_uses_max_output_tokens(self):
        """_build_payload uses MAX_OUTPUT_TOKENS as default instead of hardcoded 2048."""
        from app.infrastructure.ai_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        payload = provider._build_payload("hello")
        assert payload["max_tokens"] == 32768

    def test_payload_kwarg_overrides_max_output_tokens(self):
        """Explicit max_tokens kwarg overrides MAX_OUTPUT_TOKENS."""
        from app.infrastructure.ai_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        payload = provider._build_payload("hello", max_tokens=1024)
        assert payload["max_tokens"] == 1024
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestMaxOutputTokens -v`
Expected: FAILS

- [ ] **Step 3: Implement**

В `base.py` после `TIMEOUT` добавить:

```python
    MAX_OUTPUT_TOKENS: ClassVar[int] = 2048
```

В `base.py:_build_payload` строка 141 заменить:

```python
            "max_tokens": kwargs.get("max_tokens", 2048),
```

на:

```python
            "max_tokens": kwargs.get("max_tokens", self.MAX_OUTPUT_TOKENS),
```

В каждый провайдер добавить `MAX_OUTPUT_TOKENS` после `TAGS`:

- `groq.py`: `MAX_OUTPUT_TOKENS = 32768`
- `cerebras.py`: `MAX_OUTPUT_TOKENS = 8192`
- `huggingface.py`: `MAX_OUTPUT_TOKENS = 8192`
- `cloudflare.py`: `MAX_OUTPUT_TOKENS = 4096`
- `openrouter.py`: `MAX_OUTPUT_TOKENS = 16384`
- `github_models.py`: `MAX_OUTPUT_TOKENS = 16384`
- `fireworks.py`: `MAX_OUTPUT_TOKENS = 4096`
- `novita.py`: `MAX_OUTPUT_TOKENS = 16384`

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestMaxOutputTokens -v`
Expected: ALL 10 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/ services/free-ai-selector-business-api/tests/unit/test_new_providers.py
git commit -m "feat: add MAX_OUTPUT_TOKENS per-provider, replace hardcoded 2048"
```

---

## Task 7: OpenRouter reasoning timeout

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/openrouter.py`
- Test: `services/free-ai-selector-business-api/tests/unit/test_new_providers.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.unit
class TestOpenRouterTimeout:
    """Tests for OpenRouter increased timeout for reasoning models."""

    def test_openrouter_timeout_180s(self):
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")
        assert provider.timeout == 180.0

    def test_groq_timeout_default(self):
        """Other providers keep default 30s."""
        from app.infrastructure.ai_providers.groq import GroqProvider

        provider = GroqProvider(api_key="test-key")
        assert provider.timeout == 30.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestOpenRouterTimeout -v`
Expected: `test_openrouter_timeout_180s` FAILS (returns 30.0)

- [ ] **Step 3: Implement**

В `openrouter.py` добавить после `SUPPORTS_RESPONSE_FORMAT`:

```python
    TIMEOUT = 180.0  # Reasoning models (R1) need 50-120s for long prompts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_new_providers.py::TestOpenRouterTimeout -v`
Expected: ALL 2 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/openrouter.py services/free-ai-selector-business-api/tests/unit/test_new_providers.py
git commit -m "feat: increase OpenRouter timeout to 180s for reasoning models"
```

---

## Task 8: Add tags parameter to PromptRequest and API schema

**Files:**
- Modify: `services/free-ai-selector-business-api/app/domain/models.py:42-55`
- Modify: `services/free-ai-selector-business-api/app/api/v1/schemas.py:16-36`
- Test: `services/free-ai-selector-business-api/tests/unit/test_f011b_schemas.py`

- [ ] **Step 1: Write failing test**

В `tests/unit/test_f011b_schemas.py` добавить:

```python
@pytest.mark.unit
class TestTagsParameter:
    """Tests for tags parameter in API schema."""

    def test_schema_accepts_tags(self):
        from app.api.v1.schemas import ProcessPromptRequest

        req = ProcessPromptRequest(prompt="hello", tags=["fast", "json"])
        assert req.tags == ["fast", "json"]

    def test_schema_tags_optional(self):
        from app.api.v1.schemas import ProcessPromptRequest

        req = ProcessPromptRequest(prompt="hello")
        assert req.tags is None

    def test_domain_prompt_request_tags(self):
        from app.domain.models import PromptRequest

        req = PromptRequest(user_id="u1", prompt_text="hello", tags=["code"])
        assert req.tags == ["code"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_f011b_schemas.py::TestTagsParameter -v`
Expected: FAILS (unexpected keyword argument 'tags')

- [ ] **Step 3: Implement**

В `app/domain/models.py`, PromptRequest, после `response_format`:

```python
    tags: Optional[list[str]] = None  # Filter models by provider tags
```

В `app/api/v1/schemas.py`, ProcessPromptRequest, после `response_format` Field:

```python
    tags: Optional[list[str]] = Field(
        None,
        description="Optional list of tags to filter models (e.g. ['fast', 'json']). Models must have ALL requested tags.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_f011b_schemas.py::TestTagsParameter -v`
Expected: ALL 3 PASS

- [ ] **Step 5: Commit**

```bash
git add services/free-ai-selector-business-api/app/domain/models.py services/free-ai-selector-business-api/app/api/v1/schemas.py services/free-ai-selector-business-api/tests/unit/test_f011b_schemas.py
git commit -m "feat: add tags parameter to PromptRequest and API schema"
```

---

## Task 9: Tag-based model filtering in process_prompt

**Files:**
- Modify: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`
- Test: `services/free-ai-selector-business-api/tests/unit/test_process_prompt_use_case.py`

- [ ] **Step 1: Write failing test**

В `tests/unit/test_process_prompt_use_case.py` добавить:

```python
@pytest.mark.unit
class TestTagFiltering:
    """Tests for tag-based model filtering."""

    def test_filter_by_tags_matches(self):
        """Models with all requested tags are kept."""
        from app.application.use_cases.process_prompt import ProcessPromptUseCase
        from app.domain.models import AIModelInfo

        uc = ProcessPromptUseCase.__new__(ProcessPromptUseCase)
        models = [
            AIModelInfo(id=1, name="M1", provider="Groq", api_endpoint="", reliability_score=0.9, is_active=True),
            AIModelInfo(id=2, name="M2", provider="Cerebras", api_endpoint="", reliability_score=0.8, is_active=True),
        ]
        result = uc._filter_by_tags(models, ["fast", "json"])
        assert len(result) == 2  # Both Groq and Cerebras have fast+json

    def test_filter_by_tags_excludes(self):
        """Models missing a requested tag are excluded."""
        from app.application.use_cases.process_prompt import ProcessPromptUseCase
        from app.domain.models import AIModelInfo

        uc = ProcessPromptUseCase.__new__(ProcessPromptUseCase)
        models = [
            AIModelInfo(id=1, name="M1", provider="Groq", api_endpoint="", reliability_score=0.9, is_active=True),
            AIModelInfo(id=2, name="M2", provider="HuggingFace", api_endpoint="", reliability_score=0.8, is_active=True),
        ]
        result = uc._filter_by_tags(models, ["json"])
        # Groq has json, HuggingFace does not
        assert len(result) == 1
        assert result[0].provider == "Groq"

    def test_filter_by_tags_none_returns_all(self):
        """No tags filter returns all models."""
        from app.application.use_cases.process_prompt import ProcessPromptUseCase
        from app.domain.models import AIModelInfo

        uc = ProcessPromptUseCase.__new__(ProcessPromptUseCase)
        models = [
            AIModelInfo(id=1, name="M1", provider="Groq", api_endpoint="", reliability_score=0.9, is_active=True),
        ]
        result = uc._filter_by_tags(models, None)
        assert len(result) == 1

    def test_filter_by_tags_fallback_when_empty(self):
        """If no models match tags, fallback to all models."""
        from app.application.use_cases.process_prompt import ProcessPromptUseCase
        from app.domain.models import AIModelInfo

        uc = ProcessPromptUseCase.__new__(ProcessPromptUseCase)
        models = [
            AIModelInfo(id=1, name="M1", provider="Groq", api_endpoint="", reliability_score=0.9, is_active=True),
        ]
        result = uc._filter_by_tags(models, ["nonexistent_tag"])
        assert len(result) == 1  # fallback to all
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_process_prompt_use_case.py::TestTagFiltering -v`
Expected: FAILS (no attribute _filter_by_tags)

- [ ] **Step 3: Implement**

В `process_prompt.py` добавить метод `_filter_by_tags` рядом с `_filter_json_capable_models`:

```python
    def _filter_by_tags(
        self,
        models: list[AIModelInfo],
        tags: Optional[list[str]],
    ) -> list[AIModelInfo]:
        """Filter models by provider tags. Fallback to all if none match."""
        if not tags:
            return models

        tag_set = set(tags)
        capable = [
            m for m in models
            if tag_set.issubset(ProviderRegistry.get_tags(m.provider))
        ]

        if capable:
            logger.info("tag_filter", total=len(models), matched=len(capable), tags=tags)
            return capable

        logger.warning("no_tag_matched_models", total=len(models), tags=tags, fallback="all")
        return models
```

В `execute()` вызвать `_filter_by_tags` после `_filter_json_capable_models` (после Step 2.5):

```python
        # Step 2.6: Filter by tags if requested
        tag_filtered_models = self._filter_by_tags(json_filtered_models, request.tags)
```

И заменить `json_filtered_models` на `tag_filtered_models` в дальнейшем коде (Step 3: sort).

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_process_prompt_use_case.py::TestTagFiltering -v`
Expected: ALL 4 PASS

- [ ] **Step 5: Run all tests**

Run: `docker compose exec free-ai-selector-business-api pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py services/free-ai-selector-business-api/tests/unit/test_process_prompt_use_case.py
git commit -m "feat: add tag-based model filtering in process_prompt"
```
