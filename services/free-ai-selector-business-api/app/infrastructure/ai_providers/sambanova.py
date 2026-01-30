"""
SambaNova Cloud AI Provider integration

Integrates with SambaNova Cloud API for fast AI inference.
Free tier: Llama 3.3 70B (20 RPM), Llama 405B (10 RPM), no credit card required.
Speed: 430+ tokens/sec.
Bonus: $5 credits = 30M+ tokens on Llama 8B.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class SambanovaProvider(OpenAICompatibleProvider):
    """
    SambaNova Cloud API provider (OpenAI-compatible).

    Uses SambaNova's optimized RDU hardware for fast AI generation.
    No credit card required - fully free tier.
    Supports response_format (F011-B).
    """

    PROVIDER_NAME = "SambaNova"
    BASE_URL = "https://api.sambanova.ai/v1/chat/completions"
    MODELS_URL = "https://api.sambanova.ai/v1/models"
    DEFAULT_MODEL = "Meta-Llama-3.3-70B-Instruct"
    API_KEY_ENV = "SAMBANOVA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = True  # F011-B: Supports {"type": "json_object"}
