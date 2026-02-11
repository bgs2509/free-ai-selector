"""
Pydantic schemas for AI Manager Platform - Business API Service
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Prompt Processing Schemas
# =============================================================================


class ProcessPromptRequest(BaseModel):
    """Schema for prompt processing request."""

    prompt: str = Field(..., min_length=1, max_length=10000, description="User's prompt text")
    model_id: Optional[int] = Field(
        None,
        gt=0,
        description="Optional forced AI model ID. If unavailable or failing, fallback is used",
    )

    # NEW: F011-B - System Prompts & JSON Response Support
    system_prompt: Optional[str] = Field(
        None,
        max_length=5000,
        description="Optional system prompt to guide AI behavior (OpenAI-compatible providers only)"
    )

    # NEW: F011-B - System Prompts & JSON Response Support
    response_format: Optional[dict] = Field(
        None,
        description="Optional response format specification. Example: {'type': 'json_object'}"
    )


class ProcessPromptResponse(BaseModel):
    """Schema for prompt processing response."""

    prompt: str = Field(..., description="Original prompt text")
    response: str = Field(..., description="AI-generated response")
    selected_model: str = Field(..., description="Selected AI model name")
    provider: str = Field(..., description="AI provider name")
    response_time_seconds: Decimal = Field(..., description="Response time in seconds")
    success: bool = Field(..., description="Whether generation was successful")


# =============================================================================
# Model Statistics Schemas
# =============================================================================


class AIModelStatsResponse(BaseModel):
    """Schema for AI model statistics."""

    id: int = Field(..., description="Model ID")
    name: str = Field(..., description="Model name")
    provider: str = Field(..., description="Provider name")
    reliability_score: float = Field(..., description="Reliability score (0.0-1.0)")
    success_rate: float = Field(..., description="Success rate (0.0-1.0)")
    average_response_time: float = Field(..., description="Average response time in seconds")
    total_requests: int = Field(..., description="Total request count")
    is_active: bool = Field(..., description="Whether model is active")


class ModelsStatsResponse(BaseModel):
    """Schema for all models statistics."""

    models: list[AIModelStatsResponse] = Field(..., description="List of model statistics")
    total_models: int = Field(..., description="Total number of models")


# =============================================================================
# Health Check Schema
# =============================================================================


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    data_api_connection: str = Field(..., description="Data API connection status")
