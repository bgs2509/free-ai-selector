"""
HTTP client for Data API communication

Implements HTTP-only data access pattern (framework requirement).
Business services must never access database directly.
"""

import logging
import os
from decimal import Decimal
from typing import List, Optional

import httpx

from app.domain.models import AIModelInfo

logger = logging.getLogger(__name__)

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
        headers = {"Content-Type": "application/json"}
        if self.request_id:
            headers["X-Request-ID"] = self.request_id
        return headers

    async def get_all_models(self, active_only: bool = True) -> List[AIModelInfo]:
        """
        Get all AI models from Data API.

        Args:
            active_only: If True, return only active models (default: True)

        Returns:
            List of AIModelInfo objects

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/models",
                params={"active_only": active_only},
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
                )
                for model in models_data
            ]

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch models from Data API: {str(e)}")
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
            )

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch model {model_id} from Data API: {str(e)}")
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
            logger.error(f"Failed to increment success for model {model_id}: {str(e)}")
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
            logger.error(f"Failed to increment failure for model {model_id}: {str(e)}")
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
            logger.error(f"Failed to create history record: {str(e)}")
            raise
