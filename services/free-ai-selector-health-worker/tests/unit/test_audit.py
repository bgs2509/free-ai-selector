"""Тесты для app/utils/audit.py — audit JSONL логирование."""
import json
from unittest.mock import patch

from app.utils.audit import (
    _hash_text,
    _sanitize_payload_value,
    audit_event,
)


class TestHashText:
    def test_returns_dict_with_chars_and_sha256(self):
        result = _hash_text("hello")
        assert result["chars"] == 5
        assert len(result["sha256"]) == 64

    def test_different_inputs_different_hashes(self):
        h1 = _hash_text("abc")
        h2 = _hash_text("def")
        assert h1["sha256"] != h2["sha256"]


class TestSanitizePayloadValue:
    def test_masks_api_key(self):
        assert _sanitize_payload_value("api_key", "secret123") == "***"

    def test_masks_token(self):
        assert _sanitize_payload_value("auth_token", "my-token") == "***"

    def test_masks_password(self):
        assert _sanitize_payload_value("db_password", "pass") == "***"

    def test_hashes_prompt(self):
        result = _sanitize_payload_value("prompt", "Hello world")
        assert isinstance(result, dict)
        assert "sha256" in result
        assert "chars" in result

    def test_hashes_response(self):
        result = _sanitize_payload_value("response", "AI response")
        assert isinstance(result, dict)
        assert "sha256" in result

    def test_none_passthrough(self):
        assert _sanitize_payload_value("key", None) is None

    def test_nested_dict(self):
        result = _sanitize_payload_value("data", {"api_key": "secret", "name": "test"})
        assert result["api_key"] == "***"

    def test_list_values(self):
        result = _sanitize_payload_value("items", ["val1", "val2"])
        assert isinstance(result, list)
        assert len(result) == 2


class TestAuditEvent:
    def test_disabled_does_nothing(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        with (
            patch("app.utils.audit.AUDIT_ENABLED", False),
            patch("app.utils.audit.AUDIT_JSONL_PATH", audit_file),
        ):
            audit_event("test_event", {"key": "value"})
        assert not audit_file.exists()

    def test_enabled_writes_jsonl(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        with (
            patch("app.utils.audit.AUDIT_ENABLED", True),
            patch("app.utils.audit.AUDIT_JSONL_PATH", audit_file),
        ):
            audit_event("test_event", {"model": "test-model"})

        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "test_event"
        assert "timestamp" in data
        assert "service" in data

    def test_sanitizes_payload(self, tmp_path):
        audit_file = tmp_path / "audit.jsonl"
        with (
            patch("app.utils.audit.AUDIT_ENABLED", True),
            patch("app.utils.audit.AUDIT_JSONL_PATH", audit_file),
        ):
            audit_event("test", {"api_key": "real-secret", "prompt": "hello"})

        data = json.loads(audit_file.read_text().strip())
        assert data["api_key"] == "***"
        assert isinstance(data["prompt"], dict)
        assert "sha256" in data["prompt"]
