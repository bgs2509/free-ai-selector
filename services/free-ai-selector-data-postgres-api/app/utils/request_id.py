"""ContextVars для трассировки запросов (AIDD Framework)."""
import uuid
from contextvars import ContextVar

import structlog

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"


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


def setup_tracing_context(
    request_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """
    Установить контекст трассировки.

    Args:
        request_id: ID текущего запроса.
        correlation_id: ID корреляции (для отслеживания цепочки).
        user_id: ID пользователя.
    """
    if request_id is None:
        request_id = generate_id()

    set_request_id(request_id)
    set_correlation_id(correlation_id or request_id)
    set_user_id(user_id)

    # Биндим к structlog
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        correlation_id=correlation_id or request_id,
    )
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=user_id)


def clear_tracing_context() -> None:
    """Очистить контекст трассировки."""
    set_request_id(None)
    set_correlation_id(None)
    set_user_id(None)
    structlog.contextvars.unbind_contextvars("request_id", "correlation_id", "user_id")


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
    return headers
