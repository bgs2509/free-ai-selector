"""Структурированное логирование по Log-Driven Design (AIDD Framework)."""
import logging
import os
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
