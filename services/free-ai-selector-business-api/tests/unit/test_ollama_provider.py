"""Unit tests for Ollama provider (local LLM)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.mark.unit
class TestOllamaGemma4E2B:
    """Tests for OllamaGemma4E2B provider."""

    def test_init_defaults(self, monkeypatch):
        """Test initialization with default parameters."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.model == "gemma4:e2b"
        assert provider.api_url == "http://localhost:11434/v1/chat/completions"
        assert provider.timeout == 120.0

    def test_provider_name(self, monkeypatch):
        """Test provider name."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.get_provider_name() == "Ollama-Gemma4-E2B"

    def test_tags_include_local(self):
        """Test that Ollama providers have 'local' tag."""
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        assert "local" in OllamaGemma4E2B.TAGS

    def test_supports_response_format(self):
        """Test that Ollama supports response_format."""
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        assert OllamaGemma4E2B.SUPPORTS_RESPONSE_FORMAT is True

    def test_init_without_api_key_raises(self, monkeypatch):
        """Test that missing API key raises ValueError."""
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        with pytest.raises(ValueError, match="OLLAMA_API_KEY is required"):
            OllamaGemma4E2B()

    def test_custom_base_url(self, monkeypatch):
        """Test that OLLAMA_BASE_URL is respected."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://my-vps:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.api_url == "http://my-vps:11434/v1/chat/completions"

    def test_default_base_url_when_env_missing(self, monkeypatch):
        """Test fallback to localhost when OLLAMA_BASE_URL not set."""
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")
        assert provider.api_url == "http://localhost:11434/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_generate_success(self, monkeypatch):
        """Test successful generation."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from Ollama"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await provider.generate("Test prompt")
            assert result == "Hello from Ollama"

    @pytest.mark.asyncio
    async def test_health_check_success(self, monkeypatch):
        """Test successful health check."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, monkeypatch):
        """Test health check when Ollama is down."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        from app.infrastructure.ai_providers.ollama import OllamaGemma4E2B

        provider = OllamaGemma4E2B(api_key="ollama")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await provider.health_check()
            assert result is False


@pytest.mark.unit
class TestOllamaProviderRegistry:
    """Tests for Ollama provider in registry."""

    def test_ollama_providers_dict_has_gemma4(self):
        """Test OLLAMA_PROVIDERS contains Gemma4E2B."""
        from app.infrastructure.ai_providers.ollama import OLLAMA_PROVIDERS

        assert "Ollama-Gemma4-E2B" in OLLAMA_PROVIDERS

    def test_registry_has_ollama(self):
        """Test that ProviderRegistry includes Ollama provider."""
        from app.infrastructure.ai_providers.registry import ProviderRegistry

        assert ProviderRegistry.has_provider("Ollama-Gemma4-E2B")

    def test_registry_get_tags(self):
        """Test that registry returns local tag for Ollama."""
        from app.infrastructure.ai_providers.registry import ProviderRegistry

        tags = ProviderRegistry.get_tags("Ollama-Gemma4-E2B")
        assert "local" in tags

    def test_registry_get_api_key_env(self):
        """Test that registry returns correct API key env var."""
        from app.infrastructure.ai_providers.registry import ProviderRegistry

        assert ProviderRegistry.get_api_key_env("Ollama-Gemma4-E2B") == "OLLAMA_API_KEY"
