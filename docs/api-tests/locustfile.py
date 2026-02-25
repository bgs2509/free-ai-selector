"""
Шаблон нагрузочного теста для Business API (Locust).

Запуск (пример):
    locust -f docs/api-tests/locustfile.py --host http://localhost:8000 \
        --users 1 --spawn-rate 1 --run-time 10m

Ключевые переменные окружения:
    LOCUST_SCENARIO=baseline|ramp_up|sustained|failover
    API_PREFIX=/api/v1
    HEALTH_PATH=/health
    MODEL_STATS_PATH=/api/v1/models/stats
    PROMPT_PATH=/api/v1/prompts/process
    ENABLE_MONITORING=true|false
    INCLUDE_OVERSIZE_PROMPT=false
    WRITE_RESULTS_JSONL=true|false
    RESULTS_JSONL_PATH=docs/api-tests/locust-results-custom.jsonl
"""

from __future__ import annotations

import json
import os
import random
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gevent.lock import Semaphore
from locust import HttpUser, events, task
from locust.env import Environment


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _safe_json(response: Any) -> dict[str, Any]:
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"raw_json": data}
    except Exception:
        return {}


def _extract_error_text(status_code: int, body: dict[str, Any], fallback_text: str) -> str:
    if body:
        if isinstance(body.get("detail"), str):
            return str(body["detail"])
        if isinstance(body.get("message"), str):
            return str(body["message"])
        if isinstance(body.get("error"), str):
            return str(body["error"])
    if fallback_text:
        return fallback_text[:300]
    return f"HTTP {status_code}"


@dataclass(frozen=True)
class PromptProfile:
    """Профиль генерации промптов."""

    name: str
    length: int
    weight: int


@dataclass(frozen=True)
class ScenarioConfig:
    """Конфигурация сценария нагрузки."""

    name: str
    wait_min_seconds: float
    wait_max_seconds: float
    health_ratio: float
    model_stats_ratio: float
    prompts: tuple[PromptProfile, ...]


SHORT_PROMPT_CHARS = _env_int("SHORT_PROMPT_CHARS", 60)
LONG_PROMPT_CHARS = _env_int("LONG_PROMPT_CHARS", 2000)
BOUNDARY_PROMPT_CHARS = _env_int("BOUNDARY_PROMPT_CHARS", 6900)
OVERSIZE_PROMPT_CHARS = _env_int("OVERSIZE_PROMPT_CHARS", 7200)

ENABLE_MONITORING = _env_bool("ENABLE_MONITORING", True)
INCLUDE_OVERSIZE_PROMPT = _env_bool("INCLUDE_OVERSIZE_PROMPT", False)
WRITE_RESULTS_JSONL = _env_bool("WRITE_RESULTS_JSONL", True)
AUDIT_ENABLED = _env_bool("AUDIT_ENABLED", True)

HOST = os.getenv("LOCUST_HOST", "http://localhost:8000").strip()
API_PREFIX = os.getenv("API_PREFIX", "/api/v1").strip()
PROMPT_PATH = os.getenv("PROMPT_PATH", f"{API_PREFIX}/prompts/process").strip()
MODEL_STATS_PATH = os.getenv("MODEL_STATS_PATH", f"{API_PREFIX}/models/stats").strip()
HEALTH_PATH = os.getenv("HEALTH_PATH", "/health").strip()
REQUEST_TIMEOUT_SECONDS = _env_float("REQUEST_TIMEOUT_SECONDS", 90.0)

SCENARIO = os.getenv("LOCUST_SCENARIO", "baseline").strip().lower()
MODEL_ID_OVERRIDE = os.getenv("MODEL_ID_OVERRIDE")
RUN_ID = os.getenv("RUN_ID", "").strip()
RUN_SOURCE = os.getenv("RUN_SOURCE", "locust").strip()
RUN_SCENARIO = os.getenv("RUN_SCENARIO", SCENARIO).strip() or SCENARIO
RUN_STARTED_AT = os.getenv("RUN_STARTED_AT", "").strip()

