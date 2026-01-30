---
feature_id: "F016"
feature_name: "reliability-score-ssot"
title: "Reliability Score: Single Source of Truth"
created: "2026-01-30"
author: "AI (Architect)"
type: "feature_plan"
status: "PLAN_READY"
version: 1

related_features: [F010, F015]
services: [free-ai-selector-data-postgres-api]
---

# Implementation Plan: Reliability Score Single Source of Truth

**Feature ID**: F016
**Дата**: 2026-01-30
**Автор**: AI Agent (Архитектор)
**Статус**: PLAN_READY

---

## 1. Обзор

### 1.1 Цель

Вынести расчёт `reliability_score` в Domain Service для соблюдения SSoT (Single Source of Truth) и устранения дублирования формулы в 2 местах.

### 1.2 Scope

| Аспект | Детали |
|--------|---------|
| **Сервисы** | free-ai-selector-data-postgres-api |
| **Файлов к созданию** | 2 (service + __init__) |
| **Файлов к изменению** | 2 (domain/models.py, api/v1/models.py) |
| **Breaking changes** | ❌ Нет |
| **DB Migration** | ❌ Не требуется |

### 1.3 Текущее состояние

**Проблема**: Формула `reliability_score = (success_rate × 0.6) + (speed_score × 0.4)` дублируется:

1. `app/domain/models.py:70-80` — Domain model property
2. `app/api/v1/models.py:404-412` — Recent metrics calculation (F010)

**Последствия**:
- ⚠️ Нарушение DRY/SSoT
- ⚠️ Риск расхождения при изменениях
- ⚠️ Hardcoded weights (0.6, 0.4)

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Компоненты | Изменения |
|--------|-----------|-----------|
| free-ai-selector-data-postgres-api | domain/models.py | Делегация в сервис |
| free-ai-selector-data-postgres-api | api/v1/models.py | Использование сервиса |
| free-ai-selector-data-postgres-api | domain/services/ | Создание (NEW) |

### 2.2 Точки интеграции

#### 2.2.1 Domain Model (app/domain/models.py)

**Текущая реализация**:
```python
@property
def reliability_score(self) -> float:
    """
    Calculate reliability score (0.0 - 1.0).
    Formula: reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

    Note: If success_rate = 0, returns 0.0 (F011 fix).
    """
    if self.success_rate == 0.0:
        return 0.0
    return (self.success_rate * 0.6) + (self.speed_score * 0.4)  # ← Дублирование
```

**Использование**:
- `api/v1/models.py:373` — `reliability_score=model.reliability_score`
- `api/v1/models.py:426` — `effective_reliability_score=round(model.reliability_score, 4)`

**Зависимости**:
- `self.success_rate` (property)
- `self.speed_score` (property)
- `self.average_response_time` (property)

---

#### 2.2.2 Recent Metrics Calculation (app/api/v1/models.py)

**Текущая реализация**:
```python
def _calculate_recent_metrics(
    model: AIModel, recent_stats: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    """F010: Calculate recent metrics for a model."""
    stats = recent_stats.get(model.id, {})
    request_count = stats.get("request_count", 0)
    success_count = stats.get("success_count", 0)
    avg_response_time = stats.get("avg_response_time", 0.0)

    if request_count >= MIN_REQUESTS_FOR_RECENT:
        recent_success_rate = success_count / request_count
        # F011: Zero success rate = zero reliability
        if recent_success_rate == 0.0:
            recent_reliability = 0.0
            recent_speed_score = 0.0
        else:
            recent_speed_score = max(0.0, 1.0 - (avg_response_time / 10.0))
            recent_reliability = (recent_success_rate * 0.6) + (recent_speed_score * 0.4)  # ← Дублирование
        ...
```

**Использование**:
- F010 rolling window reliability для recent metrics
- Fallback на `model.reliability_score` если данных недостаточно

---

### 2.3 Существующие зависимости

| Компонент | Зависимости | Влияние F016 |
|-----------|-------------|--------------|
| AIModel | success_rate, speed_score, average_response_time | Без изменений |
| _model_to_response() | model.reliability_score | Без изменений (API) |
| _calculate_recent_metrics() | F010 recent stats | Изменится внутренний расчёт |

---

## 3. План изменений

### 3.1 Новые компоненты

