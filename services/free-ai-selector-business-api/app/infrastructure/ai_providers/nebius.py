"""
Nebius AI Provider integration

Интеграция с Nebius Studio API для генерации текста.
Бесплатный tier: $1 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class NebiusProvider(AIProviderBase):
    """
    Nebius Studio API провайдер.

    Использует Nebius API для генерации текста.
    OpenAI-совместимый формат запросов.
    Бесплатно: $1 кредитов, без кредитной карты.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация Nebius провайдера.

        Args:
            api_key: Nebius API ключ (по умолчанию из NEBIUS_API_KEY)
            model: Название модели (по умолчанию meta-llama/Meta-Llama-3.1-70B-Instruct)
        """
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY", "")
        self.model = model or "meta-llama/Meta-Llama-3.1-70B-Instruct"
        self.api_url = "https://api.studio.nebius.ai/v1/chat/completions"
        self.timeout = 30.0  # секунды

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерация ответа через Nebius API.

        Args:
            prompt: Текст промпта пользователя
            **kwargs: Дополнительные параметры
                - system_prompt (str, optional): System prompt для управления AI (F011-B)
                - response_format (dict, optional): Спецификация формата ответа (F011-B)
                - max_tokens (int, optional): Максимум токенов для генерации
                - temperature (float, optional): Температура сэмплирования

        Returns:
            Сгенерированный текст ответа

        Raises:
            httpx.HTTPError: При ошибке API запроса
            ValueError: При отсутствии API ключа
        """
        if not self.api_key:
            raise ValueError("Nebius API ключ обязателен")

        # F011-B: Extract new kwargs
        system_prompt = kwargs.get("system_prompt")
        response_format = kwargs.get("response_format")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # F011-B: Build messages array (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # OpenAI-совместимый формат
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }

        # F011-B: Add response_format if supported and provided
        if response_format:
            if self._supports_response_format():
                payload["response_format"] = response_format
            else:
                logger.warning(
                    "response_format_not_supported",
                    provider=self.get_provider_name(),
                    requested_format=response_format,
                )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # OpenAI-совместимый формат ответа
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    return message.get("content", "").strip()
                else:
                    logger.error(f"Неожиданный формат ответа Nebius: {sanitize_error_message(str(result))}")
                    raise ValueError("Некорректный формат ответа от Nebius")

            except httpx.HTTPError as e:
                logger.error(f"Ошибка Nebius API: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Проверка доступности Nebius API.

        Returns:
            True если API доступен, False иначе
        """
        if not self.api_key:
            logger.warning("Nebius API ключ не настроен")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Используем models endpoint для проверки здоровья
        models_url = "https://api.studio.nebius.ai/v1/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Nebius health check не прошёл: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Получить имя провайдера."""
        return "Nebius"

    def _supports_response_format(self) -> bool:
        """
        Check if provider supports response_format parameter.

        F011-B: Nebius support for response_format is TBD.
        Using graceful degradation (returns False).
        """
        return False
