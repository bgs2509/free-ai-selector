"""
Hyperbolic AI Provider integration

Интеграция с Hyperbolic API для генерации текста.
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


class HyperbolicProvider(AIProviderBase):
    """
    Hyperbolic API провайдер.

    Использует Hyperbolic API для генерации текста.
    OpenAI-совместимый формат запросов.
    Бесплатно: $1 кредитов, без кредитной карты.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация Hyperbolic провайдера.

        Args:
            api_key: Hyperbolic API ключ (по умолчанию из HYPERBOLIC_API_KEY)
            model: Название модели (по умолчанию meta-llama/Llama-3.3-70B-Instruct)
        """
        self.api_key = api_key or os.getenv("HYPERBOLIC_API_KEY", "")
        self.model = model or "meta-llama/Llama-3.3-70B-Instruct"
        self.api_url = "https://api.hyperbolic.xyz/v1/chat/completions"
        self.timeout = 30.0  # секунды

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерация ответа через Hyperbolic API.

        Args:
            prompt: Текст промпта пользователя
            **kwargs: Дополнительные параметры (max_tokens, temperature и т.д.)

        Returns:
            Сгенерированный текст ответа

        Raises:
            httpx.HTTPError: При ошибке API запроса
            ValueError: При отсутствии API ключа
        """
        if not self.api_key:
            raise ValueError("Hyperbolic API ключ обязателен")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # OpenAI-совместимый формат
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }

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
                    logger.error(f"Неожиданный формат ответа Hyperbolic: {sanitize_error_message(str(result))}")
                    raise ValueError("Некорректный формат ответа от Hyperbolic")

            except httpx.HTTPError as e:
                logger.error(f"Ошибка Hyperbolic API: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Проверка доступности Hyperbolic API.

        Returns:
            True если API доступен, False иначе
        """
        if not self.api_key:
            logger.warning("Hyperbolic API ключ не настроен")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Используем models endpoint для проверки здоровья
        models_url = "https://api.hyperbolic.xyz/v1/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Hyperbolic health check не прошёл: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Получить имя провайдера."""
        return "Hyperbolic"
