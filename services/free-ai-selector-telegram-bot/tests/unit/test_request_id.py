"""Тесты для app/utils/request_id.py."""
from app.utils.request_id import (
    generate_id,
    get_request_id,
    setup_tracing_context,
    clear_tracing_context,
    create_tracing_headers,
    get_correlation_id,
)


class TestGenerateId:
    def test_returns_32_hex(self):
        id_ = generate_id()
        assert len(id_) == 32
        int(id_, 16)  # Не должно вызвать исключение

    def test_unique(self):
        ids = {generate_id() for _ in range(50)}
        assert len(ids) == 50


class TestTracingContext:
    def test_setup_and_get(self):
        setup_tracing_context(request_id="r1", correlation_id="c1", user_id="u1")
        assert get_request_id() == "r1"
        assert get_correlation_id() == "c1"
        clear_tracing_context()

    def test_auto_request_id(self):
        setup_tracing_context()
        assert get_request_id() is not None
        clear_tracing_context()

    def test_clear(self):
        setup_tracing_context(request_id="r1")
        clear_tracing_context()
        assert get_request_id() is None

    def test_headers(self):
        setup_tracing_context(request_id="r1", correlation_id="c1")
        headers = create_tracing_headers()
        assert headers["X-Request-ID"] == "r1"
        assert headers["X-Correlation-ID"] == "c1"
        clear_tracing_context()
