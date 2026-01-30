"""
Domain services for AI Manager Platform - Data API Service.

Domain services содержат бизнес-логику, которая:
- Не принадлежит ни одному Entity/Value Object
- Требует координации между несколькими объектами
- Является stateless (без внутреннего состояния)

F016: ReliabilityService — расчёт reliability score (Single Source of Truth).
"""

from app.domain.services.reliability_service import ReliabilityService

__all__ = ["ReliabilityService"]
