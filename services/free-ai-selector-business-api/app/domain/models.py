"""
Domain models for AI Manager Platform - Business API Service

Lightweight DTOs for business logic layer.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class AIModelInfo:
    """
    AI Model information DTO.

    Minimal representation of AI model from Data API.
    """

    id: int
    name: str
    provider: str
    api_endpoint: str
    reliability_score: float
    is_active: bool
    # F008 SSOT fields
    api_format: str = "openai"  # Discriminator for health check dispatch
    env_var: str = ""  # ENV variable name for API key lookup
    # F010: Rolling window reliability fields
    effective_reliability_score: float = 0.0  # Score used for model selection
    recent_request_count: int = 0  # Requests in recent window
    decision_reason: str = "fallback"  # "recent_score" or "fallback"


@dataclass
class PromptRequest:
    """
    Prompt processing request DTO.

    Represents a user's request to process a prompt.
    """

    user_id: str
    prompt_text: str


@dataclass
class PromptResponse:
    """
    Prompt processing response DTO.

    Contains the AI-generated response and metadata.
    """

    prompt_text: str
    response_text: str
    selected_model_name: str
    selected_model_provider: str
    response_time: Decimal
    success: bool
    error_message: Optional[str] = None
