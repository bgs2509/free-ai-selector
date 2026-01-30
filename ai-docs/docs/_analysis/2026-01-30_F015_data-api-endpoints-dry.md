---
feature_id: "F015"
feature_name: "data-api-endpoints-dry"
title: "Data API Endpoints: DRY Refactoring"
created: "2026-01-30"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 1
mode: "FEATURE"

related_features: []
services: [free-ai-selector-data-postgres-api]
requirements_count: 4

pipelines:
  business: false
  data: true
  integration: false
  modified: [data_api_models]
---

# PRD: Data API Endpoints DRY Refactoring

**Feature ID**: F015
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Аналитик)
**Статус**: PRD_READY
**Тип**: Рефакторинг (Quality Cascade QC-1/DRY)

---

## 1. Обзор

### 1.1 Проблема

В файле `models.py` (Data API endpoints) обнаружены два нарушения DRY:

**Нарушение #1: Дублирование `_model_to_response()` функций**
```
services/free-ai-selector-data-postgres-api/app/api/v1/models.py:
├── _model_to_response()              (строки 334-370) — 36 строк
└── _model_to_response_with_recent()  (строки 421-462) — 41 строк
```
90% идентичного кода, отличие только в `recent_*` полях.

**Нарушение #2: Дублирование "get + 404" паттерна**
```
7 мест с идентичным паттерном:
строки 84-91, 117-125, 167-180, 207-216, 245-252, 277-284, 318-328

model = await repository.get_by_id(model_id)
if not model:
    raise HTTPException(status_code=404, detail="AI model not found")
```

### 1.2 Решение

1. **Объединить** `_model_to_response()` функции с optional параметром `include_recent`
2. **Создать** FastAPI dependency `get_model_or_404()`

**После рефакторинга:**
```python
# Unified function
def _model_to_response(model: AIModel, include_recent: bool = False) -> AIModelResponse:
    """Конвертирует модель в response, опционально включая recent_* поля."""
    pass

# Dependency
async def get_model_or_404(
    model_id: int,
    repository: AIModelRepository = Depends(get_repository)
) -> AIModel:
    """Получает модель или возвращает 404."""
    model = await repository.get_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="AI model not found")
    return model
```

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Разработчики | Те кто поддерживает Data API | DRY, единообразие |

### 1.4 Ценностное предложение

- **Сокращение кода**: ~77 строк → ~45 строк (response converters)
- **7 мест дублирования** → 1 dependency
- **Единообразие**: все endpoints используют одинаковый паттерн

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | Unified _model_to_response | Объединить две функции с параметром include_recent | Одна функция с optional параметром |
| FR-002 | get_model_or_404 dependency | Создать FastAPI dependency для получения модели | Dependency используется в 7 endpoints |
| FR-003 | Миграция endpoints | Обновить все endpoints использовать dependency | 7 endpoints используют get_model_or_404 |
| FR-004 | Сохранить поведение | Результат API должен быть идентичен | Все тесты проходят |

---

## 3. User Stories

### US-001: Разработчик добавляет новый endpoint

**Как** разработчик
**Я хочу** использовать готовый dependency для получения модели
**Чтобы** не дублировать код и обрабатывать 404 единообразно

**Критерии приёмки:**
- [ ] Новый endpoint использует `model: AIModel = Depends(get_model_or_404)`
- [ ] Не нужно писать if/raise HTTPException

**Связанные требования:** FR-002, FR-003

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (рефакторинг) |
| Затрагиваемые пайплайны | data_api (API layer) |

### 4.4 Влияние на существующие пайплайны

| Пайплайн | Тип изменения | Обратная совместимость |
|----------|---------------|------------------------|
| data_api_models | modify (internal) | Да |

**Breaking changes:**
- [x] Нет breaking changes — API контракты сохранены

---

## 5. Нефункциональные требования

### 6.5 Требования к тестированию

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Regression | Все существующие тесты проходят | ✅ Да |
| TRQ-002 | Unit | Тест для get_model_or_404 (found) | ✅ Да |
| TRQ-003 | Unit | Тест для get_model_or_404 (not found) | ✅ Да |

---

## 7. Технические ограничения

### 7.1 Файлы для изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `models.py` | Modify | Объединить функции, добавить dependency |

### 7.2 Затрагиваемые endpoints

- GET /api/v1/models/{model_id}
- PUT /api/v1/models/{model_id}
- DELETE /api/v1/models/{model_id}
- PATCH /api/v1/models/{model_id}/statistics
- GET /api/v1/models/{model_id}/statistics
- POST /api/v1/models/{model_id}/health-check
- GET /api/v1/models/{model_id}/with-stats (uses _with_recent)

---

## 8. Допущения и риски

### 8.1 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение response format | Low | High | Contract tests |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID
- [x] Критерии приёмки определены

---

## Ожидаемый результат

**До рефакторинга:**
```
2 функции _model_to_response (77 строк)
7 мест с дублированием get + 404
```

**После рефакторинга:**
```
1 функция _model_to_response (~40 строк)
1 dependency get_model_or_404
7 endpoints используют dependency
```
