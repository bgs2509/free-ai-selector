"""Структурированное логирование по Log-Driven Design (AIDD Framework)."""
import logging
import os
import sys
from typing import Any

import structlog

from app.utils.sensitive_filter import sanitize_sensitive_data

# Константы
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # json или console


def setup_logging(service_name: str) -> None:
    """
    Настроить structlog для сервиса.

    Args:
        service_name: Название сервиса для логов.
    """
    json_logs = LOG_FORMAT == "json"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        sanitize_sensitive_data,  # Defensive-in-depth: автофильтрация секретов
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Перехват stdlib logging → structlog JSON
    # Все логи от сторонних библиотек (httpx, asyncio, uvicorn.error)
    # проходят через structlog processors и рендерятся в JSON.
    stdlib_handler = logging.StreamHandler(sys.stdout)
    stdlib_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                sanitize_sensitive_data,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer() if json_logs
                else structlog.dev.ConsoleRenderer(colors=True),
            ],
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(stdlib_handler)
    root_logger.setLevel(logging.getLevelName(LOG_LEVEL))

    # Подавить шумные логи сторонних библиотек
    for noisy in ("httpx", "httpcore", "asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Получить логгер.

    Args:
        name: Имя модуля (опционально).

    Returns:
        Bound logger structlog.
    """
    logger: Any = structlog.get_logger()
    if name:
        logger = logger.bind(module=name)
    return logger
