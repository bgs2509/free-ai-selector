"""
Migration script to remove obsolete AI providers and prepare for new ones.

Removes old providers that are no longer free-tier:
- Replicate (now requires paid subscription)
- Together.ai (now requires credit card)
- Old HuggingFace naming format

This migration runs automatically during container startup before seeding.
After removing obsolete models, the seed script will populate 6 new free-tier providers.
"""

import asyncio

from sqlalchemy import select

from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM
from app.utils.logger import setup_logging, get_logger
from app.utils.security import sanitize_error_message

logger = get_logger(__name__)

# List of obsolete providers to remove
OBSOLETE_PROVIDERS = [
    "Replicate",  # No longer free-tier
    "Together.ai",  # No longer free-tier without credit card
]

# List of obsolete model names to remove (old naming patterns)
OBSOLETE_MODEL_NAMES = [
    "HuggingFace Meta-Llama-3-8B-Instruct",  # Old naming, will be replaced by "Meta-Llama-3-8B-Instruct"
    "Replicate Meta-Llama-3-8B-Instruct",
    "Together.ai Meta-Llama-3-8B-Instruct",
]


async def migrate_to_new_providers() -> None:
    """
    Remove obsolete AI providers from database.

    This migration:
    1. Removes providers that are no longer free-tier (Replicate, Together.ai)
    2. Removes old model naming patterns
    3. Prepares database for new provider seeding

    Safe to run multiple times (idempotent).
    """
    setup_logging("free-ai-selector-data-postgres-api")
    logger.info("migration_started")

    async with AsyncSessionLocal() as session:
        try:
            deleted_count = 0

            # Remove models by obsolete provider names
            for provider_name in OBSOLETE_PROVIDERS:
                query = select(AIModelORM).where(AIModelORM.provider == provider_name)
                result = await session.execute(query)
                models = result.scalars().all()

                for model in models:
                    logger.info(
                        "removing_obsolete_provider",
                        provider=model.provider,
                        model=model.name,
                    )
                    await session.delete(model)
                    deleted_count += 1

            # Remove models by obsolete model names
            for model_name in OBSOLETE_MODEL_NAMES:
                query = select(AIModelORM).where(AIModelORM.name == model_name)
                result = await session.execute(query)
                model = result.scalar_one_or_none()

                if model is not None:
                    logger.info("removing_obsolete_model", model=model.name, provider=model.provider)
                    await session.delete(model)
                    deleted_count += 1

            await session.commit()

            if deleted_count > 0:
                logger.info("migration_completed", deleted_count=deleted_count)
            else:
                logger.info("migration_completed", deleted_count=0)

        except Exception as e:
            await session.rollback()
            logger.error("migration_failed", error=sanitize_error_message(e))
            raise


async def check_migration_needed() -> bool:
    """
    Check if migration is needed.

    Returns:
        True if obsolete providers exist in database, False otherwise
    """
    async with AsyncSessionLocal() as session:
        try:
            # Check for obsolete providers
            for provider_name in OBSOLETE_PROVIDERS:
                query = select(AIModelORM).where(AIModelORM.provider == provider_name)
                result = await session.execute(query)
                if result.scalar_one_or_none() is not None:
                    return True

            # Check for obsolete model names
            for model_name in OBSOLETE_MODEL_NAMES:
                query = select(AIModelORM).where(AIModelORM.name == model_name)
                result = await session.execute(query)
                if result.scalar_one_or_none() is not None:
                    return True

            return False

        except Exception as e:
            logger.error("migration_status_check_failed", error=sanitize_error_message(e))
            return False


if __name__ == "__main__":
    # Run migration script
    asyncio.run(migrate_to_new_providers())