DEFAULT_RESULTS_PATH = (
    Path("docs")
    / "api-tests"
    / f"locust-results-{SCENARIO}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
)
RESULTS_JSONL_PATH = Path(
    os.getenv("RESULTS_JSONL_PATH", str(DEFAULT_RESULTS_PATH)).strip()
)
AUDIT_JSONL_PATH = Path(
    os.getenv("AUDIT_JSONL_PATH", "docs/api-tests/results/audit/audit.jsonl").strip()
)


def _prompts_with_optional_oversize(base: tuple[PromptProfile, ...]) -> tuple[PromptProfile, ...]:
    if not INCLUDE_OVERSIZE_PROMPT:
        return base
    return base + (PromptProfile(name="oversize", length=OVERSIZE_PROMPT_CHARS, weight=1),)


SCENARIOS: dict[str, ScenarioConfig] = {
    "baseline": ScenarioConfig(
        name="baseline",
        wait_min_seconds=1.0,
        wait_max_seconds=2.5,
        health_ratio=0.05,
        model_stats_ratio=0.05,
        prompts=_prompts_with_optional_oversize(
            (
                PromptProfile(name="short", length=SHORT_PROMPT_CHARS, weight=8),
                PromptProfile(name="long", length=LONG_PROMPT_CHARS, weight=2),
            )
        ),
    ),
    "ramp_up": ScenarioConfig(
        name="ramp_up",
        wait_min_seconds=0.2,
        wait_max_seconds=1.2,
        health_ratio=0.03,
        model_stats_ratio=0.02,
        prompts=_prompts_with_optional_oversize(
            (
                PromptProfile(name="short", length=SHORT_PROMPT_CHARS, weight=6),
                PromptProfile(name="long", length=LONG_PROMPT_CHARS, weight=3),
                PromptProfile(name="boundary", length=BOUNDARY_PROMPT_CHARS, weight=1),
            )
        ),
    ),
    "sustained": ScenarioConfig(
        name="sustained",
        wait_min_seconds=0.3,
        wait_max_seconds=1.0,
        health_ratio=0.03,
        model_stats_ratio=0.02,
        prompts=_prompts_with_optional_oversize(
            (
                PromptProfile(name="short", length=SHORT_PROMPT_CHARS, weight=5),
                PromptProfile(name="long", length=LONG_PROMPT_CHARS, weight=3),
                PromptProfile(name="boundary", length=BOUNDARY_PROMPT_CHARS, weight=2),
            )
        ),
    ),
    "failover": ScenarioConfig(
        name="failover",
        wait_min_seconds=0.4,
        wait_max_seconds=1.5,
        health_ratio=0.02,
        model_stats_ratio=0.03,
        prompts=_prompts_with_optional_oversize(
            (
                PromptProfile(name="short", length=SHORT_PROMPT_CHARS, weight=3),
                PromptProfile(name="long", length=LONG_PROMPT_CHARS, weight=4),
                PromptProfile(name="boundary", length=BOUNDARY_PROMPT_CHARS, weight=3),
            )
        ),
    ),
}


if SCENARIO not in SCENARIOS:
    available = ", ".join(sorted(SCENARIOS.keys()))
    raise RuntimeError(f"Unsupported LOCUST_SCENARIO='{SCENARIO}'. Available: {available}")


