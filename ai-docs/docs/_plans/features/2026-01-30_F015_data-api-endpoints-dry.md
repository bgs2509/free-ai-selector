---
feature_id: "F015"
feature_name: "data-api-endpoints-dry"
title: "Data API Endpoints: DRY Refactoring"
created: "2026-01-30"
author: "AI (Architect)"
type: "implementation-plan"
status: "PENDING_APPROVAL"
version: 1
mode: "FEATURE"

related_features: [F010, F012]
services: [free-ai-selector-data-postgres-api]
---

# План реализации: F015 Data API Endpoints DRY Refactoring

**Feature ID**: F015
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Архитектор)
**Статус**: PENDING_APPROVAL

---

## 1. Обзор

### 1.1 Цель рефакторинга

Устранение ~93 строк дублирования в `models.py` Data API:
1. Объединение двух `_model_to_response()` функций в одну
2. Создание FastAPI dependency `get_model_or_404()` для 6 эндпоинтов

### 1.2 Связь с существующим функционалом

- **F010** (Rolling Window): Логика `effective_reliability_score` сохраняется
- **F012** (Rate Limit): `available_at` поле сохраняется

### 1.3 Метрики до/после

| Метрика | До | После |
|---------|-----|-------|
| `_model_to_response` функций | 2 (~79 строк) | 1 (~45 строк) |
| Мест с get+404 паттерном | 6 | 0 |
| Строк дублирования | ~93 | 0 |
| **Итого изменение LOC** | — | **-44** |

---

## 2. Анализ существующего кода

### 2.1 Целевые файлы

| Файл | Строк | Описание |
|------|-------|----------|
| `app/api/v1/models.py` | 463 | 14 эндпоинтов, целевой файл |
| `app/api/deps.py` | ~20 | Существующие dependencies |

### 2.2 Функции для объединения

| Функция | Строки | Параметры |
|---------|--------|-----------|
| `_model_to_response()` | 334-370 (37) | `model` |
| `_model_to_response_with_recent()` | 421-462 (42) | `model`, `recent_stats` |

**Различия**: только 5 полей `recent_*` (rest 14 полей идентичны)

### 2.3 Эндпоинты с get+404 паттерном

| # | Эндпоинт | Строки | Метод |
|---|----------|--------|-------|
| 1 | `GET /{model_id}` | 84-91 | `get_model_by_id` |
| 2 | `PUT /{model_id}/stats` | 167-180 | `update_model_stats` |
| 3 | `POST /{model_id}/increment-success` | 207-216 | `increment_success` |
| 4 | `POST /{model_id}/increment-failure` | 245-252 | `increment_failure` |
| 5 | `PATCH /{model_id}/active` | 277-284 | `set_model_active` |
| 6 | `PUT /{model_id}/availability` | 318-328 | `set_model_availability` |

---

## 3. План изменений

### 3.1 Новые компоненты

| Компонент | Расположение | Описание |
|-----------|--------------|----------|
| `get_model_or_404()` | `app/api/deps.py` | FastAPI dependency |

### 3.2 Модификации существующего кода

| Файл | Изменение | LOC | Причина |
|------|-----------|-----|---------|
| `app/api/deps.py` | Добавить `get_model_or_404` | +20 | FR-002 |
| `app/api/v1/models.py` | Unified `_model_to_response` | +45 / -79 | FR-001 |
| `app/api/v1/models.py` | Миграция 6 эндпоинтов | -30 | FR-003 |

### 3.3 Итоговое изменение LOC

| Тип | Строк |
|-----|-------|
| Добавлено | +65 |
| Удалено | -109 |
| **Итого** | **-44** |

---

## 4. Детальный дизайн

### 4.1 FR-002: Dependency `get_model_or_404()`

**Файл**: `app/api/deps.py`

```python
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import crud
from app.infrastructure.database.models import AIModel


async def get_model_or_404(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> AIModel:
    """
    FastAPI dependency: get model by ID or raise 404.

    Args:
        model_id: Model ID from path parameter
        db: Database session

    Returns:
        AIModel instance

    Raises:
        HTTPException: 404 if model not found
    """
    model = await crud.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with id {model_id} not found",
        )
    return model
```

### 4.2 FR-001: Unified `_model_to_response()`

**Файл**: `app/api/v1/models.py`

```python
def _model_to_response(
    model: AIModel,
    recent_stats: RecentModelStats | None = None,
) -> AIModelResponse:
    """
    Convert database model to API response.

    Args:
        model: Database model instance
        recent_stats: Optional recent statistics for F010 rolling window

    Returns:
        AIModelResponse with or without recent statistics

    Note:
        F010: effective_reliability_score calculated only when recent_stats provided
        F012: available_at field always included
    """
    # Вычисление recent полей только если recent_stats предоставлен
    if recent_stats:
        effective_score = _calculate_effective_score(model, recent_stats)
        decision_reason = _generate_decision_reason(model, recent_stats, effective_score)
        recent_request_count = recent_stats.request_count
        recent_success_rate = recent_stats.success_rate
        recent_avg_response_time = recent_stats.avg_response_time
    else:
        effective_score = None
        decision_reason = None
        recent_request_count = None
        recent_success_rate = None
        recent_avg_response_time = None

    return AIModelResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        api_format=model.api_format,
        env_var=model.env_var,
        is_active=model.is_active,
        total_requests=model.total_requests,
        successful_requests=model.successful_requests,
        failed_requests=model.failed_requests,
        total_response_time=model.total_response_time,
        reliability_score=model.reliability_score,
        available_at=model.available_at,  # F012
        created_at=model.created_at,
        updated_at=model.updated_at,
        recent_request_count=recent_request_count,
        recent_success_rate=recent_success_rate,
        recent_avg_response_time=recent_avg_response_time,
        effective_reliability_score=effective_score,  # F010
        decision_reason=decision_reason,
    )
```

