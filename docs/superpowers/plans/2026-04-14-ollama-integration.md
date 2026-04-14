# Ollama Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ollama as a local LLM provider with tag "local", starting with gemma4:e2b model.

**Architecture:** Static provider approach — one class per Ollama model, inheriting OpenAICompatibleProvider. Ollama runs in Docker (separate project), business-api reaches it via localhost:11434. Dynamic BASE_URL via `_build_url()` override.

**Tech Stack:** Python 3.11+, httpx, pytest, Docker, Ollama

**Spec:** `docs/superpowers/specs/2026-04-14-ollama-integration-design.md`

---

### Task 1: Create ollama-docker project

**Files:**
- Create: `/home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker/docker-compose.yml`
- Create: `/home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker/.env.example`
- Create: `/home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker/Makefile`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
# Ollama LLM Server — Docker Compose
# Standalone service for local LLM inference via Ollama.
# Used by free-ai-selector and other projects.

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    network_mode: host
    volumes:
      - ollama-data:/root/.ollama
    env_file:
      - .env
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped

volumes:
  ollama-data:
    driver: local
    name: ollama-data
```

- [ ] **Step 2: Create .env.example**

```bash
# Ollama GPU optimization
OLLAMA_NUM_GPU=999
OLLAMA_FLASH_ATTENTION=1
# OLLAMA_HOST=0.0.0.0:11434  # default, uncomment to change
```

- [ ] **Step 3: Create .env from example**

```bash
cp .env.example .env
```

- [ ] **Step 4: Create Makefile**

```makefile
.PHONY: up down pull list logs ps

up:
	docker compose up -d

down:
	docker compose down

pull:
	docker exec ollama ollama pull $(MODEL)

list:
	docker exec ollama ollama list

logs:
	docker compose logs -f ollama

ps:
	docker exec ollama ollama ps
```

- [ ] **Step 5: Start Ollama and pull model**

```bash
cd /home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker
make up
# Wait for container to start
make pull MODEL=gemma4:e2b
make list
```

Expected: gemma4:e2b appears in list.

- [ ] **Step 6: Verify API is accessible**

```bash
curl -s http://localhost:11434/v1/models | python3 -m json.tool | head -20
```

Expected: JSON with model list including gemma4:e2b.

- [ ] **Step 7: Remove native Ollama installation**

```bash
# Stop native Ollama service
sudo systemctl stop ollama
sudo systemctl disable ollama
# Verify Docker Ollama is serving
curl -s http://localhost:11434/v1/models | head -5
```

- [ ] **Step 8: Commit**

```bash
cd /home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker
git init
git add docker-compose.yml .env.example Makefile
git commit -m "feat: initial ollama-docker project with GPU support"
```

---

### Task 2: Write failing tests for OllamaProvider

**Files:**
- Create: `services/free-ai-selector-business-api/tests/unit/test_ollama_provider.py`

- [ ] **Step 1: Write test file**

```python
"""Unit tests for Ollama provider (local LLM)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.mark.unit
class TestOllamaGemma4E2B:
    """Tests for OllamaGemma4E2B provider."""

    def test_init_defaults(self, monkeypatch):
        """Test initialization with default parameters."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.model == "gemma4:e2b"
        assert provider.api_url == "http://localhost:11434/v1/chat/completions"
        assert provider.timeout == 120.0

    def test_provider_name(self, monkeypatch):
        """Test provider name."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.get_provider_name() == "Ollama-Gemma4-E2B"

    def test_tags_include_local(self, monkeypatch):
        """Test that Ollama providers have 'local' tag."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        assert "local" in OllamaGemma4E2B.TAGS

    def test_supports_response_format(self, monkeypatch):
        """Test that Ollama supports response_format."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        assert OllamaGemma4E2B.SUPPORTS_RESPONSE_FORMAT is True

    def test_init_without_api_key_raises(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        with pytest.raises(ValueError, match="OLLAMA_API_KEY is required"):
            OllamaGemma4E2B()

    def test_custom_base_url(self, monkeypatch):
        """Test that OLLAMA_BASE_URL is respected."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://my-vps:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.api_url == "http://my-vps:11434/v1/chat/completions"

    def test_default_base_url_when_env_missing(self, monkeypatch):
        """Test fallback to localhost when OLLAMA_BASE_URL not set."""
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.api_url == "http://localhost:11434/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_generate_success(self, monkeypatch):
        """Test successful generation."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from Ollama"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await provider.generate("Test prompt")
            assert result == "Hello from Ollama"

    @pytest.mark.asyncio
    async def test_health_check_success(self, monkeypatch):
        """Test successful health check."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, monkeypatch):
        """Test health check when Ollama is down."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await provider.health_check()
            assert result is False


@pytest.mark.unit
class TestOllamaProviderRegistry:
    """Tests for Ollama provider in registry."""

    def test_ollama_providers_dict_has_gemma4(self):
        """Test OLLAMA_PROVIDERS contains Gemma4E2B."""
        from app.infrastructure.ai_providers.ollama import OLLAMA_PROVIDERS

        assert "Ollama-Gemma4-E2B" in OLLAMA_PROVIDERS

    def test_registry_has_ollama(self):
        """Test that ProviderRegistry includes Ollama provider."""
        from app.infrastructure.ai_providers.registry import ProviderRegistry

        assert ProviderRegistry.has_provider("Ollama-Gemma4-E2B")

    def test_registry_get_tags(self):
        """Test that registry returns local tag for Ollama."""
        from app.infrastructure.ai_providers.registry import ProviderRegistry

        tags = ProviderRegistry.get_tags("Ollama-Gemma4-E2B")
        assert "local" in tags

    def test_registry_get_api_key_env(self):
        """Test that registry returns correct API key env var."""
        from app.infrastructure.ai_providers.registry import ProviderRegistry

        assert ProviderRegistry.get_api_key_env("Ollama-Gemma4-E2B") == "OLLAMA_API_KEY"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_ollama_provider.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.infrastructure.ai_providers.ollama'`

- [ ] **Step 3: Commit failing tests**

```bash
git add services/free-ai-selector-business-api/tests/unit/test_ollama_provider.py
git commit -m "test: add failing tests for Ollama provider (RED)"
```

---

### Task 3: Implement OllamaProvider

**Files:**
- Create: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/ollama.py`

- [ ] **Step 1: Create ollama.py**

```python
"""
Ollama AI Provider integration (local LLM)

