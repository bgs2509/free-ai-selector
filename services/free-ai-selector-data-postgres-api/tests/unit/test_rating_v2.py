"""
Unit tests for reliability rating formula v2 (bmm / ADR-0003).

Locks the core anti-bug properties:
- no-data quality == 0.5 (NOT 1.0) — the explore-first defect this replaces.
- multiplicative combine: speed cannot rescue a broken-but-fast provider.
- on the ADR worked-example stats, healthy > mediocre > broken.
"""

import math

import pytest

from app.domain.services import rating_v2


@pytest.mark.unit
class TestLaplaceQuality:
    def test_no_data_is_half_not_one(self):
        # The whole point of v2: an untested model is "unknown" (0.5), not "perfect".
        assert rating_v2.laplace_quality(0.0, 0.0) == 0.5

    def test_healthy_model_high(self):
        assert rating_v2.laplace_quality(2454, 4) == pytest.approx(0.998, abs=2e-3)

    def test_broken_model_low(self):
        # SambaNova-like: 17 ok / 2405 hard-fail
        assert rating_v2.laplace_quality(17, 2405) == pytest.approx(0.0074, abs=1e-3)

    def test_429_excluded_upstream_keeps_quality_high(self):
        # If 100 successes and only rate-limits (w_fail_hard=0), quality stays high.
        assert rating_v2.laplace_quality(100, 0) > 0.98


@pytest.mark.unit
class TestSpeedScore:
    def test_floor_saturates_to_one(self):
        assert rating_v2.speed_score(0.5) == 1.0
        assert rating_v2.speed_score(0.1) == 1.0

    def test_ceil_floors_to_zero(self):
        assert rating_v2.speed_score(20.0) == 0.0
        assert rating_v2.speed_score(30.0) == 0.0

    def test_midrange(self):
        assert rating_v2.speed_score(7.6) == pytest.approx(0.636, abs=1e-2)


@pytest.mark.unit
class TestMultiplicativeCombine:
    def test_speed_cannot_rescue_broken_model(self):
        # SambaNova: quality ~0.007 but blazing fast (speed 1.0) → base stays ~0.007.
        q = rating_v2.laplace_quality(17, 2405)
        base = rating_v2.base_score(q, 1.0)
        assert base < 0.02

    def test_healthy_model_base_high(self):
        q = rating_v2.laplace_quality(2454, 4)
        base = rating_v2.base_score(q, rating_v2.speed_score(7.6))
        assert base > 0.75


@pytest.mark.unit
class TestUcbBonus:
    def test_bonus_shrinks_as_recent_n_grows(self):
        sparse = rating_v2.ucb_bonus(10000, 1)
        dense = rating_v2.ucb_bonus(10000, 5000)
        assert sparse > dense
        assert dense >= 0.0

    def test_zero_total_no_nan(self):
        assert rating_v2.ucb_bonus(0, 0) == 0.0
        assert not math.isnan(rating_v2.ucb_bonus(0, 0))


@pytest.mark.unit
class TestEffectiveRanking:
    """ADR worked example: Ollama > OpenRouter > Fireworks > Groq > SambaNova."""

    def test_ranking_matches_adr(self):
        # (w_success, w_fail_hard, median_latency, recent_n)
        models = {
            "Ollama": (2454, 4, 7.6, 2458),
            "OpenRouter": (2438, 46, 12.1, 2484),
            "Fireworks": (745, 255, 9.9, 1000),  # recent SR ~74.6%
            "Groq": (637, 2802, 0.5, 3439),
            "SambaNova": (17, 2405, 0.39, 2422),  # broken but fast
        }
        total = sum(m[3] for m in models.values())

        scores = {}
        for name, (ws, wf, lat, n) in models.items():
            eff, _base, _q = rating_v2.effective_score(ws, wf, lat, n, total)
            scores[name] = eff

        ranked = sorted(scores, key=scores.get, reverse=True)
        assert ranked == ["Ollama", "OpenRouter", "Fireworks", "Groq", "SambaNova"]

    def test_no_data_model_not_pinned_to_top(self):
        # A no-data model scores ~0.5 + small UCB — must NOT outrank a healthy model.
        eff_nodata, _b, _q = rating_v2.effective_score(0, 0, 0.0, 0, 10000)
        eff_healthy, _b2, _q2 = rating_v2.effective_score(2454, 4, 7.6, 2458, 10000)
        assert eff_healthy > eff_nodata
        assert eff_nodata < 1.0  # the old bug returned exactly 1.0
