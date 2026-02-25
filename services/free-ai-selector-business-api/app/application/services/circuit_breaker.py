"""
Circuit Breaker Manager for AI Providers.

F024: In-memory circuit breaker для мгновенного исключения нерабочих провайдеров.
Паттерн: CLOSED -> OPEN (после N ошибок) -> HALF-OPEN (через timeout) -> CLOSED (при успехе).

Configuration:
    CB_FAILURE_THRESHOLD: Ошибок подряд для CLOSED -> OPEN (default: 5)
    CB_RECOVERY_TIMEOUT: Секунд до OPEN -> HALF-OPEN (default: 60)
"""

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from app.utils.logger import get_logger

logger = get_logger(__name__)

CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
CB_RECOVERY_TIMEOUT = int(os.getenv("CB_RECOVERY_TIMEOUT", "60"))


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderCircuit:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    success_count_in_half_open: int = 0


class CircuitBreakerManager:
    """In-memory circuit breaker для всех провайдеров.

    Использует class-level dict (паттерн ProviderRegistry).
    Thread-safe в asyncio (single-threaded event loop).
    """

    _circuits: ClassVar[dict[str, ProviderCircuit]] = {}

    @classmethod
    def is_available(cls, provider_name: str) -> bool:
        circuit = cls._circuits.get(provider_name)
        if circuit is None:
            return True  # Новый провайдер — CLOSED по умолчанию

        if circuit.state == CircuitState.CLOSED:
            return True

        if circuit.state == CircuitState.OPEN:
            elapsed = time.time() - circuit.last_failure_time
            if elapsed >= CB_RECOVERY_TIMEOUT:
                old_state = circuit.state
                circuit.state = CircuitState.HALF_OPEN
                circuit.success_count_in_half_open = 0
                logger.warning(
                    "circuit_state_changed",
                    provider=provider_name,
                    old_state=old_state.value,
                    new_state=circuit.state.value,
                    reason="recovery_timeout_elapsed",
                )
                return True  # Разрешить пробный запрос
            return False

        # HALF_OPEN — разрешить (пробный запрос)
        return True

    @classmethod
    def record_success(cls, provider_name: str) -> None:
        circuit = cls._circuits.get(provider_name)
        if circuit is None:
            return

        if circuit.state == CircuitState.HALF_OPEN:
            old_state = circuit.state
            circuit.state = CircuitState.CLOSED
            circuit.failure_count = 0
            logger.warning(
                "circuit_state_changed",
                provider=provider_name,
                old_state=old_state.value,
                new_state=circuit.state.value,
                reason="probe_success",
            )
        elif circuit.state == CircuitState.CLOSED:
            circuit.failure_count = 0  # Сброс счётчика при успехе

    @classmethod
    def record_failure(cls, provider_name: str) -> None:
        circuit = cls._circuits.setdefault(
            provider_name, ProviderCircuit()
        )

        if circuit.state == CircuitState.HALF_OPEN:
            old_state = circuit.state
            circuit.state = CircuitState.OPEN
            circuit.last_failure_time = time.time()
            logger.warning(
                "circuit_state_changed",
                provider=provider_name,
                old_state=old_state.value,
                new_state=circuit.state.value,
                reason="probe_failed",
            )
            return

        # CLOSED: считаем ошибки подряд
        circuit.failure_count += 1
        circuit.last_failure_time = time.time()

        if circuit.failure_count >= CB_FAILURE_THRESHOLD:
            old_state = circuit.state
            circuit.state = CircuitState.OPEN
            logger.warning(
                "circuit_state_changed",
                provider=provider_name,
                old_state=old_state.value,
                new_state=circuit.state.value,
                reason=f"failure_threshold_reached ({circuit.failure_count})",
            )

    @classmethod
    def get_all_statuses(cls) -> dict[str, str]:
        return {
            name: circuit.state.value
            for name, circuit in cls._circuits.items()
        }

    @classmethod
    def reset(cls) -> None:
        """Сброс всех circuit breakers. Для тестов."""
        cls._circuits.clear()
