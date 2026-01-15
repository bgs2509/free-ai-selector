"""
Base AI Provider interface

Defines the contract for all AI provider integrations.
"""

from abc import ABC, abstractmethod
from typing import Optional


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
                - system_prompt (str, optional): System prompt for AI guidance (F011-B)
                - response_format (dict, optional): Response format specification (F011-B)
                    Example: {"type": "json_object"}
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