| # | Компонент | Путь | Описание |
|---|-----------|------|----------|
| 1 | `__init__.py` | `app/domain/services/__init__.py` | Инициализация модуля |
| 2 | `ReliabilityService` | `app/domain/services/reliability_service.py` | Domain service для расчёта |

#### 3.1.1 ReliabilityService (FR-001)

**Файл**: `app/domain/services/reliability_service.py`

```python
"""
Domain service для расчёта reliability score.

F016: Single Source of Truth для формулы reliability_score.
"""


class ReliabilityService:
    """
    Domain service для расчёта reliability score AI моделей.

    Формула: reliability_score = (success_rate × SUCCESS_WEIGHT) + (speed_score × SPEED_WEIGHT)

    F011 Edge Case:
        Если success_rate = 0.0, возвращает 0.0 независимо от speed_score.
        Модель с 0% успешности бесполезна, даже если быстрая.
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
            >>> ReliabilityService.calculate(0.9, 2.0)
            0.86  # (0.9 × 0.6) + (0.8 × 0.4)

            >>> ReliabilityService.calculate(0.0, 1.0)
            0.0  # F011: zero success → zero reliability

            >>> ReliabilityService.calculate(1.0, 15.0)
            0.6  # (1.0 × 0.6) + (0.0 × 0.4)
        """
        # F011: Zero success rate → zero reliability
        if success_rate == 0.0:
            return 0.0

        # Calculate speed score (0.0-1.0)
        # Formula: 1.0 - (time / baseline), clamped to [0.0, 1.0]
        speed_score = max(0.0, 1.0 - (avg_response_time / ReliabilityService.SPEED_BASELINE_SECONDS))

        # Calculate weighted reliability
        return (success_rate * ReliabilityService.SUCCESS_WEIGHT) + \
               (speed_score * ReliabilityService.SPEED_WEIGHT)
```

**Характеристики**:
- ✅ Stateless (pure function)
- ✅ F011 edge case handling
- ✅ Configurable weights (class constants)
- ✅ Docstring с примерами

---

#### 3.1.2 Module __init__.py

**Файл**: `app/domain/services/__init__.py`

```python
"""Domain services для Data API."""

from app.domain.services.reliability_service import ReliabilityService

__all__ = ["ReliabilityService"]
```

---

### 3.2 Модификации существующего кода

#### 3.2.1 Domain Model Property (FR-002)

**Файл**: `app/domain/models.py:70-80`

**До**:
```python
@property
def reliability_score(self) -> float:
    """
    Calculate reliability score (0.0 - 1.0).
    Formula: reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

    Note: If success_rate = 0, returns 0.0 (F011 fix).
    """
    if self.success_rate == 0.0:
        return 0.0
    return (self.success_rate * 0.6) + (self.speed_score * 0.4)
```

**После**:
```python
@property
def reliability_score(self) -> float:
    """
    Calculate reliability score (0.0 - 1.0).

    Делегирует расчёт в ReliabilityService (F016 SSoT).

    F011 Edge Case: Returns 0.0 if success_rate = 0.
    """
    from app.domain.services.reliability_service import ReliabilityService

    return ReliabilityService.calculate(
        success_rate=self.success_rate,
        avg_response_time=self.average_response_time
    )
```

**Изменения**:
1. Импорт `ReliabilityService` (внутри метода для избежания циклического импорта)
2. Делегация в `ReliabilityService.calculate()`
3. Передача `self.success_rate` и `self.average_response_time`
4. Удаление inline формулы

**Backward compatibility**: ✅ API property не изменился

---

#### 3.2.2 Recent Metrics Calculation (FR-003)

**Файл**: `app/api/v1/models.py:383-429`

**До**:
```python
def _calculate_recent_metrics(
    model: AIModel, recent_stats: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate recent metrics for a model (F010).
    ...
    """
    stats = recent_stats.get(model.id, {})
    request_count = stats.get("request_count", 0)
    success_count = stats.get("success_count", 0)
    avg_response_time = stats.get("avg_response_time", 0.0)

    if request_count >= MIN_REQUESTS_FOR_RECENT:
        recent_success_rate = success_count / request_count
        # F011: Zero success rate = zero reliability
        if recent_success_rate == 0.0:
            recent_reliability = 0.0
            recent_speed_score = 0.0
        else:
            recent_speed_score = max(0.0, 1.0 - (avg_response_time / 10.0))
            recent_reliability = (recent_success_rate * 0.6) + (recent_speed_score * 0.4)  # ← Удалить

        return {
            "recent_reliability_score": round(recent_reliability, 4),
            "effective_reliability_score": round(recent_reliability, 4),
            "decision_reason": "recent_score",
        }
    else:
        return {
            "recent_reliability_score": None,
            "recent_request_count": request_count,
            "effective_reliability_score": round(model.reliability_score, 4),
            "decision_reason": "fallback",
        }
```

