"""Хелперы для логирования решений (AIDD Framework Log-Driven Design)."""
import time
from typing import Any, Literal

import structlog

DecisionType = Literal["ACCEPT", "REJECT", "RETRY", "SKIP", "FALLBACK"]


def log_decision(
    logger: structlog.BoundLogger,
    decision: DecisionType,
    reason: str,
    evaluated_conditions: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """
    Залогировать бизнес-решение.

    Используется для логирования критических точек принятия решений,
    чтобы AI-агент мог понять ПОЧЕМУ было принято конкретное решение.

    Args:
        logger: Structlog логгер.
        decision: Тип решения (ACCEPT, REJECT, RETRY, SKIP, FALLBACK).
        reason: Причина решения (человекочитаемая строка).
        evaluated_conditions: Условия, которые были оценены при принятии решения.
        **kwargs: Дополнительные поля для лога.

    Example:
        >>> log_decision(
        ...     logger,
        ...     decision="ACCEPT",
        ...     reason="highest_reliability_score",
        ...     evaluated_conditions={
        ...         "models_count": 5,
        ...         "selected_model": "gemini-1.5-flash",
        ...         "reliability_score": 0.95,
        ...     },
        ... )
    """
    log_data: dict[str, Any] = {
        "decision": decision,
        "reason": reason,
    }
    if evaluated_conditions:
        log_data["evaluated_conditions"] = evaluated_conditions
    log_data.update(kwargs)

    if decision in ("REJECT", "RETRY", "FALLBACK"):
        logger.warning("decision_made", **log_data)
    else:
        logger.info("decision_made", **log_data)


def log_request_started(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    **kwargs: Any,
) -> float:
    """
    Залогировать начало HTTP-запроса.

    Args:
        logger: Structlog логгер.
        method: HTTP метод (GET, POST, etc.).
        path: Путь запроса.
        **kwargs: Дополнительные поля.

    Returns:
        Время начала запроса (для вычисления duration_ms).
    """
    logger.info("request_started", method=method, path=path, **kwargs)
    return time.perf_counter()


def log_request_completed(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    start_time: float,
    status_code: int,
    **kwargs: Any,
) -> None:
    """
    Залогировать завершение HTTP-запроса.

    Args:
        logger: Structlog логгер.
        method: HTTP метод.
        path: Путь запроса.
        start_time: Время начала (из log_request_started).
        status_code: HTTP статус-код ответа.
        **kwargs: Дополнительные поля.
    """
    duration_ms = (time.perf_counter() - start_time) * 1000
    log_data: dict[str, Any] = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    log_data.update(kwargs)

    if status_code >= 500:
        logger.error("request_completed", **log_data)
    elif status_code >= 400:
        logger.warning("request_completed", **log_data)
    else:
        logger.info("request_completed", **log_data)


def log_external_call(
    logger: structlog.BoundLogger,
    service: str,
    operation: str,
    duration_ms: float,
    success: bool,
    **kwargs: Any,
) -> None:
    """
    Залогировать вызов внешнего сервиса.

    Args:
        logger: Structlog логгер.
        service: Название внешнего сервиса (data_api, gemini, groq, etc.).
        operation: Операция (get_models, generate, health_check, etc.).
        duration_ms: Время выполнения в миллисекундах.
        success: Успешен ли вызов.
        **kwargs: Дополнительные поля.
    """
    log_data: dict[str, Any] = {
        "external_service": service,
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "success": success,
    }
    log_data.update(kwargs)

    if success:
        logger.info("external_call", **log_data)
    else:
        logger.warning("external_call", **log_data)
