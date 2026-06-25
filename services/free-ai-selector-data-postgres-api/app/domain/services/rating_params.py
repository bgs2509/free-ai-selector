"""
Rating formula v2 tunables (ADR-0003, bmm).

Single source of truth for the env-overridable parameters of the
capability-gated / Laplace-smoothed / multiplicative reliability score.
Defaults ratified at the bmm Brainstorming gate (2026-06-25).
"""

import os


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Laplace smoothing prior — symmetric (1,1) → no-data quality == 0.5 (not 1.0).
LAPLACE_ALPHA: float = _get_float("RATING_LAPLACE_ALPHA", 1.0)
LAPLACE_BETA: float = _get_float("RATING_LAPLACE_BETA", 1.0)

# Time-decay half-life in hours. 34h ≈ the legacy decay_per_hour=0.98 (0.98^34≈0.5),
# so v2 inherits today's decay behaviour unless deliberately changed.
HALF_LIFE_HOURS: float = _get_float("RATING_HALF_LIFE_HOURS", 34.0)

# Speed normalisation window (seconds): <=FAST_FLOOR → 1.0, >=SLOW_CEIL → 0.0.
FAST_FLOOR_SECONDS: float = _get_float("RATING_FAST_FLOOR_SECONDS", 0.5)
SLOW_CEIL_SECONDS: float = _get_float("RATING_SLOW_CEIL_SECONDS", 20.0)

# UCB exploration constant — bounded, decaying benefit-of-doubt for sparse models.
UCB_C: float = _get_float("RATING_UCB_C", 0.2)

# Hard cap on the UCB bonus so a no-data model is explored (ranks mid-pack) but
# never DOMINATES a proven-healthy model (would re-introduce the explore-first bug).
UCB_BONUS_CAP: float = _get_float("RATING_UCB_BONUS_CAP", 0.15)

# Neutral speed for a model with no recent data (avoids giving it a free 1.0 speed
# credit just because its median latency is 0/unknown).
NO_DATA_SPEED: float = _get_float("RATING_NO_DATA_SPEED", 0.5)


def decay_per_hour() -> float:
    """Per-hour decay derived from the half-life: 0.5 ** (1/HALF_LIFE_HOURS)."""
    return 0.5 ** (1.0 / HALF_LIFE_HOURS)