**После**:
```python
def _calculate_recent_metrics(
    model: AIModel, recent_stats: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate recent metrics for a model (F010).

    If model has >= MIN_REQUESTS_FOR_RECENT requests in window,
    uses recent_reliability_score (F016: via ReliabilityService).
    Otherwise falls back to long-term score.

    Args:
        model: AIModel domain entity
        recent_stats: Dict from get_recent_stats_for_all_models()

    Returns:
        Dict with recent_*, effective_*, and decision_reason fields
    """
    from app.domain.services.reliability_service import ReliabilityService  # ← NEW

    stats = recent_stats.get(model.id, {})
    request_count = stats.get("request_count", 0)
    success_count = stats.get("success_count", 0)
    avg_response_time = stats.get("avg_response_time", 0.0)

    if request_count >= MIN_REQUESTS_FOR_RECENT:
        recent_success_rate = success_count / request_count

        # F016: Use ReliabilityService instead of inline formula
        recent_reliability = ReliabilityService.calculate(
            success_rate=recent_success_rate,
            avg_response_time=avg_response_time
        )

        return {
            "recent_success_rate": round(recent_success_rate, 4),
            "recent_request_count": request_count,
            "recent_reliability_score": round(recent_reliability, 4),
            "effective_reliability_score": round(recent_reliability, 4),
            "decision_reason": "recent_score",
        }
    else:
        return {
            "recent_success_rate": None,
            "recent_request_count": request_count,
            "recent_reliability_score": None,
            "effective_reliability_score": round(model.reliability_score, 4),
            "decision_reason": "fallback",
        }
```

**Изменения**:
1. Импорт `ReliabilityService` в начале функции
2. Удаление inline формулы (10 строк)
3. Замена на `ReliabilityService.calculate()`
4. Удаление explicit F011 handling (теперь в сервисе)

**Backward compatibility**: ✅ Функция возвращает тот же dict

---

### 3.3 Новые зависимости

❌ **Нет новых внешних зависимостей**

Все изменения используют стандартную библиотеку Python.

---

## 4. API Контракты

### 4.1 Публичные API

❌ **Нет изменений в публичных API**

Endpoints Data API остаются без изменений:
- `GET /models` — возвращает те же поля
- `GET /models/{model_id}` — возвращает те же поля

### 4.2 Internal API

✅ **Новый Internal API**: `ReliabilityService.calculate()`

**Сигнатура**:
```python
@staticmethod
def calculate(success_rate: float, avg_response_time: float) -> float:
    """
    Args:
        success_rate: 0.0-1.0 (процент успешных запросов)
        avg_response_time: ≥0.0 (среднее время ответа в секундах)

    Returns:
        reliability_score: 0.0-1.0

    Raises:
        Нет (pure function, не может упасть)
    """
```

**Контракт**:
- ✅ Stateless (не зависит от состояния)
- ✅ Deterministic (одинаковые inputs → одинаковый output)
- ✅ Pure function (нет side effects)

---

## 5. Влияние на существующие тесты

### 5.1 Регрессионные тесты (должны пройти БЕЗ изменений)

| Тест | Файл | Статус |
|------|------|--------|
| `test_reliability_score()` | test_domain_models.py:111 | ✅ Должен пройти |
| `test_reliability_score_zero_when_no_success()` | test_domain_models.py:133 | ✅ Должен пройти |
| `test_reliability_score_zero_when_no_requests()` | test_domain_models.py:154 | ✅ Должен пройти |
| `test_calculate_recent_metrics_with_sufficient_data()` | test_f015_dry_refactoring.py:124 | ✅ Должен пройти |
| `test_calculate_recent_metrics_with_insufficient_data()` | test_f015_dry_refactoring.py:142 | ✅ Должен пройти |
| `test_calculate_recent_metrics_zero_success_rate()` | test_f015_dry_refactoring.py:161 | ✅ Должен пройти |

**Критерий успеха**: ВСЕ 6 существующих тестов должны пройти без изменений.

---

