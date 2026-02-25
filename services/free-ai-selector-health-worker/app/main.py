"""
AI Manager Platform - Health Worker Service

Background worker for synthetic monitoring of AI providers.
Runs health checks hourly and updates model statistics.
Level 2 (Development Ready) maturity.

F008 SSOT Architecture:
    Provider list is fetched from Data API (PostgreSQL as SSOT).
    Each model contains api_format field for dynamic dispatch.
    F018: API key env var names resolved via PROVIDER_ENV_VARS dict (SSOT).
    Universal health checker uses api_format to select check function.

Supports all providers configured in seed.py (currently 14).
"""

import asyncio
import os
import time
import uuid
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logger import setup_logging, get_logger
from app.utils.security import sanitize_error_message
from app.utils.audit import audit_event

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "free-ai-selector-health-worker"
LOG_LEVEL = os.getenv("WORKER_LOG_LEVEL", "INFO")
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "3600"))  # seconds
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8001")
SYNTHETIC_TEST_PROMPT = os.getenv("SYNTHETIC_TEST_PROMPT", "Generate a simple greeting message")
RUN_ID = os.getenv("RUN_ID", "").strip()
RUN_SOURCE = os.getenv("RUN_SOURCE", "").strip()
RUN_SCENARIO = os.getenv("RUN_SCENARIO", "").strip()
RUN_STARTED_AT = os.getenv("RUN_STARTED_AT", "").strip()

# Special env vars for Cloudflare (needs account_id)
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")

# F018: SSOT для API key env var names (отдельный микросервис, не может импортировать ProviderRegistry)
PROVIDER_ENV_VARS: dict[str, str] = {
    "Groq": "GROQ_API_KEY",
    "Cerebras": "CEREBRAS_API_KEY",
    "SambaNova": "SAMBANOVA_API_KEY",
    "HuggingFace": "HUGGINGFACE_API_KEY",
    "Cloudflare": "CLOUDFLARE_API_TOKEN",
    "DeepSeek": "DEEPSEEK_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
    "GitHubModels": "GITHUB_TOKEN",
    "Fireworks": "FIREWORKS_API_KEY",
    "Hyperbolic": "HYPERBOLIC_API_KEY",
    "Novita": "NOVITA_API_KEY",
    "Scaleway": "SCALEWAY_API_KEY",
    "Kluster": "KLUSTER_API_KEY",
    "Nebius": "NEBIUS_API_KEY",
}

# =============================================================================
# Logging Configuration (AIDD Framework: structlog)
# =============================================================================

setup_logging(SERVICE_NAME)
logger = get_logger(__name__)

# =============================================================================
# Universal Health Check Functions (F008 SSOT)
# =============================================================================
# Dispatch by api_format from database instead of hardcoded provider names


def format_exception_message(error: Exception) -> str:
    """
    Формирует безопасное и информативное сообщение об ошибке.

    Для сетевых таймаутов str(error) может быть пустой строкой,
    поэтому включаем имя класса исключения.
    """
    message = sanitize_error_message(f"{type(error).__name__}: {error}").strip()
    if message:
        return message
    return type(error).__name__


def _get_api_key(env_var: str) -> Optional[str]:
    """
    Get API key from environment variable (F008 SSOT).

    Args:
        env_var: Environment variable name

    Returns:
        API key value or None if not set
    """
    return os.getenv(env_var, "") or None


