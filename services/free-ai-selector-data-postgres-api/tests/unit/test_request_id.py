"""Тесты для app/utils/request_id.py — трассировка запросов."""
from app.utils.request_id import (
    generate_id,
    get_request_id,
    set_request_id,
    get_correlation_id,
    setup_tracing_context,
    clear_tracing_context,
    create_tracing_headers,
)


class TestGenerateId:
    def test_returns_32_char_hex(self):
        id_ = generate_id()
        assert len(id_) == 32
        assert all(c in "0123456789abcdef" for c in id_)

    def test_unique_ids(self):
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100


class TestTracingContext:
    def test_setup_and_get(self):
        setup_tracing_context(request_id="req-1", correlation_id="corr-1", user_id="user-1")
        assert get_request_id() == "req-1"
        assert get_correlation_id() == "corr-1"
        clear_tracing_context()

    def test_auto_generates_request_id(self):
        setup_tracing_context()
        rid = get_request_id()
        assert rid is not None
        assert len(rid) == 32
        clear_tracing_context()

    def test_correlation_defaults_to_request(self):
        setup_tracing_context(request_id="test-req")
        assert get_correlation_id() == "test-req"
        clear_tracing_context()

    def test_clear_resets_all(self):
        setup_tracing_context(request_id="req-1")
        clear_tracing_context()
        assert get_request_id() is None


class TestCreateTracingHeaders:
    def test_includes_ids(self):
        setup_tracing_context(request_id="r1", correlation_id="c1")
        headers = create_tracing_headers()
        assert headers["X-Request-ID"] == "r1"
        assert headers["X-Correlation-ID"] == "c1"
        clear_tracing_context()

    def test_includes_run_context(self):
        setup_tracing_context(
            request_id="r1",
            run_id="run-1",
            run_source="test",
            run_scenario="qa",
        )
        headers = create_tracing_headers()
        assert headers["X-Run-Id"] == "run-1"
        assert headers["X-Run-Source"] == "test"
        clear_tracing_context()

    def test_empty_when_no_context(self):
        clear_tracing_context()
        headers = create_tracing_headers()
        assert "X-Request-ID" not in headers
