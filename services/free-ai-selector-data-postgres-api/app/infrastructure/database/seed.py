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
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM
from app.utils.logger import setup_logging, get_logger
from app.utils.security import sanitize_error_message

logger = get_logger(__name__)

# Initial AI models configuration - 12 verified free-tier providers (no credit card required)
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
    },
    {
        "name": "Llama 3.3 70B",
        "provider": "Cerebras",
        "api_endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    {
        "name": "Meta-Llama-3.3-70B-Instruct",
        "provider": "SambaNova",
        "api_endpoint": "https://api.sambanova.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    {
        "name": "Meta-Llama-3-8B-Instruct",
        "provider": "HuggingFace",
        "api_endpoint": "https://router.huggingface.co/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    {
        "name": "Llama 3.3 70B Instruct FP8 Fast",
        "provider": "Cloudflare",
        "api_endpoint": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "is_active": True,
        "api_format": "cloudflare",
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
    },
    {
        "name": "DeepSeek R1 (OpenRouter)",
        "provider": "OpenRouter",
        "api_endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    {
        "name": "GPT-4o Mini (GitHub)",
        "provider": "GitHubModels",
        "api_endpoint": "https://models.inference.ai.azure.com/chat/completions",
        "is_active": True,
        "api_format": "openai",
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
    },
    {
        "name": "Llama 3.3 70B (Hyperbolic)",
        "provider": "Hyperbolic",
        "api_endpoint": "https://api.hyperbolic.xyz/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    {
        "name": "Llama 3.1 70B (Novita)",
        "provider": "Novita",
        "api_endpoint": "https://api.novita.ai/v3/openai/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    {
        "name": "Llama 3.1 70B (Scaleway)",
        "provider": "Scaleway",
        "api_endpoint": "https://api.scaleway.ai/v1/chat/completions",
        "is_active": True,
        "api_format": "openai",
    },
    # ═══════════════════════════════════════════════════════════════════════════
]


async def seed_database() -> None:
    """
    Seed database with initial AI models (upsert + cleanup).

    F018: Upsert logic — обновляет поля существующих моделей вместо пропуска.
    Удаляет orphan-модели, которых нет в SEED_MODELS.
    """
    setup_logging("free-ai-selector-data-postgres-api")
    logger.info("seed_started")

    async with AsyncSessionLocal() as session:
        try:
            seed_names = {m["name"] for m in SEED_MODELS}

            for model_data in SEED_MODELS:
                # Check if model already exists
                query = select(AIModelORM).where(AIModelORM.name == model_data["name"])
                result = await session.execute(query)
                existing_model = result.scalar_one_or_none()

                if existing_model is not None:
                    # F018: Upsert — обновить поля если изменились
                    updated = False
                    for field in ("api_format", "api_endpoint", "is_active"):
                        new_val = model_data.get(field)
                        if new_val is not None and getattr(existing_model, field) != new_val:
                            setattr(existing_model, field, new_val)
                            updated = True
                    if updated:
                        existing_model.updated_at = datetime.utcnow()
                        logger.info("model_updated", model=model_data["name"])
                    else:
                        logger.info("model_up_to_date", model=model_data["name"])
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
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

                session.add(new_model)
                logger.info("model_seeded", model=model_data["name"])

            # F018: Cleanup orphan models (удалены из seed, но остались в БД)
            all_models_result = await session.execute(select(AIModelORM))
            for model in all_models_result.scalars():
                if model.name not in seed_names:
                    logger.warning("removing_orphan_model", model=model.name)
                    await session.delete(model)

            await session.commit()
            logger.info("seed_completed")

        except Exception as e:
            await session.rollback()
            logger.error("seed_failed", error=sanitize_error_message(e))
            raise


async def clear_seed_data() -> None:
    """
    Clear all seed data from database.

    WARNING: This will delete all AI models from the seed list!
    Use with caution.
    """
    logger.warning("clearing_seed_data")

    async with AsyncSessionLocal() as session:
        try:
            for model_data in SEED_MODELS:
                query = select(AIModelORM).where(AIModelORM.name == model_data["name"])
                result = await session.execute(query)
                model = result.scalar_one_or_none()

                if model is not None:
                    await session.delete(model)
                    logger.info("model_deleted", model=model_data["name"])

            await session.commit()
            logger.info("seed_data_cleared")

        except Exception as e:
            await session.rollback()
            logger.error("clear_seed_data_failed", error=sanitize_error_message(e))
            raise


if __name__ == "__main__":
    # Run seed script
    asyncio.run(seed_database())
