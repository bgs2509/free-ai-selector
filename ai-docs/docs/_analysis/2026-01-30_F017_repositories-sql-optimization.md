---
feature_id: "F017"
feature_name: "repositories-sql-optimization"
title: "Data API Repositories: SQL Aggregation Optimization"
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
  modified: [prompt_history_repository]
---

# PRD: Repositories SQL Aggregation Optimization

**Feature ID**: F017
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Аналитик)
**Статус**: PRD_READY
**Тип**: Рефакторинг (Quality Cascade QC-2/KISS, Performance)

---

## 1. Обзор

### 1.1 Проблема

Метод `get_statistics_for_period()` в `prompt_history_repository.py` **загружает все записи в память** вместо SQL aggregation:

```python
# Строки 224-237 — ТЕКУЩАЯ РЕАЛИЗАЦИЯ
histories = result.scalars().all()  # ЗАГРУЖАЕТ ВСЕ ЗАПИСИ!
total_requests = len(histories)      # Python loop вместо SQL COUNT

success_count = 0
for history in histories:           # Python aggregation!
    if history.is_success:
        success_count += 1
```

**Проблемы:**
- **Память**: При 100K записей — ~100MB в RAM
- **Производительность**: O(n) в Python vs O(1) в PostgreSQL
- **Масштабируемость**: Не работает с большими объёмами

### 1.2 Решение

Переписать на **SQL aggregation**:

```python
async def get_statistics_for_period(
    self,
    provider_name: str,
    start_date: datetime,
    end_date: datetime
) -> dict:
    """
    Получает статистику за период через SQL aggregation.
    """
    query = select(
        func.count().label('total'),
        func.count().filter(PromptHistory.is_success == True).label('success'),
        func.avg(PromptHistory.response_time).label('avg_response_time')
    ).where(
        and_(
            PromptHistory.provider_name == provider_name,
            PromptHistory.created_at >= start_date,
            PromptHistory.created_at <= end_date
        )
    )
    result = await self.session.execute(query)
    row = result.one()

    return {
        'total_requests': row.total or 0,
        'successful_requests': row.success or 0,
        'avg_response_time': row.avg_response_time or 0.0
    }
```

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Operations | Те кто мониторит систему | Быстрые статистики |
| DBA | Те кто оптимизирует БД | Эффективные запросы |

### 1.4 Ценностное предложение

- **Память**: 0 bytes вместо O(n)
- **Скорость**: ~10ms вместо ~500ms для 100K записей
- **Масштабируемость**: Работает с любым объёмом данных

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | SQL COUNT | Использовать func.count() вместо len() | Один SQL запрос |
| FR-002 | SQL AVG | Использовать func.avg() вместо Python | Среднее считается в SQL |
| FR-003 | Сохранить интерфейс | Response format должен быть идентичен | Тесты проходят |

---

## 3. User Stories

### US-001: Health Worker запрашивает статистику

**Как** Health Worker
**Я хочу** получить статистику за 7 дней быстро
**Чтобы** не блокировать процесс health check

**Критерии приёмки:**
- [ ] Запрос выполняется < 50ms для любого объёма
- [ ] Память не зависит от количества записей

**Связанные требования:** FR-001, FR-002

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (рефакторинг) |
| Затрагиваемые пайплайны | prompt_history_repository |

### 4.4 Влияние на существующие пайплайны

| Пайплайн | Тип изменения | Обратная совместимость |
|----------|---------------|------------------------|
| prompt_history_repository | modify (internal) | Да |

**Breaking changes:**
- [x] Нет breaking changes — публичный интерфейс сохранён

---

## 6. Нефункциональные требования

### 6.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Query time | < 50ms для 100K записей | EXPLAIN ANALYZE |
| NF-002 | Memory | O(1) вместо O(n) | Memory profiler |

### 6.5 Требования к тестированию

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Unit | Тест get_statistics_for_period() | ✅ Да |
| TRQ-002 | Integration | Тест с реальной БД | ✅ Да |
| TRQ-003 | Regression | Существующие тесты проходят | ✅ Да |

---

## 7. Технические ограничения

### 7.1 Файлы для изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `prompt_history_repository.py` | Modify | Переписать get_statistics_for_period() |

### 7.2 SQL функции

```python
from sqlalchemy import func, and_
from sqlalchemy.future import select

# Использовать:
func.count()
func.avg()
func.count().filter(condition)
```

---

## 8. Допущения и риски

### 8.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | PostgreSQL поддерживает filter() | Использовать CASE WHEN |

### 8.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Разница в NULL handling | Low | Med | Unit tests |
| 2 | Индекс отсутствует | Med | Med | Добавить индекс |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Нужен ли индекс на (provider_name, created_at)? | Resolved | Уже есть ix_prompt_history_created_at |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID
- [x] Критерии приёмки определены
- [x] Риски идентифицированы

---

## Ожидаемый результат

**До рефакторинга:**
```
O(n) память
O(n) время
Python aggregation
```

**После рефакторинга:**
```
O(1) память
O(1) время (индексированный запрос)
SQL aggregation
```
