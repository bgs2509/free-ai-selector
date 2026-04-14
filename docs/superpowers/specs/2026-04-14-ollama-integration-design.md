# Design: Ollama Integration into Free AI Selector

**Date:** 2026-04-14
**Status:** Draft

## Goal

Add local LLM support via Ollama as a provider in free-ai-selector. Start with gemma4:e2b, support adding more models later. Deploy on local machines and VPS.

## Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Approach | Static (one class per model) | Matches existing architecture, KISS |
| Naming | `Ollama-Gemma4-E2B` | One provider = one class = one seed entry |
| Tag | `"local"` | Filter local models via existing tag system |
| Routing | General + tag-based | Mode C: competes in ranking + available via `tags: ["local"]` |
| Health monitoring | No changes | Health-worker tests all active models, including Ollama |
| Ollama deployment | Docker with host network | Separate project at `~/ai-steward/Gena_Beeline_Local/ollama-docker/` |
| OLLAMA_BASE_URL | Configurable via .env | Default `http://localhost:11434` |

## Hardware Context

**Thinkpad P73 (current):**
- GPU: Quadro P620, 4 GB VRAM
- CPU: Intel i7-9850H, 6 cores / 12 threads
- RAM: 48 GB
- gemma4:e2b (Q4_K_M, 5.1B params) needs ~4 GB VRAM — fits with partial offload

**VPS:** Various configurations, each with its own GPU and Ollama instance.

## Architecture

```
┌─────────────────────────┐
│  ollama-docker/         │  Separate project
│  docker-compose.yml     │  network_mode: host
│  ollama/ollama:latest   │  port 11434
└────────┬────────────────┘
         │ http://localhost:11434
         │
┌────────▼────────────────┐
│  free-ai-selector       │
│  business-api (host)    │
│  OllamaGemma4E2B        │
│  → /v1/chat/completions │
└─────────────────────────┘
```

Business-api runs on host network — reaches Ollama at localhost:11434 directly.

## Component 1: ollama-docker project

**Location:** `/home/bgs/ai-steward/Gena_Beeline_Local/ollama-docker/`

**Files:**
- `docker-compose.yml` — Ollama container with GPU, host network, persistent volume
- `.env.example` — OLLAMA_NUM_GPU, OLLAMA_FLASH_ATTENTION
- `Makefile` — up, down, pull, list, logs commands
- `README.md` — setup instructions for local and VPS

**docker-compose.yml:**
- Image: `ollama/ollama:latest`
- `network_mode: host` (port 11434 on host)
- Volume: `ollama-data:/root/.ollama` (models persist)
- GPU: `deploy.resources.reservations.devices` with nvidia driver
- Env: `OLLAMA_NUM_GPU=999`, `OLLAMA_FLASH_ATTENTION=1`
- `restart: unless-stopped`

## Component 2: OllamaProvider (business-api)

**New file:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/ollama.py`

```python
class OllamaProvider(OpenAICompatibleProvider):
    """Base class for all Ollama-hosted models."""
    API_KEY_ENV = "OLLAMA_API_KEY"          # dummy key, Ollama ignores it
    SUPPORTS_RESPONSE_FORMAT = True
    TIMEOUT = 120.0                         # slower than cloud (partial GPU offload)
    TAGS: ClassVar[set[str]] = {"local"}

    @property
    def BASE_URL(self):                     # dynamic from env
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return f"{base}/v1/chat/completions"

    @property
    def MODELS_URL(self):
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return f"{base}/v1/models"


class OllamaGemma4E2B(OllamaProvider):
    PROVIDER_NAME = "Ollama-Gemma4-E2B"
    DEFAULT_MODEL = "gemma4:e2b"

OLLAMA_PROVIDERS = {
    "Ollama-Gemma4-E2B": OllamaGemma4E2B,
}
```

**Note:** BASE_URL and MODELS_URL as properties (not class vars) to read OLLAMA_BASE_URL at call time, not import time. Need to verify this works with the base class — if base class reads them as class attributes, may need `_build_url()` override instead.

## Component 3: Registry update

**File:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/registry.py`

Add to `PROVIDER_CLASSES`:
```python
from .ollama import OLLAMA_PROVIDERS
# ...
PROVIDER_CLASSES = {
    # ... existing providers ...
    **OLLAMA_PROVIDERS,
}
```

## Component 4: Seed update

**File:** `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

Add to `SEED_MODELS`:
```python
{
    "name": "Ollama-Gemma4-E2B",
    "provider": "Ollama-Gemma4-E2B",
    "api_endpoint": "http://localhost:11434/v1/chat/completions",
    "is_active": True,
    "api_format": "openai",
},
```

## Component 5: Environment config

**`.env.example`** — add:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_KEY=ollama
```

**`docker-compose.yml`** — add to business-api environment:
```yaml
OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://localhost:11434}
OLLAMA_API_KEY: ${OLLAMA_API_KEY:-ollama}
```

## Adding a new Ollama model later

1. Add class in `ollama.py` (3 lines: class name, PROVIDER_NAME, DEFAULT_MODEL)
2. Add to `OLLAMA_PROVIDERS` dict in same file
3. Add seed entry in `seed.py`
4. Pull model: `docker exec ollama ollama pull <model>`

## Out of scope

- Changes to process_prompt.py (tag filtering already works)
- Changes to health-worker (tests all active models by default)
- Changes to base.py
- Changes to data API / ORM models
- Open WebUI or other Ollama frontends

## Risks

1. **BASE_URL as property vs class var** — base class may expect class attributes. Verify during implementation, fallback to `_build_url()` override.
2. **Timeout 120s** — if Ollama cold-starts (loading model into VRAM), first request may be slow. Ollama keeps model loaded for 5 min by default.
3. **VRAM contention** — if other processes grab VRAM, Ollama falls back to CPU. No code fix needed, just ops awareness.
