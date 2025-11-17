"""
AI Manager Platform - Health Worker Service

Background worker for synthetic monitoring of AI providers.
Runs health checks hourly and updates model statistics.
Level 2 (Development Ready) maturity.
"""

import asyncio
import logging
import os
import time
from decimal import Decimal

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "aimanager_health_worker"
LOG_LEVEL = os.getenv("WORKER_LOG_LEVEL", "INFO")
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "3600"))  # seconds
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8001")
SYNTHETIC_TEST_PROMPT = os.getenv("SYNTHETIC_TEST_PROMPT", "Generate a simple greeting message")

# AI Provider API Keys
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY", "")
TOGETHER_AI_API_KEY = os.getenv("TOGETHER_AI_API_KEY", "")

# =============================================================================
# Logging Configuration
# =============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "'
    + SERVICE_NAME
    + '", "message": "%(message)s"}',
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# =============================================================================
# Health Check Functions
# =============================================================================


async def check_huggingface(endpoint: str) -> tuple[bool, float]:
    """Check HuggingFace model health."""
    if not HUGGINGFACE_API_KEY:
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"},
                json={
                    "inputs": SYNTHETIC_TEST_PROMPT,
                    "parameters": {"max_new_tokens": 50},
                },
            )
            response_time = time.time() - start_time
            # 200 OK or 503 (model loading) both indicate API is responding
            return response.status_code in [200, 503], response_time
    except Exception as e:
        logger.error(f"HuggingFace health check failed: {str(e)}")
        return False, time.time() - start_time


async def check_replicate(endpoint: str) -> tuple[bool, float]:
    """Check Replicate model health."""
    if not REPLICATE_API_KEY:
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.replicate.com/v1/models",
                headers={"Authorization": f"Token {REPLICATE_API_KEY}"},
            )
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Replicate health check failed: {str(e)}")
        return False, time.time() - start_time


async def check_together(endpoint: str) -> tuple[bool, float]:
    """Check Together.ai model health."""
    if not TOGETHER_AI_API_KEY:
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {TOGETHER_AI_API_KEY}"},
                json={
                    "model": "meta-llama/Meta-Llama-3-8B-Instruct",
                    "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                    "max_tokens": 50,
                },
            )
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Together.ai health check failed: {str(e)}")
        return False, time.time() - start_time


# =============================================================================
# Main Health Check Job
# =============================================================================


async def run_health_checks():
    """
    Run synthetic health checks for all AI models.

    Fetches models from Data API, checks each provider,
    and updates statistics based on results.
    """
    logger.info("Starting synthetic health checks...")

    try:
        # Fetch all active models from Data API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{DATA_API_URL}/api/v1/models?active_only=true")
            response.raise_for_status()
            models = response.json()

        logger.info(f"Checking health of {len(models)} models")

        # Check each model
        for model in models:
            model_id = model["id"]
            model_name = model["name"]
            provider = model["provider"]
            endpoint = model["api_endpoint"]

            logger.info(f"Checking {model_name} ({provider})...")

            # Run provider-specific health check
            if provider == "HuggingFace":
                is_healthy, response_time = await check_huggingface(endpoint)
            elif provider == "Replicate":
                is_healthy, response_time = await check_replicate(endpoint)
            elif provider == "Together.ai":
                is_healthy, response_time = await check_together(endpoint)
            else:
                logger.warning(f"Unknown provider: {provider}")
                continue

            # Update model statistics in Data API
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    if is_healthy:
                        logger.info(
                            f"{model_name}: ✅ Healthy (response time: {response_time:.2f}s)"
                        )
                        await client.post(
                            f"{DATA_API_URL}/api/v1/models/{model_id}/increment-success",
                            params={"response_time": response_time},
                        )
                    else:
                        logger.warning(f"{model_name}: ❌ Unhealthy")
                        await client.post(
                            f"{DATA_API_URL}/api/v1/models/{model_id}/increment-failure",
                            params={"response_time": response_time},
                        )
            except Exception as update_error:
                logger.error(f"Failed to update stats for {model_name}: {str(update_error)}")

        logger.info("Health checks completed successfully")

    except Exception as e:
        logger.error(f"Health check job failed: {str(e)}")


# =============================================================================
# Main Function
# =============================================================================


async def main():
    """
    Main worker entry point.

    Sets up scheduler and runs health checks at configured interval.
    """
    logger.info(f"Starting {SERVICE_NAME}")
    logger.info(f"Data API URL: {DATA_API_URL}")
    logger.info(f"Health check interval: {HEALTH_CHECK_INTERVAL} seconds")

    # Verify Data API connection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DATA_API_URL}/health")
            if response.status_code == 200:
                logger.info("Data API connection verified")
            else:
                logger.warning(f"Data API health check returned {response.status_code}")
    except Exception as e:
        logger.error(f"Data API connection failed: {str(e)}")
        raise

    # Run initial health check
    logger.info("Running initial health check...")
    await run_health_checks()

    # Setup scheduler for periodic checks
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_health_checks,
        trigger=IntervalTrigger(seconds=HEALTH_CHECK_INTERVAL),
        id="health_check_job",
        name="Synthetic AI Model Health Checks",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started. Next check in {HEALTH_CHECK_INTERVAL} seconds")

    # Keep worker running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        logger.info(f"{SERVICE_NAME} stopped")


if __name__ == "__main__":
    asyncio.run(main())
