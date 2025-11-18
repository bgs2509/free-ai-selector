"""
Database seed script for AI Manager Platform - Data API Service

Seeds the database with initial AI models for free providers:
- HuggingFace (Meta-Llama-3-8B-Instruct)
- Replicate (Meta-Llama-3-8B-Instruct)
- Together.ai (Meta-Llama-3-8B-Instruct)
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initial AI models configuration
SEED_MODELS = [
    {
        "name": "HuggingFace Meta-Llama-3-8B-Instruct",
        "provider": "HuggingFace",
        "api_endpoint": "https://router.huggingface.co/hf-inference/models/meta-llama/Meta-Llama-3-8B-Instruct",
        "is_active": True,
    },
    {
        "name": "Replicate Meta-Llama-3-8B-Instruct",
        "provider": "Replicate",
        "api_endpoint": "https://api.replicate.com/v1/models/meta/meta-llama-3-8b-instruct/predictions",
        "is_active": True,
    },
    {
        "name": "Together.ai Meta-Llama-3-8B-Instruct",
        "provider": "Together.ai",
        "api_endpoint": "https://api.together.xyz/v1/chat/completions",
        "is_active": True,
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
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

                session.add(new_model)
                logger.info(f"Seeded model: {model_data['name']}")

            await session.commit()
            logger.info("Database seeding completed successfully!")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error seeding database: {str(e)}")
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
            logger.error(f"Error clearing seed data: {str(e)}")
            raise


if __name__ == "__main__":
    # Run seed script
    asyncio.run(seed_database())