Integrates with Ollama server for local LLM inference.
Ollama exposes an OpenAI-compatible API at /v1/chat/completions.

Uses OLLAMA_BASE_URL env var for server address (default: http://localhost:11434).
API key is a dummy value — Ollama ignores the Authorization header.
"""

import os
from typing import ClassVar

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """
    Base class for Ollama-hosted models.

    All Ollama models share the same server URL and dummy API key.
    Subclasses only set PROVIDER_NAME and DEFAULT_MODEL.
    """

    API_KEY_ENV = "OLLAMA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = True
    TIMEOUT: ClassVar[float] = 120.0
    TAGS: ClassVar[set[str]] = {"local"}
    MAX_OUTPUT_TOKENS: ClassVar[int] = 4096

    def _get_base_url(self) -> str:
        """Get Ollama server base URL from environment."""
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def _build_url(self) -> str:
        """Build chat completions URL from OLLAMA_BASE_URL."""
        return f"{self._get_base_url()}/v1/chat/completions"

    def _get_models_url(self) -> str:
        """Build models URL from OLLAMA_BASE_URL."""
        return f"{self._get_base_url()}/v1/models"

    async def health_check(self) -> bool:
        """Health check using dynamic MODELS_URL."""
        import httpx

        from app.utils.logger import get_logger
        from app.utils.security import sanitize_error_message

        logger = get_logger(__name__)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        models_url = self._get_models_url()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return self._is_health_check_success(response)
            except Exception as e:
                err_msg = sanitize_error_message(e)
                logger.error(
                    "health_check_failed", provider=self.PROVIDER_NAME, error=err_msg
                )
                return False


class OllamaGemma4E2B(OllamaProvider):
    """Ollama Gemma 4 E2B (5.1B params, Q4_K_M, vision+audio+tools+thinking)."""

    PROVIDER_NAME = "Ollama-Gemma4-E2B"
    DEFAULT_MODEL = "gemma4:e2b"


# Dict for easy registration in registry.py
OLLAMA_PROVIDERS: dict[str, type[OllamaProvider]] = {
    "Ollama-Gemma4-E2B": OllamaGemma4E2B,
}
```

- [ ] **Step 2: Run tests**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_ollama_provider.py -v`

Expected: Tests about OllamaGemma4E2B pass. Registry tests still fail (not registered yet).

- [ ] **Step 3: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/ollama.py
git commit -m "feat: add OllamaProvider with Gemma4-E2B model"
```

---

### Task 4: Register Ollama in registry and seed

**Files:**
- Modify: `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`
- Modify: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

- [ ] **Step 1: Update registry.py — add import**

Add after the last import (line 37):
```python
from app.infrastructure.ai_providers.ollama import OLLAMA_PROVIDERS
```

- [ ] **Step 2: Update registry.py — add to PROVIDER_CLASSES**

Add after `"Scaleway": ScalewayProvider,` (line 58), before the closing `}`:
```python
    # Локальные провайдеры (Ollama)
    **OLLAMA_PROVIDERS,
```

- [ ] **Step 3: Update seed.py — add Ollama model**

Add after the last seed entry (after the Scaleway entry, before the closing `]`):
```python
    # ═══════════════════════════════════════════════════════════════════════════
    # Локальные провайдеры (Ollama)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Gemma4 E2B (Ollama)",
        "provider": "Ollama-Gemma4-E2B",
        "api_endpoint": "http://localhost:11434/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
```

- [ ] **Step 4: Run all Ollama tests**

Run: `docker compose exec free-ai-selector-business-api pytest tests/unit/test_ollama_provider.py -v`

Expected: ALL tests PASS including registry tests.

- [ ] **Step 5: Run existing tests to ensure no regressions**

Run: `docker compose exec free-ai-selector-business-api pytest tests/ -v --timeout=60`

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py
git add services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py
git commit -m "feat: register Ollama-Gemma4-E2B in provider registry and seed"
```

---

### Task 5: Add seed data test for Ollama

**Files:**
- Modify: `services/free-ai-selector-data-postgres-api/tests/unit/test_seed_data.py`

- [ ] **Step 1: Add test to TestSeedModelNames class**

Add at the end of the class:
```python
    def test_ollama_gemma4_e2b_exists(self):
        """Ollama Gemma4 E2B is in seed models."""
        from app.infrastructure.database.seed import SEED_MODELS

        ollama = next(
            (m for m in SEED_MODELS if m["provider"] == "Ollama-Gemma4-E2B"), None
        )
        assert ollama is not None, "Ollama-Gemma4-E2B not found in SEED_MODELS"
        assert ollama["api_format"] == "openai"
        assert "11434" in ollama["api_endpoint"]
        assert ollama["is_active"] is True
```

- [ ] **Step 2: Run test**

Run: `docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_seed_data.py -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add services/free-ai-selector-data-postgres-api/tests/unit/test_seed_data.py
git commit -m "test: add seed data test for Ollama-Gemma4-E2B"
```

---

### Task 6: Update docker-compose.yml and environment config

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add Ollama env vars to business-api**

Add after `SCALEWAY_API_KEY: ${SCALEWAY_API_KEY:-}` (line 121) in business-api environment:
```yaml
      # Ollama (local LLM)
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://localhost:11434}
      OLLAMA_API_KEY: ${OLLAMA_API_KEY:-ollama}
```

- [ ] **Step 2: Verify docker-compose is valid**

Run: `docker compose config --quiet`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Ollama env vars to business-api docker-compose"
```

---

### Task 7: Integration smoke test

- [ ] **Step 1: Ensure Ollama is running**

```bash
cd /home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker
make list
```

Expected: gemma4:e2b in list.

- [ ] **Step 2: Rebuild and restart free-ai-selector**

```bash
cd /home/bgs/ai-steward/Gena_Beeline_Local/free-ai-selector
make build && make up
```

- [ ] **Step 3: Run seed to add Ollama model to DB**

```bash
make seed
```

- [ ] **Step 4: Test Ollama via Business API**

```bash
curl -s -X POST http://localhost:8020/api/v1/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello in Russian", "tags": ["local"]}' | python3 -m json.tool
```

Expected: Response from Ollama-Gemma4-E2B with Russian text.

- [ ] **Step 5: Test without tag (general routing)**

```bash
curl -s -X POST http://localhost:8020/api/v1/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}' | python3 -m json.tool
```

Expected: Response from any provider (Ollama may or may not be chosen depending on score).

- [ ] **Step 6: Verify health check endpoint**

```bash
curl -s http://localhost:8020/health | python3 -m json.tool
```

Expected: healthy status.

---

### Task 8: Update CHANGELOG and documentation

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add CHANGELOG entry**

Add under the latest version or create new section:
```markdown
## [Unreleased]

### Added
- Ollama provider for local LLM support (`Ollama-Gemma4-E2B`)
- Tag-based filtering: `"local"` tag for Ollama models
- Configurable `OLLAMA_BASE_URL` for multi-environment deployment
- Separate `ollama-docker` project for containerized Ollama with GPU
```

- [ ] **Step 2: Update CLAUDE.md AI providers section**

Add Ollama to the providers list in CLAUDE.md.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md CLAUDE.md
git commit -m "docs: add Ollama integration to CHANGELOG and CLAUDE.md"
```
