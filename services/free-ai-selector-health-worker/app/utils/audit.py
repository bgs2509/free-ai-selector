"""Утилиты для записи audit-событий в JSONL для health-worker."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.utils.security import sanitize_error_message


SERVICE_NAME = os.getenv("SERVICE_NAME", "free-ai-selector-health-worker")
AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AUDIT_JSONL_PATH = Path(os.getenv("AUDIT_JSONL_PATH", "/audit/audit.jsonl")).expanduser()
RUN_ID = os.getenv("RUN_ID", "").strip() or None
RUN_SOURCE = os.getenv("RUN_SOURCE", "").strip() or None
RUN_SCENARIO = os.getenv("RUN_SCENARIO", "").strip() or None
RUN_STARTED_AT = os.getenv("RUN_STARTED_AT", "").strip() or None

_SENSITIVE_KEYWORDS = (
    "api_key",
    "token",
    "authorization",
    "password",
    "secret",
)
_TEXT_FIELDS = (
    "prompt",
    "response",
    "content",
    "system_prompt",
)


def _hash_text(value: str) -> dict[str, Any]:
    """Возвращает безопасную сводку по тексту без хранения исходного значения."""
    return {
        "chars": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }


def _sanitize_payload_value(key: str, value: Any) -> Any:
    """Рекурсивно санитизирует payload перед записью в audit."""
    if value is None:
        return None

    if isinstance(value, dict):
        return {str(k): _sanitize_payload_value(str(k), v) for k, v in value.items()}

    if isinstance(value, list):
        return [_sanitize_payload_value(key, item) for item in value]

    if isinstance(value, str):
        lowered = key.lower()
        if any(keyword in lowered for keyword in _SENSITIVE_KEYWORDS):
            return "***"
        if any(keyword in lowered for keyword in _TEXT_FIELDS):
            return _hash_text(value)
        return sanitize_error_message(value)

    return value


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Санитизирует словарь payload."""
    return {key: _sanitize_payload_value(key, value) for key, value in payload.items()}


def audit_event(event: str, payload: dict[str, Any] | None = None) -> None:
    """Пишет audit-событие в JSONL."""
    if not AUDIT_ENABLED:
        return

    data: dict[str, Any] = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        "service": SERVICE_NAME,
        "run_id": RUN_ID,
        "run_source": RUN_SOURCE,
        "run_scenario": RUN_SCENARIO,
        "run_started_at": RUN_STARTED_AT,
    }

    if payload:
        data.update(_safe_payload(payload))

    try:
        AUDIT_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_JSONL_PATH.open("a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")
            fh.flush()
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        # Audit не должен ломать основной поток выполнения worker.
        return
