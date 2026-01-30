"""
Reliability Score Domain Service (F016: Single Source of Truth).

Единственное место для расчёта reliability_score AI моделей.
"""


class ReliabilityService:
    """
    Domain service для расчёта reliability score AI моделей.

    Формула: reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

    Attributes:
        SUCCESS_WEIGHT: Вес успешности в формуле (60%)
        SPEED_WEIGHT: Вес скорости в формуле (40%)
        SPEED_BASELINE_SECONDS: Базовая линия для расчёта speed_score (10 секунд)
    """

    SUCCESS_WEIGHT = 0.6
    SPEED_WEIGHT = 0.4
    SPEED_BASELINE_SECONDS = 10.0

    @staticmethod
    def calculate(success_rate: float, avg_response_time: float) -> float:
        """
        Рассчитывает reliability score для AI модели.

        Args:
            success_rate: Процент успешных запросов (0.0-1.0)
            avg_response_time: Среднее время ответа в секундах

        Returns:
            Reliability score (0.0-1.0)

        Examples:
            >>> ReliabilityService.calculate(0.95, 2.0)
            0.89  # (0.95 * 0.6) + (0.8 * 0.4)

            >>> ReliabilityService.calculate(0.0, 1.0)
            0.0  # F011: Zero success rate → zero reliability

        Note:
            F011 Edge Case: Если success_rate = 0.0, возвращает 0.0
            независимо от скорости ответа.
        """
        # F011: Zero success rate → zero reliability
        if success_rate == 0.0:
            return 0.0

        # Calculate speed score (0.0-1.0)
        # speed_score = max(0.0, 1.0 - (response_time / baseline))
        speed_score = max(
            0.0, 1.0 - (avg_response_time / ReliabilityService.SPEED_BASELINE_SECONDS)
        )

        # Calculate weighted reliability
        reliability = (
            success_rate * ReliabilityService.SUCCESS_WEIGHT
            + speed_score * ReliabilityService.SPEED_WEIGHT
        )

        return reliability