### 4.3 FR-003: Миграция эндпоинтов

**Пример миграции `get_model_by_id`:**

**До:**
```python
@router.get("/{model_id}", response_model=AIModelResponse)
async def get_model_by_id(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> AIModelResponse:
    """Get a specific AI model by ID."""
    model = await crud.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with id {model_id} not found",
        )
    return _model_to_response(model)
```

**После:**
```python
@router.get("/{model_id}", response_model=AIModelResponse)
async def get_model_by_id(
    model: AIModel = Depends(get_model_or_404),
) -> AIModelResponse:
    """Get a specific AI model by ID."""
    return _model_to_response(model)
```

**Аналогичная миграция для остальных 5 эндпоинтов.**

---

## 5. API контракты

**Нет изменений** — рефакторинг внутренней реализации.

| Эндпоинт | Request | Response | Изменения |
|----------|---------|----------|-----------|
| `GET /{model_id}` | path: model_id | AIModelResponse | Нет |
| `PUT /{model_id}/stats` | path: model_id, body: stats | AIModelResponse | Нет |
| Остальные 4 | — | — | Нет |

---

## 6. Влияние на существующие тесты

### 6.1 Существующие тесты (не требуют изменений)

Все существующие тесты должны проходить без модификаций, так как:
- API контракты не изменяются
- 404 поведение сохраняется
- Response format идентичен

### 6.2 Новые тесты

| Тест | Описание | Приоритет |
|------|----------|-----------|
| `test_get_model_or_404_returns_model` | Проверка успешного получения | Must |
| `test_get_model_or_404_raises_404` | Проверка 404 для несуществующей модели | Must |
| `test_model_to_response_without_recent` | Проверка без recent_stats | Should |
| `test_model_to_response_with_recent` | Проверка с recent_stats | Should |

---

## 7. План интеграции

| # | Шаг | Описание | Зависимости |
|---|-----|----------|-------------|
| 1 | Добавить `get_model_or_404` | Создать dependency в deps.py | — |
| 2 | Создать unified `_model_to_response` | Объединить две функции | — |
| 3 | Мигрировать `get_model_by_id` | Первый эндпоинт | Шаги 1, 2 |
| 4 | Мигрировать `update_model_stats` | Второй эндпоинт | Шаг 3 |
| 5 | Мигрировать `increment_success` | Третий эндпоинт | Шаг 4 |
| 6 | Мигрировать `increment_failure` | Четвёртый эндпоинт | Шаг 5 |
| 7 | Мигрировать `set_model_active` | Пятый эндпоинт | Шаг 6 |
| 8 | Мигрировать `set_model_availability` | Шестой эндпоинт | Шаг 7 |
| 9 | Удалить `_model_to_response_with_recent` | Cleanup | Шаг 8 |
| 10 | Запустить тесты | Regression проверка | Шаг 9 |
| 11 | Добавить unit тесты | Покрытие новых компонентов | Шаг 10 |

---

## 8. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение API response | Low | High | Contract tests, regression |
| 2 | Regression в effective_score | Low | Medium | Сохранить логику F010 без изменений |
| 3 | Circular import в deps.py | Low | Medium | Импортировать crud внутри функции |

---

## 9. Breaking Changes

**Нет breaking changes:**

- [x] API контракты не изменяются
- [x] Response schema идентична
- [x] 404 сообщения идентичны
- [x] Все существующие тесты должны проходить

---

## 10. Чеклист Quality Cascade

| # | Проверка | Статус |
|---|----------|--------|
| QC-1 | DRY: Устранено ~93 строки дублирования | ✅ |
| QC-2 | KISS: Одна функция вместо двух | ✅ |
| QC-3 | YAGNI: Только необходимые изменения | ✅ |
| QC-4 | SoC: Dependency в deps.py, конвертер в models.py | ✅ |
| QC-5 | SSoT: Одна функция для конвертации | ✅ |
| QC-6 | CoC: FastAPI Depends() паттерн | ✅ |
| QC-7 | Security: 404 не раскрывает внутреннюю информацию | ✅ |

---

## 11. Ожидаемый результат

### До рефакторинга

```
models.py: 463 строки
├── _model_to_response(): 37 строк
├── _model_to_response_with_recent(): 42 строк
└── 6 эндпоинтов с get+404: ~48 строк дублирования
```

### После рефакторинга

```
models.py: ~419 строк (-44)
├── _model_to_response(): 45 строк (unified)
└── 6 эндпоинтов: используют get_model_or_404

deps.py: +20 строк
└── get_model_or_404(): dependency
```

---

## Качественные ворота PLAN_APPROVED

### Checklist

- [x] 🔴 Plan создан в `_plans/features/`
- [x] 🔴 Интеграция с существующим кодом описана
- [ ] 🔴 **Пользователь утвердил план**
- [ ] 🔴 `.pipeline-state.json` обновлён после утверждения
- [x] 🟡 Breaking changes определены (нет)
- [x] 🟡 Миграции БД описаны (не применимо)

---

## Следующий шаг

После утверждения плана пользователем:

```bash
/aidd-code  # Реализация
```

---

**Версия документа**: 1.0
**Обновлён**: 2026-01-30
