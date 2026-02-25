"""
Base AI Provider interface

Defines the contract for all AI provider integrations.

F013: OpenAICompatibleProvider — базовый класс для OpenAI-совместимых провайдеров.
Устраняет ~1100 строк дублирования через унификацию generate/health_check.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Optional

import httpx

from app.domain.exceptions import ProviderError
from app.utils.security import sanitize_error_message

logger = logging.getLogger(__name__)


class AIProviderBase(ABC):
    """
    Abstract base class for AI provider integrations.

    All AI provider implementations must inherit from this class
    and implement the generate method.
    """

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response for given prompt.

        Args:
            prompt: User's prompt text
            **kwargs: Additional provider-specific parameters
                - system_prompt (str): System prompt for AI guidance (F011-B)
                - response_format (dict): Response format specification
                    (F011-B). Example: {"type": "json_object"}
                - max_tokens (int, optional): Maximum tokens to generate
                - temperature (float, optional): Sampling temperature

        Returns:
            Generated response text

        Raises:
            Exception: If generation fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is healthy and responding.

        Returns:
            True if provider is healthy, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get provider name for logging/identification.

        Returns:
            Provider name string
        """
        pass


class OpenAICompatibleProvider(AIProviderBase):
    """
    Базовый класс для OpenAI-совместимых провайдеров.

    Наследники определяют только class-level конфигурацию.
    Вся логика generate/health_check унифицирована.

    F013: Устраняет ~1100 строк дублирования через унификацию.
    """

    # === Конфигурация (переопределяется в наследниках) ===
    PROVIDER_NAME: ClassVar[str] = ""
    BASE_URL: ClassVar[str] = ""  # chat/completions endpoint
    MODELS_URL: ClassVar[str] = ""  # health check endpoint
    DEFAULT_MODEL: ClassVar[str] = ""
    API_KEY_ENV: ClassVar[str] = ""
    SUPPORTS_RESPONSE_FORMAT: ClassVar[bool] = False
    EXTRA_HEADERS: ClassVar[dict[str, str]] = {}
    TIMEOUT: ClassVar[float] = 30.0

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация провайдера с валидацией API key.

        Args:
            api_key: API ключ (или из env)
            model: Модель (или default)

        Raises:
            ValueError: Если API key отсутствует
        """
        self.api_key = api_key or os.getenv(self.API_KEY_ENV, "")
        if not self.api_key:
            raise ValueError(f"{self.API_KEY_ENV} is required")

        self.model = model or self.DEFAULT_MODEL
        self.api_url = self._build_url()
        self.timeout = self.TIMEOUT

    def _build_url(self) -> str:
        """Hook для динамических URL (HuggingFace)."""
        return self.BASE_URL

    def _build_headers(self) -> dict[str, str]:
        """Hook для дополнительных заголовков (OpenRouter)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.EXTRA_HEADERS)
        return headers

    def _build_payload(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Формирование payload для OpenAI API."""
        # F011-B: Extract system_prompt and response_format
        system_prompt = kwargs.get("system_prompt")
        response_format = kwargs.get("response_format")

        # Build messages array
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }

        # F011-B: Add response_format if supported
        if response_format:
            if self.SUPPORTS_RESPONSE_FORMAT:
                payload["response_format"] = response_format
            else:
                logger.warning(
                    "response_format_not_supported",
                    extra={
                        "provider": self.PROVIDER_NAME,
                        "requested_format": response_format,
                    },
                )

        return payload

    def _parse_response(self, result: dict[str, Any]) -> str:
        """Парсинг OpenAI-совместимого ответа."""
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            return str(content).strip()
        else:
            err_msg = sanitize_error_message(str(result))
            logger.error(f"Unexpected {self.PROVIDER_NAME} response: {err_msg}")
            raise ValueError(f"Invalid response format from {self.PROVIDER_NAME}")

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Генерация ответа через OpenAI-совместимый API.

        Args:
            prompt: Пользовательский промпт
            **kwargs: system_prompt, response_format, max_tokens, temperature, top_p

        Returns:
            Сгенерированный текст

        Raises:
            ProviderError: При ошибках API
        """
        headers = self._build_headers()
        payload = self._build_payload(prompt, **kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.api_url, headers=headers, json=payload
                )
                response.raise_for_status()
                result = response.json()
                return self._parse_response(result)

            except httpx.HTTPStatusError as e:
                # F022: Пробрасываем с HTTP-кодом для classify_error()
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise

            except httpx.HTTPError as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} API error: {err_msg}")
                raise ProviderError(f"{self.PROVIDER_NAME} error: {e}") from e

    def _is_health_check_success(self, response: httpx.Response) -> bool:
        """Hook для кастомной проверки успеха (GitHub Models)."""
        return response.status_code == 200

    async def health_check(self) -> bool:
        """Проверка здоровья через GET /models."""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(self.MODELS_URL, headers=headers)
                return self._is_health_check_success(response)
            except Exception as e:
                err_msg = sanitize_error_message(e)
                logger.error(f"{self.PROVIDER_NAME} health check failed: {err_msg}")
                return False

    def get_provider_name(self) -> str:
        """Имя провайдера для логирования."""
        return self.PROVIDER_NAME

    def _supports_response_format(self) -> bool:
        """Поддержка response_format (F011-B)."""
        return self.SUPPORTS_RESPONSE_FORMAT