async def check_openai_format(
    endpoint: str, api_key: str, provider: str
) -> tuple[bool, float]:
    """
    Universal health check for OpenAI-compatible APIs (F008 SSOT).

    Used by: Groq, Cerebras, SambaNova, DeepSeek, OpenRouter, GitHubModels,
             Fireworks, Hyperbolic, Novita, Scaleway, Kluster, Nebius

    Args:
        endpoint: API endpoint URL
        api_key: API key for authentication
        provider: Provider name for logging

    Returns:
        Tuple of (is_healthy, response_time_seconds)
    """
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            # OpenRouter requires referer header
            if "openrouter" in endpoint.lower():
                headers["HTTP-Referer"] = "https://github.com/free-ai-selector"

            payload = {
                "model": "auto",  # Model is not important for health check
                "messages": [{"role": "user", "content": SYNTHETIC_TEST_PROMPT}],
                "max_tokens": 50,
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(
            "health_check_failed",
            provider=provider,
            api_format="openai",
            error=format_exception_message(e),
        )
        return False, time.time() - start_time


async def check_huggingface_format(
    endpoint: str, api_key: str, provider: str
) -> tuple[bool, float]:
    """
    Health check for HuggingFace Inference API format (F008 SSOT).

    Used by: HuggingFace

    Args:
        endpoint: API endpoint URL
        api_key: API key for authentication
        provider: Provider name for logging

    Returns:
        Tuple of (is_healthy, response_time_seconds)
    """
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "inputs": SYNTHETIC_TEST_PROMPT,
                "parameters": {"max_new_tokens": 50},
            }
            response = await client.post(endpoint, headers=headers, json=payload)
            response_time = time.time() - start_time
            # 200 OK or 503 (model loading) both indicate API is responding
            return response.status_code in [200, 503], response_time
    except Exception as e:
        logger.error(
            "health_check_failed",
            provider=provider,
            api_format="huggingface",
            error=format_exception_message(e),
        )
        return False, time.time() - start_time


async def check_cloudflare_format(
    endpoint: str, api_key: str, provider: str
) -> tuple[bool, float]:
    """
    Health check for Cloudflare Workers AI format (F008 SSOT).

    Used by: Cloudflare

    Note: Requires CLOUDFLARE_ACCOUNT_ID env var for endpoint URL.

    Args:
        endpoint: API endpoint URL with {account_id} placeholder
        api_key: API token for authentication
        provider: Provider name for logging

    Returns:
        Tuple of (is_healthy, response_time_seconds)
    """
    if not CLOUDFLARE_ACCOUNT_ID:
        logger.warning(
            "provider_config_missing",
            provider=provider,
            missing="CLOUDFLARE_ACCOUNT_ID",
        )
        return False, 0.0

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
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
            return response.status_code == 200, response_time
    except Exception as e:
        logger.error(
            "health_check_failed",
            provider=provider,
            api_format="cloudflare",
            error=format_exception_message(e),
        )
        return False, time.time() - start_time


# =============================================================================
# API Format Dispatch Dictionary (F008 SSOT)
# =============================================================================
# Maps api_format from database to check function

API_FORMAT_CHECKERS = {
    "openai": check_openai_format,
    "huggingface": check_huggingface_format,
    "cloudflare": check_cloudflare_format,
}


def _build_trace_headers() -> dict[str, str]:
    """
    Собирает headers для межсервисных запросов в Data API.

    Хедеры нужны для end-to-end трассировки:
    - X-Request-ID / X-Correlation-ID
    - X-Run-* (если задан run context).
    """
    request_id = uuid.uuid4().hex
    headers: dict[str, str] = {
        "X-Request-ID": request_id,
        "X-Correlation-ID": RUN_ID or request_id,
    }
    if RUN_ID:
        headers["X-Run-Id"] = RUN_ID
    if RUN_SOURCE:
        headers["X-Run-Source"] = RUN_SOURCE
    if RUN_SCENARIO:
        headers["X-Run-Scenario"] = RUN_SCENARIO
    if RUN_STARTED_AT:
        headers["X-Run-Started-At"] = RUN_STARTED_AT
    return headers


