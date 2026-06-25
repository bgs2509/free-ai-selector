"""
Reliability rating formula v2 (ADR-0003, bmm).

Pure scoring functions — capability/health gating lives in the business-api
selector; this module only turns recent (decay-weighted) stats into a score.

Pipeline:
    quality = (w_success + α) / (w_success + w_fail_hard + α + β)   # Laplace, no-data → 0.5
    speed   = clamp(1 - (median_latency - FAST_FLOOR)/(SLOW_CEIL - FAST_FLOOR), 0, 1)
    base    = quality * (0.5 + 0.5 * speed)                         # multiplicative
    ucb     = C * sqrt(ln(total_requests + 1) / (recent_n + 1))     # bounded, decaying
    effective = base + ucb

`w_success` / `w_fail_hard` are decay-weighted sums; 429s are excluded from
`w_fail_hard` upstream so rate-limits never depress quality.
"""

import math
from typing import Tuple

from app.domain.services import rating_params


def laplace_quality(
    w_success: float,
    w_fail_hard: float,
    alpha: float | None = None,
    beta: float | None = None,
) -> float:
    """Laplace-smoothed quality. With no data (0,0) → α/(α+β) = 0.5 by default."""
    a = rating_params.LAPLACE_ALPHA if alpha is None else alpha
    b = rating_params.LAPLACE_BETA if beta is None else beta
    denom = w_success + w_fail_hard + a + b
    if denom <= 0:
        return a / (a + b)
    return (w_success + a) / denom


def speed_score(median_latency_seconds: float) -> float:
    """Normalise latency to 0..1 (fast=1, slow=0) over [FAST_FLOOR, SLOW_CEIL]."""
    floor = rating_params.FAST_FLOOR_SECONDS
    ceil = rating_params.SLOW_CEIL_SECONDS
    if ceil <= floor:
        return 0.0
    raw = 1.0 - (median_latency_seconds - floor) / (ceil - floor)
    return max(0.0, min(1.0, raw))


def base_score(quality: float, speed: float) -> float:
    """Multiplicative combine — speed only modulates, never rescues a broken model."""
    return quality * (0.5 + 0.5 * speed)


def ucb_bonus(total_requests: int, recent_n: int) -> float:
    """Bounded, decaying exploration bonus. Shrinks as recent_n grows.

    Capped at UCB_BONUS_CAP so a no-data model is explored (ranks mid-pack) but never
    dominates a proven-healthy model — that would re-introduce the explore-first bug.
    """
    ln_total = math.log(max(total_requests, 0) + 1)
    raw = rating_params.UCB_C * math.sqrt(ln_total / (recent_n + 1))
    return min(raw, rating_params.UCB_BONUS_CAP)


def effective_score(
    w_success: float,
    w_fail_hard: float,
    median_latency_seconds: float,
    recent_n: int,
    total_requests: int,
) -> Tuple[float, float, float]:
    """Return (effective_score, base_score, quality).

    effective = base + ucb. Caller decides decision_reason from recent_n.
    """
    quality = laplace_quality(w_success, w_fail_hard)
    # No recent data → neutral speed (don't reward unknown latency with a free 1.0).
    speed = (
        rating_params.NO_DATA_SPEED
        if recent_n <= 0
        else speed_score(median_latency_seconds)
    )
    base = base_score(quality, speed)
    effective = base + ucb_bonus(total_requests, recent_n)
    return effective, base, quality