### 5.2 Новые тесты для ReliabilityService

**Файл**: `tests/unit/test_reliability_service.py` (NEW)

| # | Тест | Покрытие |
|---|------|----------|
| 1 | `test_calculate_basic()` | Основной расчёт (0.9, 2.0 → ~0.86) |
| 2 | `test_calculate_zero_success()` | F011: success_rate=0 → 0.0 |
| 3 | `test_calculate_slow_response()` | Slow model (1.0, 15.0 → 0.6) |
| 4 | `test_calculate_fast_response()` | Fast model (1.0, 0.5 → 0.98) |
| 5 | `test_calculate_perfect_score()` | Perfect (1.0, 0.0 → 1.0) |

**Код тестов**:
```python
"""Unit tests for ReliabilityService (F016)."""

import pytest
from app.domain.services.reliability_service import ReliabilityService


class TestReliabilityService:
    """Tests for ReliabilityService.calculate()."""

    def test_calculate_basic(self):
        """Test basic reliability calculation."""
        # success_rate = 0.9, avg_time = 2.0
        # speed_score = 1.0 - (2.0 / 10.0) = 0.8
        # reliability = (0.9 × 0.6) + (0.8 × 0.4) = 0.54 + 0.32 = 0.86
        result = ReliabilityService.calculate(0.9, 2.0)
        assert abs(result - 0.86) < 0.001

    def test_calculate_zero_success(self):
        """Test F011: zero success rate → zero reliability."""
        result = ReliabilityService.calculate(0.0, 1.0)
        assert result == 0.0

    def test_calculate_slow_response(self):
        """Test slow model (time > baseline)."""
        # success_rate = 1.0, avg_time = 15.0 (> 10.0 baseline)
        # speed_score = max(0.0, 1.0 - (15.0 / 10.0)) = 0.0
        # reliability = (1.0 × 0.6) + (0.0 × 0.4) = 0.6
        result = ReliabilityService.calculate(1.0, 15.0)
        assert abs(result - 0.6) < 0.001

    def test_calculate_fast_response(self):
        """Test fast model."""
        # success_rate = 1.0, avg_time = 0.5
        # speed_score = 1.0 - (0.5 / 10.0) = 0.95
        # reliability = (1.0 × 0.6) + (0.95 × 0.4) = 0.6 + 0.38 = 0.98
        result = ReliabilityService.calculate(1.0, 0.5)
        assert abs(result - 0.98) < 0.001

    def test_calculate_perfect_score(self):
        """Test perfect model (100% success, instant response)."""
        # success_rate = 1.0, avg_time = 0.0
        # speed_score = 1.0 - (0.0 / 10.0) = 1.0
        # reliability = (1.0 × 0.6) + (1.0 × 0.4) = 1.0
        result = ReliabilityService.calculate(1.0, 0.0)
        assert result == 1.0
```

---

## 6. План интеграции

### 6.1 Последовательность реализации

| # | Шаг | Описание | Зависимости |
|---|-----|----------|-------------|
| 1 | Создать domain/services/ структуру | `__init__.py` + `reliability_service.py` | — |
| 2 | Написать unit тесты для ReliabilityService | 5 тестов (TRQ-001, TRQ-002) | Шаг 1 |
| 3 | Запустить тесты сервиса | `pytest tests/unit/test_reliability_service.py` | Шаг 2 |
| 4 | Мигрировать domain/models.py | AIModel.reliability_score → делегация | Шаг 3 |
| 5 | Запустить регрессионные тесты (domain) | `pytest tests/unit/test_domain_models.py` | Шаг 4 |
| 6 | Мигрировать api/v1/models.py | _calculate_recent_metrics() → сервис | Шаг 5 |
| 7 | Запустить регрессионные тесты (F010, F015) | `pytest tests/unit/test_f015_dry_refactoring.py` | Шаг 6 |
| 8 | Запустить все тесты Data API | `make test-data` | Шаг 7 |
| 9 | Code review (self) | Проверить, что формула удалена | Шаг 8 |
| 10 | Создать git commit | F016: Reliability Score SSoT | Шаг 9 |

---

### 6.2 Детальные инструкции для шага 1

#### Создать domain/services/ структуру

```bash
# 1. Создать директорию
mkdir -p services/free-ai-selector-data-postgres-api/app/domain/services

# 2. Создать __init__.py
touch services/free-ai-selector-data-postgres-api/app/domain/services/__init__.py

# 3. Создать reliability_service.py
# (использовать код из раздела 3.1.1)
```

