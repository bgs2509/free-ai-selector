"""
HuggingFace AI Provider integration

Integrates with HuggingFace Inference Providers API (OpenAI-compatible).
Free tier available with HuggingFace account.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class HuggingFaceProvider(OpenAICompatibleProvider):
    """
    HuggingFace Inference Providers API provider (OpenAI-compatible).

    Uses router.huggingface.co OpenAI-compatible API.
    Supports multiple inference providers under unified endpoint.
    """

    PROVIDER_NAME = "HuggingFace"
    BASE_URL = "https://router.huggingface.co/v1/chat/completions"
    MODELS_URL = "https://router.huggingface.co/v1/models"
    DEFAULT_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"
    API_KEY_ENV = "HUGGINGFACE_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
