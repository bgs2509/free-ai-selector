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