**Проверка**:
```bash
ls -la services/free-ai-selector-data-postgres-api/app/domain/services/
# Ожидается:
# __init__.py
# reliability_service.py
```

---

### 6.3 Детальные инструкции для шага 2-3

#### Написать и запустить unit тесты

```bash
# 1. Создать test_reliability_service.py
# (использовать код из раздела 5.2)

# 2. Запустить тесты
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_reliability_service.py -v

# Ожидается: 5/5 passed
```

---

### 6.4 Детальные инструкции для шага 4-5

#### Мигрировать domain/models.py

**Изменение**:
```python
# В app/domain/models.py:70-80
# ЗАМЕНИТЬ весь метод reliability_score на код из раздела 3.2.1 (После)
```

**Проверка**:
```bash
# Запустить регрессионные тесты domain model
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_domain_models.py::TestAIModel::test_reliability_score -v
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_domain_models.py::TestAIModel::test_reliability_score_zero_when_no_success -v
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_domain_models.py::TestAIModel::test_reliability_score_zero_when_no_requests -v

# Ожидается: 3/3 passed
```

---

### 6.5 Детальные инструкции для шага 6-7

#### Мигрировать api/v1/models.py

**Изменение**:
```python
# В app/api/v1/models.py:383-429
# ЗАМЕНИТЬ _calculate_recent_metrics() на код из раздела 3.2.2 (После)
```

**Проверка**:
```bash
# Запустить регрессионные тесты F010, F015
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_f015_dry_refactoring.py -v

# Ожидается: все тесты пройдены (8 tests)
```

---

### 6.6 Детальные инструкции для шага 8

#### Запустить все тесты Data API

```bash
make test-data
# или
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/ -v

# Ожидается: все тесты пройдены
```

**Если есть failure**:
1. Проверить логи pytest
2. Убедиться, что импорты корректны
3. Проверить, что формула в сервисе идентична старой

---

### 6.7 Детальные инструкции для шага 9

#### Code Review Checklist

- [ ] ✅ `ReliabilityService.calculate()` создан
- [ ] ✅ Weights вынесены в class constants (SUCCESS_WEIGHT, SPEED_WEIGHT)
- [ ] ✅ F011 edge case handling в сервисе
- [ ] ✅ `domain/models.py` делегирует в сервис
- [ ] ✅ `api/v1/models.py` использует сервис
- [ ] ✅ Inline формулы удалены (grep "0.6.*0.4" не находит)
- [ ] ✅ 5 новых тестов для сервиса
- [ ] ✅ 6 регрессионных тестов проходят

**Проверка удаления дублирования**:
```bash
# В директории Data API
grep -rn "0.6.*0.4" app/

# Ожидается: НЕТ результатов (или только в комментариях)
```

---

### 6.8 Детальные инструкции для шага 10

#### Создать git commit

```bash
git add services/free-ai-selector-data-postgres-api/app/domain/services/
git add services/free-ai-selector-data-postgres-api/app/domain/models.py
git add services/free-ai-selector-data-postgres-api/app/api/v1/models.py
git add services/free-ai-selector-data-postgres-api/tests/unit/test_reliability_service.py

git commit -m "$(cat <<'EOF'
feat(F016): reliability score SSoT via ReliabilityService

Create domain service for reliability score calculation to eliminate
formula duplication in 2 places (domain/models.py, api/v1/models.py).

Changes:
- Add ReliabilityService in domain/services/
- Weights as class constants (SUCCESS_WEIGHT=0.6, SPEED_WEIGHT=0.4)
- Migrate AIModel.reliability_score to use service
- Migrate _calculate_recent_metrics() to use service
- Add 5 unit tests for ReliabilityService
- All 6 regression tests pass (F010, F011, F015)

Quality Cascade:
- QC-1 (DRY): 2 places → 1 SSoT ✅
- QC-10 (SSoT): Single source of truth restored ✅

Breaking changes: None
DB migration: Not required

Related: F010 (Rolling Window), F015 (Data API DRY)
EOF
)"
```

---

## 7. Риски и митигация

### 7.1 Технические риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Floating point inconsistency | Low | Medium | Unit tests с фиксированными inputs |
| 2 | Циклический импорт domain/models ← services | Low | High | Импорт внутри метода |
| 3 | Производительность (extra function call) | Very Low | Low | Stateless метод, inline-able |
| 4 | Regression в F010 recent metrics | Low | Medium | Запуск всех F010, F015 тестов |