async def universal_health_check(
    endpoint: str,
    api_format: str,
    provider: str,
) -> tuple[bool, float]:
    """
    Universal health check dispatcher (F008 SSOT, F018).

    Resolves API key env var name via PROVIDER_ENV_VARS dict,
    then dispatches to appropriate format-specific checker based on api_format.

    Args:
        endpoint: API endpoint URL from database
        api_format: API format discriminator from database
        provider: Provider name for logging and env var lookup

    Returns:
        Tuple of (is_healthy, response_time_seconds)
    """
    # F018: Resolve env var name from provider name
    env_var = PROVIDER_ENV_VARS.get(provider, "")
    if not env_var:
        logger.warning(
            "provider_env_var_unknown",
            provider=provider,
        )
        return False, 0.0

    # Get API key from environment
    api_key = _get_api_key(env_var)
    if not api_key:
        logger.warning(
            "provider_api_key_missing",
            provider=provider,
            env_var=env_var,
        )
        return False, 0.0

    # Get format-specific checker
    checker = API_FORMAT_CHECKERS.get(api_format)
    if not checker:
        logger.warning(
            "unknown_api_format",
            provider=provider,
            api_format=api_format,
        )
        return False, 0.0

    # Run check
    return await checker(endpoint, api_key, provider)


# =============================================================================
# Main Health Check Job
# =============================================================================


async def run_health_checks():
    """
    Run synthetic health checks for all AI models (F008 SSOT).

    Fetches models from Data API (including api_format),
    checks each provider using universal health checker,
    and updates statistics based on results.

    F012: Rate-limited providers (available_at > now) are excluded
    from health checks via available_only=true parameter.
    """
    # Генерируем job_id для этого цикла проверок
    job_id = uuid.uuid4().hex[:12]
    logger.info("health_check_job_started", job_id=job_id)
    audit_event(
        "health_check_job_started",
        {
            "job_id": job_id,
            "run_id": RUN_ID or None,
            "run_source": RUN_SOURCE or None,
            "run_scenario": RUN_SCENARIO or None,
        },
    )

    try:
        # Fetch all active models from Data API (F008: includes api_format)
        # F012: available_only=true excludes rate-limited providers
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{DATA_API_URL}/api/v1/models?active_only=true&available_only=true",
                headers=_build_trace_headers(),
            )
            response.raise_for_status()
            models = response.json()

        logger.info("fetched_models_for_check", job_id=job_id, models_count=len(models))

        healthy_count = 0
        unhealthy_count = 0
        skipped_count = 0

        # Check each model using universal health checker
        for model in models:
            model_id = model["id"]
            model_name = model["name"]
            provider = model["provider"]
            endpoint = model["api_endpoint"]
            # F008 SSOT: api_format from database
            api_format = model.get("api_format", "openai")

            logger.info(
                "checking_model",
                job_id=job_id,
                model=model_name,
                provider=provider,
                api_format=api_format,
            )
            audit_event(
                "model_call_start",
                {
                    "source": "health_worker",
                    "job_id": job_id,
                    "model_id": model_id,
                    "model": model_name,
                    "provider": provider,
                    "api_format": api_format,
                    "prompt_chars": len(SYNTHETIC_TEST_PROMPT),
                },
            )

            # F008: Use universal health check with api_format dispatch
            # F018: env_var resolved inside via PROVIDER_ENV_VARS
            is_healthy, response_time = await universal_health_check(
                endpoint=endpoint,
                api_format=api_format,
                provider=provider,
            )

            # Skip if no API key configured (response_time == 0.0 indicates missing key)
            if response_time == 0.0 and not is_healthy:
                skipped_count += 1
                audit_event(
                    "model_call_error",
                    {
                        "source": "health_worker",
                        "job_id": job_id,
                        "model_id": model_id,
                        "model": model_name,
                        "provider": provider,
                        "duration_ms": 0.0,
                        "error_type": "ProviderNotConfigured",
                        "error": "Provider API key missing or provider env var unknown",
                    },
                )
                continue

            # Update model statistics in Data API
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    if is_healthy:
                        healthy_count += 1
                        logger.info(
                            "model_healthy",
                            job_id=job_id,
                            model=model_name,
                            provider=provider,
                            response_time_seconds=round(response_time, 2),
                        )
                        audit_event(
                            "model_call_success",
                            {
                                "source": "health_worker",
                                "job_id": job_id,
                                "model_id": model_id,
                                "model": model_name,
                                "provider": provider,
                                "duration_ms": round(response_time * 1000.0, 2),
                                "response_chars": None,
                            },
                        )
                        await client.post(
                            f"{DATA_API_URL}/api/v1/models/{model_id}/increment-success",
                            params={"response_time": response_time},
                            headers=_build_trace_headers(),
                        )
                    else:
                        unhealthy_count += 1
                        logger.warning(
                            "model_unhealthy",
                            job_id=job_id,
                            model=model_name,
                            provider=provider,
                        )
                        audit_event(
                            "model_call_error",
                            {
                                "source": "health_worker",
                                "job_id": job_id,
                                "model_id": model_id,
                                "model": model_name,
                                "provider": provider,
                                "duration_ms": round(response_time * 1000.0, 2),
                                "error_type": "UnhealthyResponse",
                                "error": "Provider health check returned non-healthy status",
                            },
                        )
                        await client.post(
                            f"{DATA_API_URL}/api/v1/models/{model_id}/increment-failure",
                            params={"response_time": response_time},
                            headers=_build_trace_headers(),
                        )
            except Exception as update_error:
                logger.error(
                    "stats_update_failed",
                    job_id=job_id,
                    model=model_name,
                    error=format_exception_message(update_error),
                )
                audit_event(
                    "health_stats_update_failed",
                    {
                        "job_id": job_id,
                        "model_id": model_id,
                        "model": model_name,
                        "provider": provider,
                        "error": format_exception_message(update_error),
                    },
                )

        logger.info(
            "health_check_job_completed",
            job_id=job_id,
            healthy=healthy_count,
            unhealthy=unhealthy_count,
            skipped=skipped_count,
            total=len(models),
        )
        audit_event(
            "health_check_job_completed",
            {
                "job_id": job_id,
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "skipped": skipped_count,
                "total": len(models),
            },
        )

    except Exception as e:
        logger.error("health_check_job_failed", job_id=job_id, error=format_exception_message(e))
        audit_event(
            "health_check_job_failed",
            {
                "job_id": job_id,
                "error": format_exception_message(e),
            },
        )


