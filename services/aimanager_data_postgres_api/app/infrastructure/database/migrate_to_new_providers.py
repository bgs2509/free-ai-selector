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
import logging

from sqlalchemy import select

from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    logger.info("Starting migration to new providers...")

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
                        f"Removing obsolete provider: {model.provider} - {model.name}"
                    )
                    await session.delete(model)
                    deleted_count += 1

            # Remove models by obsolete model names
            for model_name in OBSOLETE_MODEL_NAMES:
                query = select(AIModelORM).where(AIModelORM.name == model_name)
                result = await session.execute(query)
                model = result.scalar_one_or_none()

                if model is not None:
                    logger.info(f"Removing obsolete model: {model.name} ({model.provider})")
                    await session.delete(model)
                    deleted_count += 1

            await session.commit()

            if deleted_count > 0:
                logger.info(
                    f"✅ Migration completed: removed {deleted_count} obsolete model(s)"
                )
            else:
                logger.info("✅ Migration completed: no obsolete models found")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {str(e)}")
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
            logger.error(f"Error checking migration status: {str(e)}")
            return False


if __name__ == "__main__":
    # Run migration script
    asyncio.run(migrate_to_new_providers())
