"""
Unit tests for ReliabilityService (F016: Single Source of Truth).

Тестирует расчёт reliability score в изоляции от других компонентов.
"""

import pytest

from app.domain.services.reliability_service import ReliabilityService


class TestReliabilityService:
    """Тесты для ReliabilityService.calculate()"""

    def test_calculate_normal_case(self):
        """
        Test: Нормальный случай с хорошими метриками.

        Given: success_rate=0.95, avg_response_time=2.0s
        When: ReliabilityService.calculate()
        Then: reliability = (0.95 × 0.6) + (0.8 × 0.4) = 0.89
        """
        # Given
        success_rate = 0.95
        avg_response_time = 2.0

        # When
        result = ReliabilityService.calculate(success_rate, avg_response_time)

        # Then
        # speed_score = max(0, 1.0 - (2.0 / 10.0)) = 0.8
        # reliability = (0.95 * 0.6) + (0.8 * 0.4) = 0.57 + 0.32 = 0.89
        expected = 0.89
        assert result == pytest.approx(expected, abs=0.01)

    def test_calculate_zero_success_rate(self):
        """
        Test: F011 edge case — нулевой success_rate.

        Given: success_rate=0.0, любое avg_response_time
        When: ReliabilityService.calculate()
        Then: reliability = 0.0 (игнорирует скорость)
        """
        # Given
        success_rate = 0.0
        avg_response_time = 1.0  # Даже если скорость хорошая

        # When
        result = ReliabilityService.calculate(success_rate, avg_response_time)

        # Then
        assert result == 0.0

    def test_calculate_slow_response(self):
        """
        Test: Медленный ответ (speed_score = 0).

        Given: success_rate=1.0, avg_response_time=15.0s (> baseline)
        When: ReliabilityService.calculate()
        Then: reliability = (1.0 × 0.6) + (0.0 × 0.4) = 0.6
        """
        # Given
        success_rate = 1.0
        avg_response_time = 15.0  # Больше чем SPEED_BASELINE_SECONDS (10.0)

        # When
        result = ReliabilityService.calculate(success_rate, avg_response_time)

        # Then
        # speed_score = max(0, 1.0 - (15.0 / 10.0)) = max(0, -0.5) = 0.0
        # reliability = (1.0 * 0.6) + (0.0 * 0.4) = 0.6
        expected = 0.6
        assert result == pytest.approx(expected, abs=0.01)

    def test_calculate_perfect_metrics(self):
        """
        Test: Идеальные метрики (100% успех, мгновенный ответ).

        Given: success_rate=1.0, avg_response_time=0.0s
        When: ReliabilityService.calculate()
        Then: reliability = (1.0 × 0.6) + (1.0 × 0.4) = 1.0
        """
        # Given
        success_rate = 1.0
        avg_response_time = 0.0

        # When
        result = ReliabilityService.calculate(success_rate, avg_response_time)

        # Then
        # speed_score = max(0, 1.0 - (0.0 / 10.0)) = 1.0
        # reliability = (1.0 * 0.6) + (1.0 * 0.4) = 1.0
        assert result == 1.0

    def test_calculate_weights_sum_to_one(self):
        """
        Test: Weights конфигурация — SUCCESS_WEIGHT + SPEED_WEIGHT = 1.0.

        Given: Weights как class constants
        When: Проверка суммы
        Then: 0.6 + 0.4 = 1.0
        """
        # Then
        total_weight = ReliabilityService.SUCCESS_WEIGHT + ReliabilityService.SPEED_WEIGHT
        assert total_weight == pytest.approx(1.0, abs=0.001)

    def test_calculate_with_edge_values(self):
        """
        Test: Граничные значения success_rate.

        Given: success_rate близкие к границам (0.01, 0.99)
        When: ReliabilityService.calculate()
        Then: Результат в допустимом диапазоне [0.0, 1.0]
        """
        # Test near-zero success rate (но не 0.0, чтобы не сработал F011)
        result_low = ReliabilityService.calculate(0.01, 5.0)
        assert 0.0 <= result_low <= 1.0

        # Test near-perfect success rate
        result_high = ReliabilityService.calculate(0.99, 1.0)
        assert 0.0 <= result_high <= 1.0
        assert result_high > 0.8  # Должно быть высокое значение