---

### 7.2 Стратегия митигации

#### Риск #1: Floating Point Inconsistency

**Проблема**: Старая и новая реализация могут давать слегка разные результаты из-за порядка операций.

**Митигация**:
```python
# test_reliability_service.py
def test_consistency_with_legacy():
    """Убедиться, что сервис даёт тот же результат, что старый код."""
    success_rate = 0.9
    avg_response_time = 2.0

    # Старая формула
    speed_score_old = max(0.0, 1.0 - (avg_response_time / 10.0))
    old_result = (success_rate * 0.6) + (speed_score_old * 0.4)

    # Новая формула
    new_result = ReliabilityService.calculate(success_rate, avg_response_time)

    # Должны совпадать с точностью до машинного epsilon
    assert abs(old_result - new_result) < 1e-9
```

---

#### Риск #2: Циклический импорт

**Проблема**: `domain/models.py` импортирует `domain/services/reliability_service.py`, который может импортировать models.

**Митигация**:
1. **Импорт внутри метода** (текущее решение):
   ```python
   @property
   def reliability_score(self) -> float:
       from app.domain.services.reliability_service import ReliabilityService
       return ReliabilityService.calculate(...)
   ```

2. **Альтернатива (если нужны type hints)**:
   ```python
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from app.domain.services.reliability_service import ReliabilityService
   ```

**Текущее решение**: Вариант 1 (импорт внутри метода) — достаточно для этой задачи.

---

#### Риск #3: Производительность

**Проблема**: Дополнительный вызов функции может замедлить расчёт.

**Анализ**:
- Метод stateless и простой (3-4 операции)
- Python compiler может inline простые методы
- Вызывается ПОСЛЕ чтения из БД (I/O доминирует)

**Вывод**: ❌ Не является проблемой (CPU overhead < 0.1% от I/O)

---

#### Риск #4: Regression в F010

**Проблема**: Изменение `_calculate_recent_metrics()` может сломать F010 rolling window.

**Митигация**:
1. Запустить ВСЕ тесты F010:
   ```bash
   docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/ -k "recent" -v
   ```

2. Запустить ВСЕ тесты F015 (DRY refactoring):
   ```bash
   docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_f015_dry_refactoring.py -v
   ```

3. Убедиться, что `recent_reliability_score` возвращает тот же результат:
   ```python
   # В _calculate_recent_metrics()
   # ДО: recent_reliability = (recent_success_rate * 0.6) + (recent_speed_score * 0.4)
   # ПОСЛЕ: recent_reliability = ReliabilityService.calculate(recent_success_rate, avg_response_time)
   # Должны давать одинаковый результат
   ```

---

## 8. Тестирование

### 8.1 Test Plan

| Фаза | Тесты | Критерий успеха |
|------|-------|-----------------|
| Unit | 5 новых тестов ReliabilityService | 5/5 passed |
| Regression (domain) | 3 теста AIModel.reliability_score | 3/3 passed |
| Regression (F010) | 3 теста _calculate_recent_metrics | 3/3 passed |
| Regression (F015) | 8 тестов DRY refactoring | 8/8 passed |
| Full suite | Все тесты Data API | 100% passed |

---

### 8.2 Команды для запуска тестов

```bash
# 1. Unit тесты ReliabilityService (TRQ-001)
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_reliability_service.py -v

# 2. Regression: domain models (TRQ-003)
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_domain_models.py::TestAIModel -k reliability -v

# 3. Regression: F010 recent metrics
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_f015_dry_refactoring.py -k recent -v

# 4. Regression: F015 DRY refactoring
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_f015_dry_refactoring.py -v

# 5. Full suite
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/ -v
```

---

### 8.3 Expected Test Output

**Шаг 1**: Unit тесты сервиса
```
tests/unit/test_reliability_service.py::TestReliabilityService::test_calculate_basic PASSED
tests/unit/test_reliability_service.py::TestReliabilityService::test_calculate_zero_success PASSED
tests/unit/test_reliability_service.py::TestReliabilityService::test_calculate_slow_response PASSED
tests/unit/test_reliability_service.py::TestReliabilityService::test_calculate_fast_response PASSED
tests/unit/test_reliability_service.py::TestReliabilityService::test_calculate_perfect_score PASSED

========== 5 passed in 0.05s ==========
```

