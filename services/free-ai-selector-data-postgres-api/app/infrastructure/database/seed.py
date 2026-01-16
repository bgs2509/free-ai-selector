"""
Database seed script for AI Manager Platform - Data API Service

Seeds the database with initial AI models for verified free-tier providers (no credit card required):
- Groq (Llama 3.3 70B) - 20 RPM, 14,400 RPD, 1,800 tokens/sec
- Cerebras (Llama 3.3 70B) - 1M tokens/day, 30 RPM, 2,500+ tokens/sec
- SambaNova (Meta-Llama-3.3-70B-Instruct) - 20 RPM, 430 tokens/sec
- HuggingFace (Meta-Llama-3-8B-Instruct) - Rate limited, free inference API
- Cloudflare (Llama 3.3 70B FP8 Fast) - 10,000 Neurons/day
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM
from app.utils.security import sanitize_error_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initial AI models configuration - 14 verified free-tier providers (no credit card required)
# F008 SSOT: This is the SINGLE SOURCE OF TRUTH for provider configuration
SEED_MODELS = [
    # ═══════════════════════════════════════════════════════════════════════════
    # Существующие провайдеры (5 шт.)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Llama 3.3 70B Versatile",
        "provider": "Groq",
        "api_endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "GROQ_API_KEY",
    },
    {
        "name": "Llama 3.3 70B",
        "provider": "Cerebras",
        "api_endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "CEREBRAS_API_KEY",
    },
    {
        "name": "Meta-Llama-3.3-70B-Instruct",
        "provider": "SambaNova",
        "api_endpoint": "https://api.sambanova.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "SAMBANOVA_API_KEY",
    },
    {
        "name": "Meta-Llama-3-8B-Instruct",
        "provider": "HuggingFace",
        "api_endpoint": "https://router.huggingface.co/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "HUGGINGFACE_API_KEY",
    },
    {
        "name": "Llama 3.3 70B Instruct FP8 Fast",
        "provider": "Cloudflare",
        "api_endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "is_active": True,
        "api_format": "cloudflare",
        "env_var": "CLOUDFLARE_API_KEY",
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # Новые провайдеры F003 — Фаза 1: Приоритетные (3 шт.)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "DeepSeek Chat",
        "provider": "DeepSeek",
        "api_endpoint": "https://api.deepseek.com/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "DEEPSEEK_API_KEY",
    },
    {
        "name": "DeepSeek R1 (OpenRouter)",
        "provider": "OpenRouter",
        "api_endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "OPENROUTER_API_KEY",
    },
    {
        "name": "GPT-4o Mini (GitHub)",
        "provider": "GitHubModels",
        "api_endpoint": "https://models.inference.ai.azure.com/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "GITHUB_TOKEN",
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # Новые провайдеры F003 — Фаза 2: Дополнительные (4 шт.)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Llama 3.1 70B (Fireworks)",
        "provider": "Fireworks",
        "api_endpoint": "https://api.fireworks.ai/inference/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "FIREWORKS_API_KEY",
    },
    {
        "name": "Llama 3.3 70B (Hyperbolic)",
        "provider": "Hyperbolic",
        "api_endpoint": "https://api.hyperbolic.xyz/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "HYPERBOLIC_API_KEY",
    },
    {
        "name": "Llama 3.1 70B (Novita)",
        "provider": "Novita",
        "api_endpoint": "https://api.novita.ai/v3/openai/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "NOVITA_API_KEY",
    },
    {
        "name": "Llama 3.1 70B (Scaleway)",
        "provider": "Scaleway",
        "api_endpoint": "https://api.scaleway.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "SCALEWAY_API_KEY",
    },
    # ═══════════════════════════════════════════════════════════════════════════
    # Новые провайдеры F003 — Фаза 3: Резервные (2 шт.)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Llama 3.3 70B Turbo (Kluster)",
        "provider": "Kluster",
        "api_endpoint": "https://api.kluster.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "KLUSTER_API_KEY",
    },
    {
        "name": "Llama 3.1 70B (Nebius)",
        "provider": "Nebius",
        "api_endpoint": "https://api.studio.nebius.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
        "env_var": "NEBIUS_API_KEY",
    },
]


async def seed_database() -> None:
    """
    Seed database with initial AI models.

    Checks if models already exist before inserting to avoid duplicates.
    """
    logger.info("Starting database seeding...")

    async with AsyncSessionLocal() as session:
        try:
            for model_data in SEED_MODELS:
                # Check if model already exists
                query = select(AIModelORM).where(AIModelORM.name == model_data["name"])
                result = await session.execute(query)
                existing_model = result.scalar_one_or_none()

                if existing_model is not None:
                    logger.info(f"Model '{model_data['name']}' already exists, skipping...")
                    continue

                # Create new model
                new_model = AIModelORM(
                    name=model_data["name"],
                    provider=model_data["provider"],
                    api_endpoint=model_data["api_endpoint"],
                    success_count=0,
                    failure_count=0,
                    total_response_time=Decimal("0.0"),
                    request_count=0,
                    last_checked=None,
                    is_active=model_data["is_active"],
                    api_format=model_data.get("api_format", "openai"),
                    env_var=model_data.get("env_var", ""),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

                session.add(new_model)
                logger.info(f"Seeded model: {model_data['name']}")

            await session.commit()
            logger.info("Database seeding completed successfully!")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error seeding database: {sanitize_error_message(e)}")
            raise


async def clear_seed_data() -> None:
    """
    Clear all seed data from database.

    WARNING: This will delete all AI models from the seed list!
    Use with caution.
    """
    logger.warning("Clearing seed data from database...")

    async with AsyncSessionLocal() as session:
        try:
            for model_data in SEED_MODELS:
                query = select(AIModelORM).where(AIModelORM.name == model_data["name"])
                result = await session.execute(query)
                model = result.scalar_one_or_none()

                if model is not None:
                    await session.delete(model)
                    logger.info(f"Deleted model: {model_data['name']}")

            await session.commit()
            logger.info("Seed data cleared successfully!")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error clearing seed data: {sanitize_error_message(e)}")
            raise


if __name__ == "__main__":
    # Run seed script
    asyncio.run(seed_database())
