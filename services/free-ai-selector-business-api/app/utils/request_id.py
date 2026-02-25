"""ContextVars для трассировки запросов (AIDD Framework)."""
import uuid
from contextvars import ContextVar

import structlog

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
_run_id_ctx: ContextVar[str | None] = ContextVar("run_id", default=None)
_run_source_ctx: ContextVar[str | None] = ContextVar("run_source", default=None)
_run_scenario_ctx: ContextVar[str | None] = ContextVar("run_scenario", default=None)
_run_started_at_ctx: ContextVar[str | None] = ContextVar("run_started_at", default=None)

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"
RUN_ID_HEADER = "X-Run-Id"
RUN_SOURCE_HEADER = "X-Run-Source"
RUN_SCENARIO_HEADER = "X-Run-Scenario"
RUN_STARTED_AT_HEADER = "X-Run-Started-At"


def generate_id() -> str:
    """Сгенерировать уникальный ID."""
    return uuid.uuid4().hex


def get_request_id() -> str | None:
    """Получить request_id из контекста."""
    return _request_id_ctx.get()


def set_request_id(value: str | None) -> None:
    """Установить request_id в контексте."""
    _request_id_ctx.set(value)


def get_correlation_id() -> str | None:
    """Получить correlation_id из контекста."""
    return _correlation_id_ctx.get()


def set_correlation_id(value: str | None) -> None:
    """Установить correlation_id в контексте."""
    _correlation_id_ctx.set(value)


def get_user_id() -> str | None:
    """Получить user_id из контекста."""
    return _user_id_ctx.get()


def set_user_id(value: str | None) -> None:
    """Установить user_id в контексте."""
    _user_id_ctx.set(value)


def get_run_id() -> str | None:
    """Получить run_id из контекста."""
    return _run_id_ctx.get()


def set_run_id(value: str | None) -> None:
    """Установить run_id в контексте."""
    _run_id_ctx.set(value)


def get_run_source() -> str | None:
    """Получить run_source из контекста."""
    return _run_source_ctx.get()


def set_run_source(value: str | None) -> None:
    """Установить run_source в контексте."""
    _run_source_ctx.set(value)


def get_run_scenario() -> str | None:
    """Получить run_scenario из контекста."""
    return _run_scenario_ctx.get()


def set_run_scenario(value: str | None) -> None:
    """Установить run_scenario в контексте."""
    _run_scenario_ctx.set(value)


def get_run_started_at() -> str | None:
    """Получить run_started_at из контекста."""
    return _run_started_at_ctx.get()


def set_run_started_at(value: str | None) -> None:
    """Установить run_started_at в контексте."""
    _run_started_at_ctx.set(value)


def setup_tracing_context(
    request_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
    run_source: str | None = None,
    run_scenario: str | None = None,
    run_started_at: str | None = None,
) -> None:
    """
    Установить контекст трассировки.

    Args:
        request_id: ID текущего запроса.
        correlation_id: ID корреляции (для отслеживания цепочки).
        user_id: ID пользователя.
        run_id: ID нагрузочного/тестового прогона.
        run_source: Источник запуска (скрипт/команда).
        run_scenario: Сценарий прогона.
        run_started_at: Время старта прогона (UTC ISO-8601).
    """
    if request_id is None:
        request_id = generate_id()

    set_request_id(request_id)
    set_correlation_id(correlation_id or request_id)
    set_user_id(user_id)
    set_run_id(run_id)
    set_run_source(run_source)
    set_run_scenario(run_scenario)
    set_run_started_at(run_started_at)

    # Биндим к structlog
    bind_payload: dict[str, str] = {
        "request_id": request_id,
        "correlation_id": correlation_id or request_id,
    }
    if run_id:
        bind_payload["run_id"] = run_id
    if run_source:
        bind_payload["run_source"] = run_source
    if run_scenario:
        bind_payload["run_scenario"] = run_scenario
    if run_started_at:
        bind_payload["run_started_at"] = run_started_at

    structlog.contextvars.bind_contextvars(**bind_payload)
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)


def clear_tracing_context() -> None:
    """Очистить контекст трассировки."""
    set_request_id(None)
    set_correlation_id(None)
    set_user_id(None)
    set_run_id(None)
    set_run_source(None)
    set_run_scenario(None)
    set_run_started_at(None)
    structlog.contextvars.unbind_contextvars(
        "request_id",
        "correlation_id",
        "user_id",
        "run_id",
        "run_source",
        "run_scenario",
        "run_started_at",
    )


def create_tracing_headers() -> dict[str, str]:
    """
    Создать заголовки для исходящего запроса.

    Returns:
        Словарь с заголовками X-Request-ID и X-Correlation-ID.
    """
    headers: dict[str, str] = {}
    correlation_id = get_correlation_id()
    if correlation_id:
        headers[CORRELATION_ID_HEADER] = correlation_id
    request_id = get_request_id()
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id
    run_id = get_run_id()
    if run_id:
        headers[RUN_ID_HEADER] = run_id
    run_source = get_run_source()
    if run_source:
        headers[RUN_SOURCE_HEADER] = run_source
    run_scenario = get_run_scenario()
    if run_scenario:
        headers[RUN_SCENARIO_HEADER] = run_scenario
    run_started_at = get_run_started_at()
    if run_started_at:
        headers[RUN_STARTED_AT_HEADER] = run_started_at
    return headers
