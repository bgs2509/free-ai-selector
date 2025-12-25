"""
AI Manager Platform - Health Worker Service

Background worker for synthetic monitoring of AI providers.
Runs health checks hourly and updates model statistics.
Level 2 (Development Ready) maturity.

Supports 16 verified free-tier AI providers (no credit card required):
- Google AI Studio (Gemini 2.5 Flash)
- Groq (Llama 3.3 70B - 1,800 tokens/sec)
- Cerebras (Llama 3.3 70B - 2,500+ tokens/sec)
- SambaNova (Meta-Llama-3.3-70B-Instruct)
- HuggingFace (Meta-Llama-3-8B-Instruct)
- Cloudflare Workers AI (10,000 Neurons/day)
- DeepSeek (5M tokens free)
- Cohere (1000 calls/month)
- OpenRouter (50 RPD free models)
- GitHub Models (50 RPD via PAT)
- Fireworks ($1 credits)
- Hyperbolic ($1 credits)
- Novita ($10 credits)
- Scaleway (1M tokens/month, EU)
- Kluster ($5 credits)
- Nebius ($1 credits)
"""

import asyncio
import logging
import os
import time

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.security import sanitize_error_message

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "free-ai-selector-health-worker"
LOG_LEVEL = os.getenv("WORKER_LOG_LEVEL", "INFO")
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "3600"))  # seconds
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8001")
SYNTHETIC_TEST_PROMPT = os.getenv("SYNTHETIC_TEST_PROMPT", "Generate a simple greeting message")

# AI Provider API Keys - 16 verified free-tier providers
# Существующие провайдеры (6 шт.)
GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
# Новые провайдеры F003 (10 шт.)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
HYPERBOLIC_API_KEY = os.getenv("HYPERBOLIC_API_KEY", "")
NOVITA_API_KEY = os.getenv("NOVITA_API_KEY", "")
SCALEWAY_API_KEY = os.getenv("SCALEWAY_API_KEY", "")
KLUSTER_API_KEY = os.getenv("KLUSTER_API_KEY", "")
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")

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


