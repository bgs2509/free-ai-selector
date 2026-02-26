"""
HTTP client for Data API communication

Implements HTTP-only data access pattern (framework requirement).
Business services must never access database directly.
"""

import os
from decimal import Decimal
from typing import Any, List, Optional

import httpx
from app.utils.security import sanitize_error_message
from app.utils.request_id import REQUEST_ID_HEADER, create_tracing_headers

from app.domain.models import AIModelInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)

DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8001")
REQUEST_TIMEOUT = 10.0  # seconds


class DataAPIClient:
    """
    HTTP client for Data API service.

    Provides methods to interact with AI models and prompt history data.
    """

    def __init__(self, base_url: str = DATA_API_URL, request_id: Optional[str] = None):
        """
        Initialize Data API client.

        Args:
            base_url: Base URL of Data API service
            request_id: Optional request ID for tracing
        """
        self.base_url = base_url.rstrip("/")
        self.request_id = request_id
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    async def close(self) -> None:
        """Close HTTP client connection."""
        await self.client.aclose()

    def _get_headers(self) -> dict:
        """
        Get request headers with optional request ID.

        Returns:
            Headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            **create_tracing_headers(),
        }
        if self.request_id:
            headers.setdefault(REQUEST_ID_HEADER, self.request_id)
        return headers

    async def get_all_models(
        self,
        active_only: bool = True,
        include_recent: bool = True,
        available_only: bool = False,
    ) -> List[AIModelInfo]:
        """
        Get all AI models from Data API.

        Args:
            active_only: If True, return only active models (default: True)
            include_recent: If True, include recent metrics for F010 (default: True)
            available_only: If True, exclude models with available_at > now() (default: False)

        Returns:
            List of AIModelInfo objects with effective_reliability_score for model selection

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/models",
                params={
                    "active_only": active_only,
                    "include_recent": include_recent,
                    "available_only": available_only,
                    "window_days": 7,
                },
                headers=self._get_headers(),
            )
            response.raise_for_status()

            models_data = response.json()
            return [
                AIModelInfo(
                    id=model["id"],
                    name=model["name"],
                    provider=model["provider"],
                    api_endpoint=model["api_endpoint"],
                    reliability_score=model["reliability_score"],
                    is_active=model["is_active"],
                    api_format=model.get("api_format", "openai"),
                    # F010: Use effective_score for selection, fallback to reliability_score
                    effective_reliability_score=model.get(
                        "effective_reliability_score"
                    ) or model["reliability_score"],
                    recent_request_count=model.get("recent_request_count") or 0,
                    decision_reason=model.get("decision_reason") or "fallback",
                    # F012: Rate Limit Handling
                    available_at=model.get("available_at"),
                )
                for model in models_data
            ]

        except httpx.HTTPError as e:
            logger.error("data_api_fetch_models_failed", error=sanitize_error_message(e))
            raise

    async def get_model_by_id(self, model_id: int) -> Optional[AIModelInfo]:
        """
        Get AI model by ID from Data API.

        Args:
            model_id: AI model ID

        Returns:
            AIModelInfo object if found, None otherwise

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/models/{model_id}", headers=self._get_headers()
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()

            model_data = response.json()
            return AIModelInfo(
                id=model_data["id"],
                name=model_data["name"],
                provider=model_data["provider"],
                api_endpoint=model_data["api_endpoint"],
                reliability_score=model_data["reliability_score"],
                is_active=model_data["is_active"],
                api_format=model_data.get("api_format", "openai"),
            )

        except httpx.HTTPError as e:
            logger.error("data_api_fetch_model_failed", model_id=model_id, error=sanitize_error_message(e))
            raise

    async def increment_success(self, model_id: int, response_time: float) -> None:
        """
        Increment success count for a model.

        Args:
            model_id: AI model ID
            response_time: Response time in seconds

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/models/{model_id}/increment-success",
                params={"response_time": response_time},
                headers=self._get_headers(),
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            logger.error("data_api_increment_success_failed", model_id=model_id, error=sanitize_error_message(e))
            raise

    async def increment_failure(self, model_id: int, response_time: float) -> None:
        """
        Increment failure count for a model.

        Args:
            model_id: AI model ID
            response_time: Response time in seconds

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/models/{model_id}/increment-failure",
                params={"response_time": response_time},
                headers=self._get_headers(),
            )
            response.raise_for_status()

        except httpx.HTTPError as e:
            logger.error("data_api_increment_failure_failed", model_id=model_id, error=sanitize_error_message(e))
            raise

    async def set_availability(
        self,
        model_id: int,
        retry_after_seconds: int,
        reason: str | None = None,
        error_type: str | None = None,
        source: str | None = None,
    ) -> None:
        """
        Set model availability cooldown (F012: Rate Limit Handling).

        After receiving a 429 rate limit, set the model's available_at timestamp.
        The model will be excluded from selection until available_at is reached.

        Args:
            model_id: AI model ID
            retry_after_seconds: Seconds until model becomes available (0 = clear cooldown)
            reason: Причина изменения доступности (например: rate_limit)
            error_type: Тип ошибки, вызвавшей cooldown
            source: Источник вызова (например: process_prompt)

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            params: dict[str, Any] = {"retry_after_seconds": retry_after_seconds}
            if reason:
                params["reason"] = reason
            if error_type:
                params["error_type"] = error_type
            if source:
                params["source"] = source

            response = await self.client.patch(
                f"{self.base_url}/api/v1/models/{model_id}/availability",
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            logger.info(
                "availability_updated",
                model_id=model_id,
                retry_after_seconds=retry_after_seconds,
                reason=reason,
                error_type=error_type,
                source=source,
            )

        except httpx.HTTPError as e:
            logger.error("data_api_set_availability_failed", model_id=model_id, error=sanitize_error_message(e))
            raise

    async def create_history(
        self,
        user_id: str,
        prompt_text: str,
        selected_model_id: int,
        response_text: Optional[str],
        response_time: Decimal,
        success: bool,
        error_message: Optional[str] = None,
    ) -> int:
        """
        Create a prompt history record.

        Args:
            user_id: User ID
            prompt_text: User's prompt
            selected_model_id: Selected AI model ID
            response_text: AI response text
            response_time: Response time in seconds
            success: Whether request was successful
            error_message: Optional error message

        Returns:
            Created history record ID

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            payload = {
                "user_id": user_id,
                "prompt_text": prompt_text,
                "selected_model_id": selected_model_id,
                "response_text": response_text,
                "response_time": str(response_time),
                "success": success,
                "error_message": error_message,
            }

            response = await self.client.post(
                f"{self.base_url}/api/v1/history", json=payload, headers=self._get_headers()
            )
            response.raise_for_status()

            history_data = response.json()
            return history_data["id"]

        except httpx.HTTPError as e:
            logger.error("data_api_create_history_failed", error=sanitize_error_message(e))
            raise