# =============================================================================
# Main Function
# =============================================================================


async def main():
    """
    Main worker entry point (F008 SSOT).

    Sets up scheduler and runs health checks at configured interval.
    Provider list is fetched from Data API dynamically.
    """
    logger.info(
        "service_starting",
        data_api_url=DATA_API_URL,
        health_check_interval_seconds=HEALTH_CHECK_INTERVAL,
    )

    # Verify Data API connection and fetch provider list (F008 SSOT)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check Data API health
            response = await client.get(f"{DATA_API_URL}/health", headers=_build_trace_headers())
            if response.status_code == 200:
                logger.info("data_api_connected", status="healthy")
            else:
                logger.warning(
                    "data_api_connected",
                    status="unhealthy",
                    status_code=response.status_code,
                )

            # F008 SSOT: Fetch providers from Data API to log configured ones
            models_response = await client.get(
                f"{DATA_API_URL}/api/v1/models?active_only=true",
                headers=_build_trace_headers(),
            )
            if models_response.status_code == 200:
                models = models_response.json()
                # F018: Check which providers have API keys configured via PROVIDER_ENV_VARS
                configured_providers = []
                for model in models:
                    provider = model.get("provider", "")
                    env_var = PROVIDER_ENV_VARS.get(provider, "")
                    if env_var and _get_api_key(env_var):
                        configured_providers.append(provider)

                logger.info(
                    "configured_providers",
                    count=len(configured_providers),
                    total=len(models),
                    providers=configured_providers,
                )

                if len(configured_providers) == 0:
                    logger.warning("no_providers_configured")

    except Exception as e:
        logger.error("data_api_connection_failed", error=format_exception_message(e))
        raise

    # Run initial health check
    logger.info("running_initial_health_check")
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
    logger.info("scheduler_started", next_check_in_seconds=HEALTH_CHECK_INTERVAL)

    # Keep worker running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler_shutting_down")
        scheduler.shutdown()
        logger.info("service_stopped")


if __name__ == "__main__":
    asyncio.run(main())
