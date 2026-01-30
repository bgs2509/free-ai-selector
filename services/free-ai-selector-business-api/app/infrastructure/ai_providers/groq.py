"""
Groq AI Provider integration

Integrates with Groq API for ultra-fast AI inference on LPU (Language Processing Unit).
Free tier: Llama 3.3 70B (20 RPM, 14,400 RPD), no credit card required.
Speed: Up to 1,800 tokens/sec.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class GroqProvider(OpenAICompatibleProvider):
    """
    Groq API provider (OpenAI-compatible).

    Uses Groq's ultra-fast LPU for AI generation.
    No credit card required - fully free tier.
    """

    PROVIDER_NAME = "Groq"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODELS_URL = "https://api.groq.com/openai/v1/models"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    API_KEY_ENV = "GROQ_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
