"""
Domain models for AI Manager Platform - Data API Service

These are pure domain models (not tied to database implementation).
They represent the core business entities in the domain.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class AIModel:
    """
    AI Model domain entity.

    Represents an AI model with its reliability metrics.
    The reliability score is calculated as:
        reliability_score = (success_rate × 0.6) + (speed_score × 0.4)
    """

    id: Optional[int]
    name: str
    provider: str
    api_endpoint: str
    success_count: int
    failure_count: int
    total_response_time: Decimal
    request_count: int
    last_checked: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # F008 SSOT fields
    api_format: str = "openai"  # Discriminator for health check dispatch
    env_var: str = ""  # ENV variable name for API key lookup

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage (0.0 - 1.0)."""
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count

    @property
    def average_response_time(self) -> float:
        """Calculate average response time in seconds."""
        if self.request_count == 0:
            return 0.0
        return float(self.total_response_time) / self.request_count

    @property
    def speed_score(self) -> float:
        """
        Calculate speed score (0.0 - 1.0).
        Faster response time = higher score.
        Assumes 10 seconds is the baseline (score = 0.0).
        """
        avg_time = self.average_response_time
        if avg_time == 0.0:
            return 1.0
        if avg_time >= 10.0:
            return 0.0
        return 1.0 - (avg_time / 10.0)

    @property
    def reliability_score(self) -> float:
        """
        Calculate reliability score (0.0 - 1.0).
        Formula: reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

        Note: If success_rate = 0, returns 0.0 (F011 fix).
        """
        if self.success_rate == 0.0:
            return 0.0
        return (self.success_rate * 0.6) + (self.speed_score * 0.4)


@dataclass
class PromptHistory:
    """
    Prompt History domain entity.

    Records each prompt processing request with metrics.
    """

    id: Optional[int]
    user_id: str
    prompt_text: str
    selected_model_id: int
    response_text: Optional[str]
    response_time: Decimal
    success: bool
    error_message: Optional[str]
    created_at: datetime