async def check_google_gemini(endpoint: str) -> tuple[bool, float]:
    """
    Check Google AI Studio (Gemini) model health.

    Uses Gemini API format with API key in query params.
    Free tier: 10 RPM, 250 RPD, no credit card required.
    """
    if not GOOGLE_AI_STUDIO_API_KEY:
        logger.warning("Google AI Studio API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Gemini API format
            payload = {
                "contents": [{"parts": [{"text": SYNTHETIC_TEST_PROMPT}]}],
                "generationConfig": {
                    "maxOutputTokens": 50,
                    "temperature": 0.7,
                },
            }
            params = {"key": GOOGLE_AI_STUDIO_API_KEY}

            response = await client.post(endpoint, json=payload, params=params)
            response_time = time.time() - start_time

            # Success if 200 OK
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Google Gemini health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_groq(endpoint: str) -> tuple[bool, float]:
    """
    Check Groq model health.

    Uses OpenAI-compatible API format.
    Free tier: 20 RPM, 14,400 RPD, 1,800 tokens/sec, no credit card required.
    """
    if not GROQ_API_KEY:
        logger.warning("Groq API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # OpenAI-compatible format
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }

            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time

            # Success if 200 OK
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Groq health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_cerebras(endpoint: str) -> tuple[bool, float]:
    """
    Check Cerebras Inference model health.

    Uses OpenAI-compatible API format.
    Free tier: 1M tokens/day, 30 RPM, 2,500+ tokens/sec, no credit card required.
    """
    if not CEREBRAS_API_KEY:
        logger.warning("Cerebras API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # OpenAI-compatible format
            headers = {
                "Authorization": f"Bearer {CEREBRAS_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.3-70b",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }

            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time

            # Success if 200 OK
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Cerebras health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_sambanova(endpoint: str) -> tuple[bool, float]:
    """
    Check SambaNova Cloud model health.

    Uses OpenAI-compatible API format.
    Free tier: 20 RPM, 430 tokens/sec, no credit card required.
    """
    if not SAMBANOVA_API_KEY:
        logger.warning("SambaNova API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # OpenAI-compatible format
            headers = {
                "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "Meta-Llama-3.3-70B-Instruct",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }

            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time

            # Success if 200 OK
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"SambaNova health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_huggingface(endpoint: str) -> tuple[bool, float]:
    """
    Check HuggingFace Inference API model health.

    Uses HuggingFace-specific API format.
    Free tier: Rate limited, no credit card required.
    """
    if not HUGGINGFACE_API_KEY:
        logger.warning("HuggingFace API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
            payload = {
                "inputs": SYNTHETIC_TEST_PROMPT,
                "parameters": {"max_new_tokens": 50},
            }

            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time

            # 200 OK or 503 (model loading) both indicate API is responding
            return response.status_code in [200, 503], response_time
    except Exception as e:
        logger.error(f"HuggingFace health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_cloudflare(endpoint: str) -> tuple[bool, float]:
    """
    Check Cloudflare Workers AI model health.

    Uses Cloudflare-specific API format with account ID in URL.
    Free tier: 10,000 Neurons/day, no credit card required.
    """
    if not CLOUDFLARE_API_TOKEN:
        logger.warning("Cloudflare API token not configured")
        return False, 0.0
    if not CLOUDFLARE_ACCOUNT_ID:
        logger.warning("Cloudflare account ID not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                "Content-Type": "application/json",
            }

            # Replace {account_id} placeholder in endpoint URL
            actual_endpoint = endpoint.replace("{account_id}", CLOUDFLARE_ACCOUNT_ID)

            payload = {
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }

            response = await client.post(actual_endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time

            # Success if 200 OK
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Cloudflare health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


# =============================================================================
# New Provider Health Checks (F003)
# =============================================================================


async def check_deepseek(endpoint: str) -> tuple[bool, float]:
    """Check DeepSeek API health. OpenAI-compatible format."""
    if not DEEPSEEK_API_KEY:
        logger.warning("DeepSeek API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"DeepSeek health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_cohere(endpoint: str) -> tuple[bool, float]:
    """Check Cohere API health. Cohere v2 format."""
    if not COHERE_API_KEY:
        logger.warning("Cohere API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {COHERE_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "model": "command-r-plus",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Cohere health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_openrouter(endpoint: str) -> tuple[bool, float]:
    """Check OpenRouter API health. OpenAI-compatible format."""
    if not OPENROUTER_API_KEY:
        logger.warning("OpenRouter API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/free-ai-selector",
            }
            payload = {
                "model": "deepseek/deepseek-r1:free",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"OpenRouter health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_github_models(endpoint: str) -> tuple[bool, float]:
    """Check GitHub Models API health. OpenAI-compatible format."""
    if not GITHUB_TOKEN:
        logger.warning("GitHub Token not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"GitHub Models health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_fireworks(endpoint: str) -> tuple[bool, float]:
    """Check Fireworks API health. OpenAI-compatible format."""
    if not FIREWORKS_API_KEY:
        logger.warning("Fireworks API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {FIREWORKS_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "accounts/fireworks/models/llama-v3p1-70b-instruct",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Fireworks health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_hyperbolic(endpoint: str) -> tuple[bool, float]:
    """Check Hyperbolic API health. OpenAI-compatible format."""
    if not HYPERBOLIC_API_KEY:
        logger.warning("Hyperbolic API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {HYPERBOLIC_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "meta-llama/Llama-3.3-70B-Instruct",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Hyperbolic health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_novita(endpoint: str) -> tuple[bool, float]:
    """Check Novita API health. OpenAI-compatible format."""
    if not NOVITA_API_KEY:
        logger.warning("Novita API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {NOVITA_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "meta-llama/llama-3.1-70b-instruct",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Novita health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_scaleway(endpoint: str) -> tuple[bool, float]:
    """Check Scaleway API health. OpenAI-compatible format."""
    if not SCALEWAY_API_KEY:
        logger.warning("Scaleway API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {SCALEWAY_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "llama-3.1-70b-instruct",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Scaleway health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_kluster(endpoint: str) -> tuple[bool, float]:
    """Check Kluster API health. OpenAI-compatible format."""
    if not KLUSTER_API_KEY:
        logger.warning("Kluster API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {KLUSTER_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "klusterai/Meta-Llama-3.3-70B-Instruct-Turbo",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Kluster health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


async def check_nebius(endpoint: str) -> tuple[bool, float]:
    """Check Nebius API health. OpenAI-compatible format."""
    if not NEBIUS_API_KEY:
        logger.warning("Nebius API key not configured")
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {NEBIUS_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(f"Nebius health check failed: {sanitize_error_message(e)}")
        return False, time.time() - start_time


# =============================================================================
# Provider Check Dispatch Dictionary
# =============================================================================

PROVIDER_CHECK_FUNCTIONS = {
    # Существующие провайдеры (6)
    "GoogleGemini": check_google_gemini,
    "Groq": check_groq,
    "Cerebras": check_cerebras,
    "SambaNova": check_sambanova,
    "HuggingFace": check_huggingface,
    "Cloudflare": check_cloudflare,
    # Новые провайдеры F003 (10)
    "DeepSeek": check_deepseek,
    "Cohere": check_cohere,
    "OpenRouter": check_openrouter,
    "GitHubModels": check_github_models,
    "Fireworks": check_fireworks,
    "Hyperbolic": check_hyperbolic,
    "Novita": check_novita,
    "Scaleway": check_scaleway,
    "Kluster": check_kluster,
    "Nebius": check_nebius,
}


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

            # Run provider-specific health check using dispatch dictionary
            check_func = PROVIDER_CHECK_FUNCTIONS.get(provider)
            if check_func:
                is_healthy, response_time = await check_func(endpoint)
            else:
                logger.warning(f"Unknown provider: {provider}, skipping health check")
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
                logger.error(f"Failed to update stats for {model_name}: {sanitize_error_message(update_error)}")

        logger.info("Health checks completed successfully")

    except Exception as e:
        logger.error(f"Health check job failed: {sanitize_error_message(e)}")


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

    # Log configured providers
    configured_providers = []
    # Существующие провайдеры (6)
    if GOOGLE_AI_STUDIO_API_KEY:
        configured_providers.append("GoogleGemini")
    if GROQ_API_KEY:
        configured_providers.append("Groq")
    if CEREBRAS_API_KEY:
        configured_providers.append("Cerebras")
    if SAMBANOVA_API_KEY:
        configured_providers.append("SambaNova")
    if HUGGINGFACE_API_KEY:
        configured_providers.append("HuggingFace")
    if CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID:
        configured_providers.append("Cloudflare")
    # Новые провайдеры F003 (10)
    if DEEPSEEK_API_KEY:
        configured_providers.append("DeepSeek")
    if COHERE_API_KEY:
        configured_providers.append("Cohere")
    if OPENROUTER_API_KEY:
        configured_providers.append("OpenRouter")
    if GITHUB_TOKEN:
        configured_providers.append("GitHubModels")
    if FIREWORKS_API_KEY:
        configured_providers.append("Fireworks")
    if HYPERBOLIC_API_KEY:
        configured_providers.append("Hyperbolic")
    if NOVITA_API_KEY:
        configured_providers.append("Novita")
    if SCALEWAY_API_KEY:
        configured_providers.append("Scaleway")
    if KLUSTER_API_KEY:
        configured_providers.append("Kluster")
    if NEBIUS_API_KEY:
        configured_providers.append("Nebius")

    logger.info(f"Configured providers ({len(configured_providers)}/16): {', '.join(configured_providers)}")

    if len(configured_providers) == 0:
        logger.warning("No AI provider API keys configured! Health checks will fail.")

    # Verify Data API connection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DATA_API_URL}/health")
            if response.status_code == 200:
                logger.info("Data API connection verified")
            else:
                logger.warning(f"Data API health check returned {response.status_code}")
    except Exception as e:
        logger.error(f"Data API connection failed: {sanitize_error_message(e)}")
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
