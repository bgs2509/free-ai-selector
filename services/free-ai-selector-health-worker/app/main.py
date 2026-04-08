"""
AI Manager Platform - Health Worker Service

Background worker for synthetic monitoring of AI providers.
Delegates health checks to Business API (POST /providers/test),
which uses correct provider-specific classes and model names.
Runs checks hourly and logs results.

Business API already updates increment-success/failure in Data API,
so health worker acts as a thin scheduler — no direct provider calls needed.
"""

import asyncio
import os
import uuid

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
BUSINESS_API_URL = os.getenv("BUSINESS_API_URL", "http://free-ai-selector-business-api:8000")
RUN_ID = os.getenv("RUN_ID", "").strip()
RUN_SOURCE = os.getenv("RUN_SOURCE", "").strip()
RUN_SCENARIO = os.getenv("RUN_SCENARIO", "").strip()
RUN_STARTED_AT = os.getenv("RUN_STARTED_AT", "").strip()

# =============================================================================
# Logging Configuration (AIDD Framework: structlog)
# =============================================================================

setup_logging(SERVICE_NAME)
logger = get_logger(__name__)

# =============================================================================
# Utility Functions
# =============================================================================


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


def _build_trace_headers() -> dict[str, str]:
    """
    Собирает headers для межсервисных запросов.

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


# =============================================================================
# Main Health Check Job
# =============================================================================


async def run_health_checks():
    """
    Делегирует health check в Business API (POST /providers/test).

    Business API сам вызывает провайдеров с правильными model names
    и обновляет increment-success/failure в Data API.
    Health worker только логирует результаты.
    """
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
        # Вызываем business-api (сам обновляет increment-success/failure)
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{BUSINESS_API_URL}/api/v1/providers/test",
                headers=_build_trace_headers(),
            )
            response.raise_for_status()
            data = response.json()

        # Считаем результаты
        results = data.get("results", [])
        healthy = [r for r in results if r.get("status") == "success"]
        unhealthy = [r for r in results if r.get("status") != "success"]

        # Логируем каждый результат
        for r in healthy:
            logger.info(
                "model_healthy",
                job_id=job_id,
                model=r.get("model"),
                provider=r.get("provider"),
                response_time_seconds=r.get("response_time"),
            )
            audit_event(
                "model_call_success",
                {
                    "source": "health_worker",
                    "job_id": job_id,
                    "model": r.get("model"),
                    "provider": r.get("provider"),
                    "duration_ms": round(r.get("response_time", 0) * 1000.0, 2),
                },
            )

        for r in unhealthy:
            logger.warning(
                "model_unhealthy",
                job_id=job_id,
                model=r.get("model"),
                provider=r.get("provider"),
                error=r.get("error"),
            )
            audit_event(
                "model_call_error",
                {
                    "source": "health_worker",
                    "job_id": job_id,
                    "model": r.get("model"),
                    "provider": r.get("provider"),
                    "error": r.get("error"),
                },
            )

        # Итог
        logger.info(
            "health_check_job_completed",
            job_id=job_id,
            healthy=len(healthy),
            unhealthy=len(unhealthy),
            total=len(results),
        )
        audit_event(
            "health_check_job_completed",
            {
                "job_id": job_id,
                "healthy": len(healthy),
                "unhealthy": len(unhealthy),
                "total": len(results),
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
    Main worker entry point.

    Sets up scheduler and runs health checks at configured interval.
    Delegates actual provider testing to Business API.
    """
    logger.info(
        "service_starting",
        data_api_url=DATA_API_URL,
        business_api_url=BUSINESS_API_URL,
        health_check_interval_seconds=HEALTH_CHECK_INTERVAL,
    )

    # Проверяем доступность business-api
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

            # Check Business API health
            response = await client.get(
                f"{BUSINESS_API_URL}/health", headers=_build_trace_headers()
            )
            if response.status_code == 200:
                logger.info("business_api_connected", status="healthy")
            else:
                logger.warning(
                    "business_api_connected",
                    status="unhealthy",
                    status_code=response.status_code,
                )

    except Exception as e:
        logger.error("api_connection_failed", error=format_exception_message(e))
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
