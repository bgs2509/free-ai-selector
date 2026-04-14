"""Tests for seed data correctness."""

import pytest


@pytest.mark.unit
class TestSeedModelNames:
    """Verify seed model names match actual API model IDs."""

    def test_cerebras_model_name_is_8b(self):
        """Cerebras uses llama3.1-8b, not 70B."""
        from app.infrastructure.database.seed import SEED_MODELS

        cerebras = next(m for m in SEED_MODELS if m["provider"] == "Cerebras")
        assert "8B" in cerebras["name"], f"Cerebras name should contain '8B', got: {cerebras['name']}"
        assert "70B" not in cerebras["name"]

    def test_fireworks_model_name_is_gpt_oss(self):
        """Fireworks uses gpt-oss-20b, not Llama 70B."""
        from app.infrastructure.database.seed import SEED_MODELS

        fireworks = next(m for m in SEED_MODELS if m["provider"] == "Fireworks")
        assert "GPT-OSS" in fireworks["name"], f"Fireworks name should contain 'GPT-OSS', got: {fireworks['name']}"

    def test_novita_model_name_is_8b(self):
        """Novita uses llama-3.1-8b-instruct, not 70B."""
        from app.infrastructure.database.seed import SEED_MODELS

        novita = next(m for m in SEED_MODELS if m["provider"] == "Novita")
        assert "8B" in novita["name"], f"Novita name should contain '8B', got: {novita['name']}"
        assert "70B" not in novita["name"]

    def test_ollama_gemma4_e2b_exists(self):
        """Ollama Gemma4 E2B is in seed models."""
        from app.infrastructure.database.seed import SEED_MODELS

        ollama = next(
            (m for m in SEED_MODELS if m["provider"] == "Ollama-Gemma4-E2B"), None
        )
        assert ollama is not None, "Ollama-Gemma4-E2B not found in SEED_MODELS"
        assert ollama["api_format"] == "openai"
        assert "11434" in ollama["api_endpoint"]
        assert ollama["is_active"] is True
