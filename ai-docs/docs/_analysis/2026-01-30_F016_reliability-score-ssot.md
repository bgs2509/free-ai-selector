---
feature_id: "F016"
feature_name: "reliability-score-ssot"
title: "Reliability Score: Single Source of Truth"
created: "2026-01-30"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 1
mode: "FEATURE"

related_features: [F010]
services: [free-ai-selector-data-postgres-api]
requirements_count: 3

pipelines:
  business: false
  data: true
  integration: false
  modified: [data_api_domain]
---

# PRD: Reliability Score Single Source of Truth

**Feature ID**: F016
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Аналитик)
**Статус**: PRD_READY
**Тип**: Рефакторинг (Quality Cascade QC-10/SSoT)

---

## 1. Обзор

### 1.1 Проблема

Бизнес-логика расчёта `reliability_score` **дублируется** в двух местах:

```
services/free-ai-selector-data-postgres-api/
├── app/domain/models.py:70-80          ← Расчёт в domain model
└── app/api/v1/models.py:396-402        ← Повторный расчёт в endpoint
```

**Формула:**
```python
reliability_score = (success_rate * 0.6) + (speed_score * 0.4)
```

**Проблемы:**
- Нарушение SSoT (Single Source of Truth)
- Риск расхождения логики при изменениях
- Усложнённое тестирование

### 1.2 Решение

Вынести расчёт `reliability_score` в **Domain Service** и использовать его везде:

```python
# app/domain/services/reliability_service.py
class ReliabilityService:
    """Сервис расчёта reliability score."""

    SUCCESS_WEIGHT = 0.6
    SPEED_WEIGHT = 0.4

    @staticmethod
    def calculate(success_rate: float, avg_response_time: float) -> float:
        """
        Рассчитывает reliability score.

        Args:
            success_rate: Процент успешных запросов (0-100)
            avg_response_time: Среднее время ответа в ms

        Returns:
            Reliability score (0-100)
        """
        speed_score = max(0, 100 - avg_response_time / 10)
        return (success_rate * ReliabilityService.SUCCESS_WEIGHT) + \
               (speed_score * ReliabilityService.SPEED_WEIGHT)
```

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Разработчики | Те кто работает с reliability | Единая точка изменений |
| AI Ops | Те кто настраивает weights | Конфигурируемость |

### 1.4 Ценностное предложение

- **SSoT**: Одно место для логики расчёта
- **Тестируемость**: Изолированный unit test
- **Конфигурируемость**: Weights как class constants

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | ReliabilityService | Создать domain service для расчёта | Сервис в domain/services/ |
| FR-002 | Миграция domain/models.py | Использовать сервис вместо inline расчёта | models.py вызывает сервис |
| FR-003 | Миграция api/v1/models.py | Использовать сервис вместо inline расчёта | endpoint вызывает сервис |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-010 | Configurable weights | Weights как class constants | SUCCESS_WEIGHT, SPEED_WEIGHT |

---

## 3. User Stories

### US-001: Разработчик меняет формулу reliability

**Как** разработчик
**Я хочу** изменить формулу в одном месте
**Чтобы** изменение применилось везде автоматически

**Критерии приёмки:**
- [ ] ReliabilityService.calculate() — единственное место расчёта
- [ ] Изменение weights влияет на все использования

**Связанные требования:** FR-001, FR-002, FR-003

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (рефакторинг) |
| Затрагиваемые пайплайны | data_api_domain |

### 4.4 Влияние на существующие пайплайны

| Пайплайн | Тип изменения | Обратная совместимость |
|----------|---------------|------------------------|
| data_api_domain | add service, modify callers | Да |

**Breaking changes:**
- [x] Нет breaking changes

---

## 6. Нефункциональные требования

### 6.5 Требования к тестированию

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Unit | Тест ReliabilityService.calculate() | ✅ Да |
| TRQ-002 | Unit | Тест с разными weights | ✅ Да |
| TRQ-003 | Regression | Существующие тесты проходят | ✅ Да |

---

## 7. Технические ограничения

### 7.1 Файлы для изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `domain/services/reliability_service.py` | Create | Новый domain service |
| `domain/models.py` | Modify | Использовать сервис |
| `api/v1/models.py` | Modify | Использовать сервис |

### 7.2 Структура

```
app/domain/
├── models.py
└── services/
    ├── __init__.py
    └── reliability_service.py  ← NEW
```

---

## 8. Допущения и риски

### 8.1 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение результатов | Low | Med | Unit tests с fixed inputs |

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
2 места с дублированием формулы
Weights hardcoded
```

**После рефакторинга:**
```
1 ReliabilityService с методом calculate()
Weights как class constants
2 места используют сервис
```
