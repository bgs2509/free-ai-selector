#!/usr/bin/env python3
"""
Бенчмарк AI-провайдеров Free AI Selector (модернизированная версия, Rung 2).

Что нового по сравнению с версией 2026-04-08:
  1. Health-gate     — тяжёлый бенчмарк гоняется ТОЛЬКО по провайдерам,
                       прошедшим health_check(); мёртвые/без ключа отсеиваются
                       до замеров (fail-fast).
  2. Таксономия ошибок — каждый сбой раскладывается по классам через переиспользование
                       app.application.services.error_classifier.classify_error():
                         transport  — 400/404/413/422  (НАШ баг конфига, чинится)
                         quota      — 429/402          (лимиты/кредиты, внешнее)
                         auth       — 401/403          (ключ/WAF/forbidden, внешнее)
                         transient  — 5xx/timeout/conn (ретраебельное, инфра)
                         capability — HTTP 200, но ответ непригоден
                                      (пустой / невалидный JSON / не на русском)
  3. Registry-driven — цели берутся из PROVIDER_CLASSES (без хардкод model_id);
                       новые модели (CloudflareGemma3/Qwen3, Ollama) подхватываются сами.
  4. Warmup          — перед замером скорости делается ОДИН непрогоняемый в статистику
                       прогревочный запрос. Критично для Ollama: холодный старт ~3.3с
                       (загрузка модели в память) против тёплого ~0.33с (10x).

Ollama (локальный провайдер, gemma4:e2b) живёт на gpu-1, а не на ноутбуке.
Чтобы покрыть его бенчмарком:
  - запускать скрипт на gpu-1, ЛИБО
  - выставить OLLAMA_BASE_URL на адрес Ollama-сервера gpu-1.
Если Ollama недоступен — health-gate его аккуратно пропустит (с подсказкой),
а не завалит весь прогон.

Запуск (внутри контейнера business-api):
  docker compose exec free-ai-selector-business-api python3 /app/provider_benchmark.py
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

# Путь к приложению: /app в контейнере, либо текущий каталог при локальном запуске.
sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ollama игнорирует Authorization, но конструктор провайдера требует непустой ключ.
os.environ.setdefault("OLLAMA_API_KEY", "ollama")

from app.application.services.error_classifier import classify_error  # noqa: E402
from app.domain.exceptions import (  # noqa: E402
    AuthenticationError,
    RateLimitError,
    ServerError,
)
from app.domain.exceptions import TimeoutError as ProviderTimeout  # noqa: E402
from app.domain.exceptions import ValidationError  # noqa: E402
from app.infrastructure.ai_providers.registry import PROVIDER_CLASSES  # noqa: E402


# =============================================================================
# Промпты (лёгкий набор — экономим квоты; покрываем plain / json / russian)
# =============================================================================


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str
    use_json: bool
    expect_russian: bool
    max_tokens: int


PROMPTS: list[Prompt] = [
    Prompt(
        "plain_short",
        "What is 2+2? Answer in one short sentence.",
        use_json=False,
        expect_russian=False,
        max_tokens=64,
    ),
    Prompt(
        "json_short",
        "List 3 programming languages with their release year.",
        use_json=True,
        expect_russian=False,
        max_tokens=128,
    ),
    Prompt(
        "russian_short",
        "Что такое Python? Ответь двумя предложениями на русском.",
        use_json=False,
        expect_russian=True,
        max_tokens=256,
    ),
]

WARMUP_PROMPT = "Say hello in one word."


# =============================================================================
# Результаты
# =============================================================================


@dataclass
class GateResult:
    provider: str
    admitted: bool
    reason: str  # "ok" | "no_key" | "init_failed" | "unhealthy"


@dataclass
class TestResult:
    provider: str
    prompt_id: str
    use_json: bool
    status: str  # success | failure | skipped
    failure_class: str  # "" | transport | quota | auth | transient | capability
    detail: str
    time_s: float
    chars: int
    json_valid: Optional[bool]
    cyrillic_ratio: Optional[float]
    preview: str


# =============================================================================
# Классификация ошибок (переиспользуем classify_error, маппим в бакеты)
# =============================================================================


def _http_status(exc: Exception) -> Optional[int]:
    """Достаёт HTTP-код из исключения, если есть."""
    resp = getattr(exc, "response", None)
    if resp is not None and hasattr(resp, "status_code"):
        return int(resp.status_code)
    orig = getattr(exc, "original_exception", None)
    if orig is not None:
        return _http_status(orig)
    return None


def failure_bucket(exc: Exception) -> tuple[str, str]:
    """
    Возвращает (failure_class, detail).

    Переиспользует classify_error() как SSoT «исключение -> тип»,
    добавляя только то, что classify_error не покрывает (413), и
    разнося типы по бакетам, понятным человеку.
    """
    status = _http_status(exc)

    # 413 не покрыт classify_error -> это транспорт (payload слишком большой = наш конфиг).
    if status == 413:
        return "transport", "HTTP 413 PayloadTooLarge"

    err = classify_error(exc)
    name = type(err).__name__
    suffix = f" HTTP {status}" if status else ""

    if isinstance(err, ValidationError):  # 400 / 404 / 422
        return "transport", f"{name}{suffix}"
    if isinstance(err, RateLimitError):  # 429
        return "quota", f"{name}{suffix}"
    if isinstance(err, AuthenticationError):  # 401 / 402 / 403
        if status == 402:
            return "quota", "PaymentRequired HTTP 402"
        return "auth", f"{name}{suffix}"
    if isinstance(err, (ServerError, ProviderTimeout)):
        return "transient", f"{name}{suffix or ' (timeout/conn)'}"
    return "transient", f"{name}{suffix}"  # неизвестное -> считаем инфра


def capability_verdict(
    text: str, prompt: Prompt
) -> tuple[bool, str, Optional[bool], Optional[float]]:
    """
    Оценивает пригодность УСПЕШНОГО (HTTP 200) ответа.

    Returns: (is_capability_failure, detail, json_valid, cyrillic_ratio)
    """
    json_valid: Optional[bool] = None
    cyr_ratio: Optional[float] = None

    if not text or not text.strip():
        return True, "empty response (200 but no content)", json_valid, cyr_ratio

    if prompt.use_json:
        try:
            json.loads(text)
            json_valid = True
        except (json.JSONDecodeError, TypeError, ValueError):
            json_valid = False
            return True, "invalid JSON", json_valid, cyr_ratio

    if prompt.expect_russian:
        letters = [c for c in text if c.isalpha()]
        cyr = [c for c in letters if "а" <= c.lower() <= "я" or c.lower() == "ё"]
        cyr_ratio = round(len(cyr) / len(letters), 2) if letters else 0.0
        if cyr_ratio < 0.5:
            return (
                True,
                f"not russian (cyrillic_ratio={cyr_ratio})",
                json_valid,
                cyr_ratio,
            )

    return False, "", json_valid, cyr_ratio


# =============================================================================
# Health-gate
# =============================================================================


async def gate_provider(name: str, cls: type) -> tuple[GateResult, Optional[Any]]:
    """Проверяет ключ + health_check. Возвращает (GateResult, provider|None)."""
    api_key_env = getattr(cls, "API_KEY_ENV", "")
    if api_key_env and not os.getenv(api_key_env):
        return GateResult(name, False, "no_key"), None

    try:
        provider = cls()
    except Exception as e:
        return GateResult(name, False, f"init_failed: {str(e)[:60]}"), None

    try:
        healthy = await provider.health_check()
    except Exception as e:
        return GateResult(name, False, f"unhealthy: {str(e)[:60]}"), None

    if not healthy:
        return GateResult(name, False, "unhealthy"), None

    return GateResult(name, True, "ok"), provider


# =============================================================================
# Один замер
# =============================================================================


async def run_one(provider: Any, name: str, prompt: Prompt) -> TestResult:
    kwargs: dict[str, Any] = {"max_tokens": prompt.max_tokens, "temperature": 0.7}
    if prompt.use_json:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["system_prompt"] = "You must respond with valid JSON only."

    start = time.monotonic()
    try:
        text = await provider.generate(prompt.text, **kwargs)
        elapsed = round(time.monotonic() - start, 3)
    except Exception as e:
        elapsed = round(time.monotonic() - start, 3)
        fclass, detail = failure_bucket(e)
        return TestResult(
            provider=name,
            prompt_id=prompt.id,
            use_json=prompt.use_json,
            status="failure",
            failure_class=fclass,
            detail=detail,
            time_s=elapsed,
            chars=0,
            json_valid=None,
            cyrillic_ratio=None,
            preview="",
        )

    cap_fail, cap_detail, json_valid, cyr_ratio = capability_verdict(text, prompt)
    return TestResult(
        provider=name,
        prompt_id=prompt.id,
        use_json=prompt.use_json,
        status="failure" if cap_fail else "success",
        failure_class="capability" if cap_fail else "",
        detail=cap_detail,
        time_s=elapsed,
        chars=len(text),
        json_valid=json_valid,
        cyrillic_ratio=cyr_ratio,
        preview=text[:120].replace("\n", " "),
    )


# =============================================================================
# Прогон
# =============================================================================


async def run_benchmark() -> None:
    providers = list(PROVIDER_CLASSES.items())

    print("=" * 80)
    print("PROVIDER BENCHMARK (modernized) — Free AI Selector")
    print(f"Провайдеров в реестре: {len(providers)}")
    print(f"Промптов: {len(PROMPTS)} ({', '.join(p.id for p in PROMPTS)})")
    print("=" * 80)

    # --- Health-gate ---
    print("\n--- Health-gate ---")
    gates: list[GateResult] = []
    live: list[tuple[str, Any]] = []
    for name, cls in providers:
        gate, provider = await gate_provider(name, cls)
        gates.append(gate)
        mark = "ADMIT" if gate.admitted else "SKIP "
        print(f"  [{mark}] {name:22s} {gate.reason}")
        if gate.admitted and provider is not None:
            live.append((name, provider))

    if any(g.provider.startswith("Ollama") and not g.admitted for g in gates):
        print(
            "  hint: Ollama недоступен — запусти на gpu-1 или выставь "
            "OLLAMA_BASE_URL на Ollama-сервер gpu-1."
        )

    print(f"\nДопущено к замерам: {len(live)}/{len(providers)}")
    if not live:
        print("Нет живых провайдеров — нечего мерять.")
        return

    # --- Замеры ---
    results: list[TestResult] = []
    total = len(live) * len(PROMPTS)
    n = 0
    print(f"\n--- Замеры ({total}) ---\n")

    for name, provider in live:
        # Warmup (не идёт в статистику) — снимает cold-start перекос (Ollama 10x).
        # Все запросы к провайдеру идут подряд, поэтому Ollama keep-alive (~5 мин)
        # держит модель загруженной на всё время его блока — отдельный keep_alive не нужен.
        try:
            await provider.generate(WARMUP_PROMPT, max_tokens=8)
            warm = "warmed"
        except Exception as e:
            warm = f"warmup-failed ({str(e)[:40]})"
        print(f"  {name:22s} | {warm}")

        for prompt in PROMPTS:
            n += 1
            res = await run_one(provider, name, prompt)
            results.append(res)
            if res.status == "success":
                extra = f" json={res.json_valid}" if res.use_json else ""
                if res.cyrillic_ratio is not None:
                    extra += f" cyr={res.cyrillic_ratio}"
                print(
                    f"    [{n:3d}/{total}] {prompt.id:14s} OK  "
                    f"{res.time_s:6.2f}s {res.chars:5d}ch{extra}"
                )
            else:
                print(
                    f"    [{n:3d}/{total}] {prompt.id:14s} FAIL "
                    f"[{res.failure_class}] {res.detail[:50]}"
                )
            await asyncio.sleep(2)  # лёгкая пауза между запросами

    _report(gates, results)


def _report(gates: list[GateResult], results: list[TestResult]) -> None:
    # Рядом со скриптом: в контейнере это /app, локально — каталог сервиса.
    out_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json"
    )
    try:
        with open(out_path, "w") as f:
            json.dump(
                {
                    "gates": [asdict(g) for g in gates],
                    "results": [asdict(r) for r in results],
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\nСырые результаты: {out_path}")
    except OSError as e:
        print(f"\nНе удалось записать {out_path}: {e}")

    # Сводка по провайдерам
    print("\n" + "=" * 96)
    print("СВОДКА ПО ПРОВАЙДЕРАМ")
    print("=" * 96)
    print(
        f"{'Provider':22s} | {'ok':>3s} | {'fail':>4s} | {'avg_s':>6s} | failure_classes"
    )
    print("-" * 96)
    names = [g.provider for g in gates if g.admitted]
    for name in names:
        rs = [r for r in results if r.provider == name]
        ok = [r for r in rs if r.status == "success"]
        fail = [r for r in rs if r.status == "failure"]
        avg = sum(r.time_s for r in ok) / len(ok) if ok else 0.0
        classes: dict[str, int] = {}
        for r in fail:
            classes[r.failure_class] = classes.get(r.failure_class, 0) + 1
        cls_str = ", ".join(f"{k}:{v}" for k, v in sorted(classes.items())) or "-"
        print(f"{name:22s} | {len(ok):3d} | {len(fail):4d} | {avg:6.2f} | {cls_str}")

    # Сводка по классам ошибок (actionable: transport = наши баги)
    print("\n" + "=" * 60)
    print("ОШИБКИ ПО КЛАССАМ (transport = чинить нам)")
    print("=" * 60)
    buckets: dict[str, list[str]] = {}
    for r in results:
        if r.status == "failure":
            buckets.setdefault(r.failure_class, []).append(
                f"{r.provider}/{r.prompt_id}: {r.detail}"
            )
    for cls in ["transport", "capability", "quota", "auth", "transient"]:
        items = buckets.get(cls, [])
        print(f"\n[{cls}] ({len(items)})")
        for it in items:
            print(f"  - {it}")

    print("\nБенчмарк завершён.")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