class JsonlWriter:
    """Потокобезопасная запись результатов в jsonl."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Semaphore()
        self._fh = self.path.open("a", encoding="utf-8")

    def write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            self._fh.close()


RESULT_WRITER: JsonlWriter | None = None
AUDIT_WRITER: JsonlWriter | None = None


def _write_result(payload: dict[str, Any]) -> None:
    if RESULT_WRITER is None:
        return
    RESULT_WRITER.write(payload)


def _write_audit(payload: dict[str, Any]) -> None:
    if AUDIT_WRITER is None:
        return
    AUDIT_WRITER.write(payload)


def _run_context_payload() -> dict[str, Any]:
    return {
        "run_id": RUN_ID or None,
        "run_source": RUN_SOURCE,
        "run_scenario": RUN_SCENARIO,
        "run_started_at": RUN_STARTED_AT or None,
    }


def _build_request_headers() -> dict[str, str]:
    request_id = uuid.uuid4().hex
    headers: dict[str, str] = {
        "Content-Type": "application/json",
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


def _generate_prompt(profile: PromptProfile) -> str:
    """Генерирует промпт фиксированной длины с повторяемым содержимым."""
    header = f"[locust][{SCENARIO}][{profile.name}] "
    base_text = "Describe resilient API load testing strategy with concrete steps. "
    prompt = header + base_text

    while len(prompt) < profile.length:
        prompt += base_text

    return prompt[: profile.length]


def _choose_prompt_profile(config: ScenarioConfig) -> PromptProfile:
    return random.choices(
        population=list(config.prompts),
        weights=[profile.weight for profile in config.prompts],
        k=1,
    )[0]


@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs: Any) -> None:
    global RESULT_WRITER, AUDIT_WRITER

    if not WRITE_RESULTS_JSONL:
        RESULT_WRITER = None
    else:
        RESULT_WRITER = JsonlWriter(RESULTS_JSONL_PATH)

    if AUDIT_ENABLED:
        AUDIT_WRITER = JsonlWriter(AUDIT_JSONL_PATH)

    parsed_options = getattr(environment, "parsed_options", None)

    _write_result(
        {
            "event": "test_start",
            "timestamp": datetime.now(UTC).isoformat(),
            "scenario": SCENARIO,
            "host": HOST,
            "prompt_path": PROMPT_PATH,
            "model_stats_path": MODEL_STATS_PATH,
            "health_path": HEALTH_PATH,
            "users": getattr(parsed_options, "users", None),
            "spawn_rate": getattr(parsed_options, "spawn_rate", None),
            "run_time": getattr(parsed_options, "run_time", None),
            "enable_monitoring": ENABLE_MONITORING,
            "include_oversize_prompt": INCLUDE_OVERSIZE_PROMPT,
            **_run_context_payload(),
        }
    )

    _write_audit(
        {
            "event": "locust_test_start",
            "timestamp": datetime.now(UTC).isoformat(),
            "host": HOST,
            "users": getattr(parsed_options, "users", None),
            "spawn_rate": getattr(parsed_options, "spawn_rate", None),
            "run_time": getattr(parsed_options, "run_time", None),
            "locust_scenario": SCENARIO,
            **_run_context_payload(),
        }
    )

    print(f"[locustfile] RESULTS_JSONL_PATH={RESULTS_JSONL_PATH}")
    if AUDIT_ENABLED:
        print(f"[locustfile] AUDIT_JSONL_PATH={AUDIT_JSONL_PATH}")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs: Any) -> None:
    global RESULT_WRITER, AUDIT_WRITER

    total = environment.stats.total
    _write_result(
        {
            "event": "test_stop",
            "timestamp": datetime.now(UTC).isoformat(),
            "requests": total.num_requests,
            "failures": total.num_failures,
            "median_response_time_ms": total.median_response_time,
            "avg_response_time_ms": total.avg_response_time,
            "p95_response_time_ms": total.get_response_time_percentile(0.95),
            "p99_response_time_ms": total.get_response_time_percentile(0.99),
            "current_rps": total.current_rps,
            "current_fail_per_sec": total.current_fail_per_sec,
            **_run_context_payload(),
        }
    )
    _write_audit(
        {
            "event": "locust_test_stop",
            "timestamp": datetime.now(UTC).isoformat(),
            "requests": total.num_requests,
            "failures": total.num_failures,
            "current_rps": total.current_rps,
            **_run_context_payload(),
        }
    )

    if RESULT_WRITER is not None:
        RESULT_WRITER.close()
        RESULT_WRITER = None
    if AUDIT_WRITER is not None:
        AUDIT_WRITER.close()
        AUDIT_WRITER = None


class FreeAISelectorUser(HttpUser):
    """
    Пользователь Locust для сценариев:
    - baseline
    - ramp_up
    - sustained
    - failover
    """

    host = HOST

    def on_start(self) -> None:
        self.scenario: ScenarioConfig = SCENARIOS[SCENARIO]

    def wait_time(self) -> float:
        return random.uniform(self.scenario.wait_min_seconds, self.scenario.wait_max_seconds)

    @task
    def run_step(self) -> None:
        # Иногда выполняем мониторинговые endpoints, основная нагрузка идёт на /prompts/process.
        if ENABLE_MONITORING:
            roll = random.random()
            if roll < self.scenario.health_ratio:
                self._request_health()
                return
            if roll < self.scenario.health_ratio + self.scenario.model_stats_ratio:
                self._request_model_stats()
                return

        self._request_prompt_process()

    def _request_health(self) -> None:
        request_headers = _build_request_headers()
        started = time.perf_counter()
        with self.client.get(
            HEALTH_PATH,
            name="GET /health",
            catch_response=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers=request_headers,
        ) as response:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            body = _safe_json(response)

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

            _write_result(
                {
                    "event": "request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "scenario": self.scenario.name,
                    "endpoint": "GET /health",
                    "http_status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "success": response.status_code == 200,
                    "request_id": request_headers["X-Request-ID"],
                    "error": _extract_error_text(
                        response.status_code, body, response.text
                    )
                    if response.status_code != 200
                    else None,
                    **_run_context_payload(),
                }
            )
            _write_audit(
                {
                    "event": "locust_http_request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "endpoint": "GET /health",
                    "http_status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "success": response.status_code == 200,
                    "request_id": request_headers["X-Request-ID"],
                    **_run_context_payload(),
                }
            )

    def _request_model_stats(self) -> None:
        request_headers = _build_request_headers()
        started = time.perf_counter()
        with self.client.get(
            MODEL_STATS_PATH,
            name="GET /api/v1/models/stats",
            catch_response=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers=request_headers,
        ) as response:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            body = _safe_json(response)

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

            _write_result(
                {
                    "event": "request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "scenario": self.scenario.name,
                    "endpoint": "GET /api/v1/models/stats",
                    "http_status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "success": response.status_code == 200,
                    "models_total": body.get("total_models"),
                    "request_id": request_headers["X-Request-ID"],
                    "error": _extract_error_text(
                        response.status_code, body, response.text
                    )
                    if response.status_code != 200
                    else None,
                    **_run_context_payload(),
                }
            )
            _write_audit(
                {
                    "event": "locust_http_request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "endpoint": "GET /api/v1/models/stats",
                    "http_status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "success": response.status_code == 200,
                    "request_id": request_headers["X-Request-ID"],
                    **_run_context_payload(),
                }
            )

    def _request_prompt_process(self) -> None:
        prompt_profile = _choose_prompt_profile(self.scenario)
        prompt = _generate_prompt(prompt_profile)
        payload: dict[str, Any] = {"prompt": prompt}
        request_headers = _build_request_headers()

        if MODEL_ID_OVERRIDE:
            try:
                payload["model_id"] = int(MODEL_ID_OVERRIDE)
            except ValueError:
                pass

        started = time.perf_counter()
        with self.client.post(
            PROMPT_PATH,
            json=payload,
            name="POST /api/v1/prompts/process",
            catch_response=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers=request_headers,
        ) as response:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            body = _safe_json(response)

            is_success = response.status_code == 200 and body.get("success") is True
            if is_success:
                response.success()
            else:
                error_text = _extract_error_text(response.status_code, body, response.text)
                response.failure(f"HTTP {response.status_code}: {error_text}")

            _write_result(
                {
                    "event": "request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "scenario": self.scenario.name,
                    "endpoint": "POST /api/v1/prompts/process",
                    "http_status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "success": is_success,
                    "prompt_profile": prompt_profile.name,
                    "prompt_chars": len(prompt),
                    "selected_model": body.get("selected_model"),
                    "provider": body.get("provider"),
                    "attempts": body.get("attempts"),
                    "fallback_used": body.get("fallback_used"),
                    "request_id": request_headers["X-Request-ID"],
                    "backend_request_id": response.headers.get("x-request-id"),
                    "error": None
                    if is_success
                    else _extract_error_text(response.status_code, body, response.text),
                    **_run_context_payload(),
                }
            )
            _write_audit(
                {
                    "event": "locust_http_request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "endpoint": "POST /api/v1/prompts/process",
                    "http_status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "success": is_success,
                    "prompt_profile": prompt_profile.name,
                    "prompt_chars": len(prompt),
                    "request_id": request_headers["X-Request-ID"],
                    "backend_request_id": response.headers.get("x-request-id"),
                    **_run_context_payload(),
                }
            )
