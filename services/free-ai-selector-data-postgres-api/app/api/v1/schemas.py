"""
Pydantic schemas for AI Manager Platform - Data API Service

These schemas define the API request/response models.
Uses Pydantic 2.0 for validation and serialization.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# AI Model Schemas
# =============================================================================


class AIModelBase(BaseModel):
    """Base schema for AI Model."""

    name: str = Field(..., min_length=1, max_length=255, description="AI model name")
    provider: str = Field(..., min_length=1, max_length=100, description="AI provider name")
    api_endpoint: str = Field(..., min_length=1, max_length=500, description="API endpoint URL")


class AIModelCreate(AIModelBase):
    """Schema for creating a new AI model."""

    is_active: bool = Field(default=True, description="Whether model is active")


class AIModelUpdate(BaseModel):
    """Schema for updating an AI model."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="AI model name")
    provider: Optional[str] = Field(None, min_length=1, max_length=100, description="AI provider name")
    api_endpoint: Optional[str] = Field(
        None, min_length=1, max_length=500, description="API endpoint URL"
    )
    is_active: Optional[bool] = Field(None, description="Whether model is active")


class AIModelStatsUpdate(BaseModel):
    """Schema for updating AI model statistics."""

    success_count: Optional[int] = Field(None, ge=0, description="Total successful requests")
    failure_count: Optional[int] = Field(None, ge=0, description="Total failed requests")
    total_response_time: Optional[Decimal] = Field(
        None, ge=0, description="Total response time in seconds"
    )
    request_count: Optional[int] = Field(None, ge=0, description="Total request count")


class AIModelResponse(AIModelBase):
    """Schema for AI model response."""

    id: int = Field(..., description="AI model ID")
    success_count: int = Field(..., ge=0, description="Total successful requests")
    failure_count: int = Field(..., ge=0, description="Total failed requests")
    total_response_time: Decimal = Field(..., ge=0, description="Total response time in seconds")
    request_count: int = Field(..., ge=0, description="Total request count")
    last_checked: Optional[datetime] = Field(None, description="Last health check timestamp")
    is_active: bool = Field(..., description="Whether model is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # F008 SSOT fields
    api_format: str = Field(
        default="openai",
        description="API format for health check dispatch (openai, gemini, cohere, huggingface, cloudflare)",
    )
    # F012: Rate Limit Handling
    available_at: Optional[datetime] = Field(
        None, description="Timestamp when provider becomes available after rate limit"
    )

    # Computed fields (long-term / cumulative)
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate (0.0 - 1.0)")
    average_response_time: float = Field(..., ge=0.0, description="Average response time in seconds")
    speed_score: float = Field(..., ge=0.0, le=1.0, description="Speed score (0.0 - 1.0)")
    reliability_score: float = Field(..., ge=0.0, le=1.0, description="Reliability score (0.0 - 1.0)")

    # F010: Recent metrics (rolling window)
    recent_success_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Success rate for recent period (null if no data)"
    )
    recent_request_count: Optional[int] = Field(
        None, ge=0, description="Request count in recent period"
    )
    recent_reliability_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Reliability score for recent period"
    )
    effective_reliability_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Score used for model selection (recent or fallback)"
    )
    decision_reason: Optional[str] = Field(
        None, description="Why effective score was chosen: 'recent_score' or 'fallback'"
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Prompt History Schemas
# =============================================================================


class PromptHistoryCreate(BaseModel):
    """Schema for creating a new prompt history record."""

    user_id: str = Field(..., min_length=1, max_length=255, description="User ID (Telegram or API)")
    prompt_text: str = Field(..., min_length=1, description="User's prompt text")
    selected_model_id: int = Field(..., gt=0, description="Selected AI model ID")
    response_text: Optional[str] = Field(None, description="AI response text")
    response_time: Decimal = Field(..., ge=0, description="Response time in seconds")
    success: bool = Field(..., description="Whether request was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class PromptHistoryResponse(BaseModel):
    """Schema for prompt history response."""

    id: int = Field(..., description="History record ID")
    user_id: str = Field(..., description="User ID")
    prompt_text: str = Field(..., description="User's prompt text")
    selected_model_id: int = Field(..., description="Selected AI model ID")
    response_text: Optional[str] = Field(None, description="AI response text")
    response_time: Decimal = Field(..., description="Response time in seconds")
    success: bool = Field(..., description="Whether request was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Statistics Schemas
# =============================================================================


class ModelStatisticsResponse(BaseModel):
    """Schema for model statistics response."""

    total_requests: int = Field(..., ge=0, description="Total request count")
    successful_requests: int = Field(..., ge=0, description="Successful request count")
    failed_requests: int = Field(..., ge=0, description="Failed request count")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate (0.0 - 1.0)")


# =============================================================================
# Health Check Schema
# =============================================================================


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    database: str = Field(..., description="Database connection status")
