"""
Cerebras Inference AI Provider integration

Integrates with Cerebras Inference API for world's fastest AI inference.
Free tier: 1,000,000 tokens/day, 30 RPM, 60k TPM, no credit card required.
Speed: 2,500+ tokens/sec on Wafer-Scale Engine.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class CerebrasProvider(OpenAICompatibleProvider):
    """
    Cerebras Inference API provider (OpenAI-compatible).

    Uses Cerebras Wafer-Scale Engine for ultra-fast AI generation.
    No credit card required - fully free tier with 1M tokens/day.
    """

    PROVIDER_NAME = "Cerebras"
    BASE_URL = "https://api.cerebras.ai/v1/chat/completions"
    MODELS_URL = "https://api.cerebras.ai/v1/models"
    DEFAULT_MODEL = "llama3.1-8b"
    API_KEY_ENV = "CEREBRAS_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