**Шаг 2-4**: Regression тесты
```
tests/unit/test_domain_models.py::TestAIModel::test_reliability_score PASSED
tests/unit/test_domain_models.py::TestAIModel::test_reliability_score_zero_when_no_success PASSED
tests/unit/test_domain_models.py::TestAIModel::test_reliability_score_zero_when_no_requests PASSED

tests/unit/test_f015_dry_refactoring.py::test_calculate_recent_metrics_with_sufficient_data PASSED
tests/unit/test_f015_dry_refactoring.py::test_calculate_recent_metrics_with_insufficient_data PASSED
tests/unit/test_f015_dry_refactoring.py::test_calculate_recent_metrics_zero_success_rate PASSED

========== 9 passed in 0.15s ==========
```

---

## 9. Качественный каскад (Quality Cascade)

### 9.1 Трассировка Quality Criteria

| # | Критерий | До F016 | После F016 | Статус |
|---|----------|---------|------------|--------|
| QC-1 | **DRY** (Don't Repeat Yourself) | ❌ 2 места дублирования | ✅ 1 SSoT | ✅ Улучшено |
| QC-2 | **KISS** (Keep It Simple) | ⚠️ Inline формулы | ✅ Изолированный метод | ✅ Улучшено |
| QC-4 | **SRP** (Single Responsibility) | ⚠️ @property с логикой | ✅ Domain service | ✅ Улучшено |
| QC-10 | **SSoT** (Single Source of Truth) | ❌ 2 источника формулы | ✅ 1 источник | ✅ Улучшено |
| QC-11 | **Testability** | ⚠️ Domain model property | ✅ Stateless service | ✅ Улучшено |

**Legend**: ✅ Соблюдается, ⚠️ Частично, ❌ Нарушается

---

### 9.2 Связь с Requirements Traceability Matrix (RTM)

| Требование | Реализация | Тест | Статус |
|------------|-----------|------|--------|
| FR-001 | ReliabilityService создан | test_calculate_basic | ✅ |
| FR-002 | domain/models.py использует сервис | test_reliability_score (regression) | ✅ |
| FR-003 | api/v1/models.py использует сервис | test_calculate_recent_metrics (regression) | ✅ |
| FR-010 | Weights как class constants | ReliabilityService.SUCCESS_WEIGHT | ✅ |
| TRQ-001 | Unit тест ReliabilityService | test_reliability_service.py (5 tests) | ✅ |
| TRQ-003 | Regression тесты | Все существующие тесты | ✅ |

---

## 10. Rollback Strategy

### 10.1 Условия rollback

**Rollback требуется если**:
- ❌ Регрессионные тесты не проходят
- ❌ Production metrics деградируют (reliability_score расходится)
- ❌ Производительность снижается > 5%

### 10.2 Команды rollback

```bash
# 1. Revert git commit
git revert <commit-hash>

# 2. Rebuild и redeploy
make build
make up

# 3. Проверить health
make health
```

### 10.3 Проверка после rollback

```bash
# Убедиться, что старые формулы работают
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/test_domain_models.py -v
```

---

## 11. Метрики успеха

### 11.1 Код метрики

| Метрика | До | После | Target | Статус |
|---------|----|----|--------|--------|
| Места с формулой | 2 | 1 | 1 | ✅ |
| Hardcoded constants | 4 | 0 | 0 | ✅ |
| Unit тесты (SSoT) | 0 | 5 | ≥5 | ✅ |
| Regression coverage | 3 | 9 | 100% | ✅ |

---

### 11.2 Quality метрики

| Метрика | До | После | Target |
|---------|----|----|--------|
| DRY violations | 1 | 0 | 0 |
| SSoT violations | 1 | 0 | 0 |
| Testability | Medium | High | High |
| Cyclomatic complexity | 2×2=4 | 2 | ≤5 |

---

## 12. Зависимости и блокеры

### 12.1 Upstream зависимости

| Фича | Статус | Блокирует F016? |
|------|--------|-----------------|
| F010 (Rolling Window) | DEPLOYED | ❌ Нет |
| F015 (Data API DRY) | DOCUMENTED | ❌ Нет |

**Вывод**: ✅ Нет блокирующих зависимостей

---

### 12.2 Downstream зависимости

| Компонент | Использует reliability_score? | Влияние F016 |
|-----------|-------------------------------|--------------|
| Business API | Да (через Data API GET /models) | ❌ Нет (контракт не изменился) |
| Health Worker | Нет | ❌ Нет |
| Telegram Bot | Нет (не использует reliability) | ❌ Нет |

**Вывод**: ✅ Изменения изолированы в Data API

---

## 13. Документация

### 13.1 Обновление документации

| Файл | Действие | Описание |
|------|----------|----------|
| `CLAUDE.md` | ❌ Нет изменений | Проект-специфичная документация |
| `docs/ai-context/EXAMPLES.md` | ⚠️ Опционально | Добавить пример ReliabilityService |

### 13.2 Code documentation

✅ **Все новые компоненты документированы**:
- `ReliabilityService` класс — docstring с формулой и примерами
- `calculate()` метод — docstring с Args/Returns/Examples
- Обновлённые методы — docstring указывает на F016

---

## 14. Чеклист готовности к реализации

### 14.1 Предусловия

- [x] ✅ PRD_READY пройден (F016 PRD exists)
- [x] ✅ RESEARCH_DONE пройден (research report exists)
- [x] ✅ Архитектура определена (Domain Service pattern)
- [x] ✅ План детализирован (пошаговые инструкции)

### 14.2 Риски

- [x] ✅ Риски идентифицированы (4 риска)
- [x] ✅ Митигация определена (для всех 4)
- [x] ✅ Rollback стратегия описана

### 14.3 Тестирование

- [x] ✅ Test plan создан (5 фаз)
- [x] ✅ Новые тесты спроектированы (5 тестов)
- [x] ✅ Regression тесты определены (9 тестов)

---

## 15. Ожидаемый результат

### 15.1 До F016

```
app/domain/models.py:80:
    return (self.success_rate * 0.6) + (self.speed_score * 0.4)

app/api/v1/models.py:412:
    recent_reliability = (recent_success_rate * 0.6) + (recent_speed_score * 0.4)

Метрики:
- 2 места с формулой
- 4 hardcoded constants
- 0 domain services
```

### 15.2 После F016

```
app/domain/services/reliability_service.py:
    class ReliabilityService:
        SUCCESS_WEIGHT = 0.6
        SPEED_WEIGHT = 0.4

        @staticmethod
        def calculate(success_rate: float, avg_response_time: float) -> float:
            ...

app/domain/models.py:
    return ReliabilityService.calculate(self.success_rate, self.average_response_time)

app/api/v1/models.py:
    recent_reliability = ReliabilityService.calculate(recent_success_rate, avg_response_time)

Метрики:
- 1 место с формулой (SSoT)
- 0 hardcoded constants
- 1 domain service
- 5 новых unit тестов
```

---

## 16. Утверждение плана

### 16.1 Checklist для пользователя

Перед утверждением плана проверьте:

- [ ] ✅ Scope понятен (2 файла изменяются, 2 создаются)
- [ ] ✅ Breaking changes отсутствуют
- [ ] ✅ Rollback стратегия определена
- [ ] ✅ Тесты покрывают новую логику (5 новых + 9 regression)
- [ ] ✅ Пошаговые инструкции детализированы (10 шагов)

### 16.2 Вопросы для обсуждения

Если есть вопросы по плану:

1. **Архитектура**: Domain Service подходит для этой задачи?
2. **Производительность**: Беспокоит дополнительный вызов функции?
3. **Тестирование**: Достаточно ли 5 новых тестов?
4. **Weights**: Нужна ли конфигурация через ENV (вместо class constants)?

---

## Чеклист ворот PLAN_APPROVED

> ⚠️ AI ОБЯЗАН дождаться утверждения от пользователя!

- [x] 🔴 Feature Plan создан в `_plans/features/2026-01-30_F016_reliability-score-ssot.md`
- [x] 🔴 Интеграция с существующим кодом описана (domain/models.py, api/v1/models.py)
- [ ] 🔴 **Пользователь утвердил план** ← ОЖИДАЕТСЯ
- [ ] 🔴 `.pipeline-state.json` будет обновлён после утверждения
- [x] 🟡 Breaking changes определены (нет)
- [x] 🟡 Миграции БД описаны (не требуются)

---

**Статус**: ⏳ ОЖИДАЕТ УТВЕРЖДЕНИЯ

**Следующий шаг**: Если план утверждён → `/aidd-code F016`
