from app.utils.security import sanitize_error_message

"""
Migration script to rollback HuggingFace API endpoint

Rolls back the router.huggingface.co/hf-inference endpoint
to the correct api-inference.huggingface.co endpoint in the database.
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, update

from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLD_ENDPOINT = "https://router.huggingface.co/hf-inference/models/meta-llama/Meta-Llama-3-8B-Instruct"
NEW_ENDPOINT = "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"


async def migrate_huggingface_endpoint() -> None:
    """
    Update HuggingFace API endpoint in the database.

    Replaces the old deprecated endpoint with the new one.
    """
    logger.info("Starting HuggingFace endpoint migration...")

    async with AsyncSessionLocal() as session:
        try:
            # Find models with old HuggingFace endpoint
            query = select(AIModelORM).where(
                AIModelORM.api_endpoint == OLD_ENDPOINT
            )
            result = await session.execute(query)
            models_to_update = result.scalars().all()

            if not models_to_update:
                logger.info("No models found with old HuggingFace endpoint. Migration not needed.")
                return

            logger.info(f"Found {len(models_to_update)} model(s) to update:")
            for model in models_to_update:
                logger.info(f"  - ID: {model.id}, Name: {model.name}")

            # Update the endpoint
            update_query = (
                update(AIModelORM)
                .where(AIModelORM.api_endpoint == OLD_ENDPOINT)
                .values(
                    api_endpoint=NEW_ENDPOINT,
                    updated_at=datetime.utcnow()
                )
            )

            await session.execute(update_query)
            await session.commit()

            logger.info(f"✓ Successfully updated {len(models_to_update)} model(s)")
            logger.info(f"  Old endpoint: {OLD_ENDPOINT}")
            logger.info(f"  New endpoint: {NEW_ENDPOINT}")

        except Exception as e:
            await session.rollback()
            logger.error(f"✗ Error during migration: {sanitize_error_message(e)}")
            raise


async def verify_migration() -> None:
    """
    Verify that migration was successful.

    Checks if any models still have the old endpoint.
    """
    logger.info("\nVerifying migration...")

    async with AsyncSessionLocal() as session:
        try:
            # Check for old endpoint
            old_query = select(AIModelORM).where(
                AIModelORM.api_endpoint == OLD_ENDPOINT
            )
            old_result = await session.execute(old_query)
            old_models = old_result.scalars().all()

            # Check for new endpoint
            new_query = select(AIModelORM).where(
                AIModelORM.api_endpoint == NEW_ENDPOINT
            )
            new_result = await session.execute(new_query)
            new_models = new_result.scalars().all()

            if old_models:
                logger.warning(f"✗ Found {len(old_models)} model(s) still using old endpoint!")
                for model in old_models:
                    logger.warning(f"  - ID: {model.id}, Name: {model.name}")
            else:
                logger.info("✓ No models found with old endpoint")

            if new_models:
                logger.info(f"✓ Found {len(new_models)} model(s) using new endpoint:")
                for model in new_models:
                    logger.info(f"  - ID: {model.id}, Name: {model.name}")
            else:
                logger.info("  No models found with new endpoint")

        except Exception as e:
            logger.error(f"✗ Error during verification: {sanitize_error_message(e)}")
            raise


if __name__ == "__main__":
    # Run migration
    asyncio.run(migrate_huggingface_endpoint())

    # Verify migration
    asyncio.run(verify_migration())
