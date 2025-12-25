"""
Cohere AI Provider integration

Интеграция с Cohere API для генерации текста.
Бесплатный tier: 1000 вызовов в месяц, без требования кредитной карты.
Свой формат API (не OpenAI-совместимый).
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class CohereProvider(AIProviderBase):
    """
    Cohere API провайдер.

    Использует Cohere API v2 для генерации текста.
    Собственный формат запросов (не OpenAI-совместимый).
    Бесплатно: 1000 вызовов/месяц, без кредитной карты.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация Cohere провайдера.

        Args:
            api_key: Cohere API ключ (по умолчанию из COHERE_API_KEY)
            model: Название модели (по умолчанию command-r-plus)
        """
        self.api_key = api_key or os.getenv("COHERE_API_KEY", "")
        self.model = model or "command-r-plus"
        self.api_url = "https://api.cohere.com/v2/chat"
        self.timeout = 30.0  # секунды

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Генерация ответа через Cohere API.

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
            raise ValueError("Cohere API ключ обязателен")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Cohere v2 формат
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # Cohere v2 формат ответа
                if "message" in result and "content" in result["message"]:
                    content = result["message"]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        return content[0].get("text", "").strip()
                    elif isinstance(content, str):
                        return content.strip()

                logger.error(f"Неожиданный формат ответа Cohere: {sanitize_error_message(str(result))}")
                raise ValueError("Некорректный формат ответа от Cohere")

            except httpx.HTTPError as e:
                logger.error(f"Ошибка Cohere API: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Проверка доступности Cohere API.

        Returns:
            True если API доступен, False иначе
        """
        if not self.api_key:
            logger.warning("Cohere API ключ не настроен")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Используем models endpoint для проверки здоровья
        models_url = "https://api.cohere.com/v1/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Cohere health check не прошёл: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Получить имя провайдера."""
        return "Cohere"
