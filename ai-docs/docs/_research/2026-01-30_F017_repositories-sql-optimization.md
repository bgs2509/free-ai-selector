---
feature_id: "F017"
feature_name: "repositories-sql-optimization"
title: "Data API Repositories: SQL Aggregation Optimization"
created: "2026-01-30"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"

related_features: [F010]
services: [free-ai-selector-data-postgres-api]
---

# Research: Repositories SQL Aggregation Optimization

**Feature ID**: F017
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Исследователь)
**Статус**: RESEARCH_DONE
**Тип**: Рефакторинг (Performance Optimization)

---

## 1. Цели исследования

Проанализировать текущую реализацию `get_statistics_for_period()` в `PromptHistoryRepository` и определить оптимальный подход для замены Python aggregation на SQL aggregation.

---

## 2. Текущее состояние кода

### 2.1 Целевой метод

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/repositories/prompt_history_repository.py`

**Строки**: 204-244

**Текущая реализация**:

```python
async def get_statistics_for_period(
    self, start_date: datetime, end_date: datetime, model_id: Optional[int] = None
) -> dict:
    """
    Get statistics for a specific time period.

    Args:
        start_date: Start of period
        end_date: End of period
        model_id: Optional filter by model ID

    Returns:
        Dictionary with statistics:
        {
            "total_requests": int,
            "successful_requests": int,
            "failed_requests": int,
            "success_rate": float
        }
    """
    query = select(PromptHistoryORM).where(
        PromptHistoryORM.created_at >= start_date, PromptHistoryORM.created_at <= end_date
    )

    if model_id is not None:
        query = query.where(PromptHistoryORM.selected_model_id == model_id)

    result = await self.session.execute(query)
    histories = result.scalars().all()  # ❌ ЗАГРУЖАЕТ ВСЕ ЗАПИСИ В ПАМЯТЬ!

    total_requests = len(histories)  # ❌ Python len() вместо SQL COUNT
    successful_requests = sum(1 for h in histories if h.success)  # ❌ Python loop
    failed_requests = total_requests - successful_requests
    success_rate = successful_requests / total_requests if total_requests > 0 else 0.0

    return {
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "success_rate": success_rate,
    }
```

### 2.2 Проблемы

| Проблема | Текущее состояние | Влияние |
|----------|-------------------|---------|
| **Память** | `histories = result.scalars().all()` загружает ВСЕ записи | O(n) память, ~100MB для 100K записей |
| **CPU** | Python aggregation: `len()`, `sum()`, list comprehension | O(n) время, медленно для больших объёмов |
| **Масштабируемость** | Чем больше данных, тем медленнее | Не работает с миллионами записей |
| **Эффективность** | Не использует PostgreSQL оптимизацию | DB может агрегировать намного быстрее |

### 2.3 Замеры производительности (оценка)

| Объём данных | Память (Python) | Время (Python) | Память (SQL) | Время (SQL) |
|--------------|-----------------|----------------|--------------|-------------|
| 1K записей | ~1 MB | ~10 ms | ~0 bytes | ~2 ms |
| 10K записей | ~10 MB | ~50 ms | ~0 bytes | ~5 ms |
| 100K записей | ~100 MB | ~500 ms | ~0 bytes | ~10 ms |
| 1M записей | ~1 GB | ~5000 ms | ~0 bytes | ~50 ms |

**Вывод**: SQL aggregation быстрее в ~50-100 раз для больших объёмов.

---

## 3. Архитектурные паттерны проекта

### 3.1 SQLAlchemy 2.0 Async Pattern

Проект использует SQLAlchemy 2.0 async API:

```python
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
```

### 3.2 Существующий пример SQL aggregation

В **том же файле** есть метод `get_recent_stats_for_all_models()` (строки 155-202), который **УЖЕ ИСПОЛЬЗУЕТ SQL aggregation**:

```python
async def get_recent_stats_for_all_models(
    self, window_days: int = 7
) -> Dict[int, Dict[str, Any]]:
    """
    Get aggregated statistics for all models within a time window.

    Uses SQL GROUP BY for efficient aggregation instead of loading all records.
    Leverages existing index ix_prompt_history_created_at.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=window_days)

    query = (
        select(
            PromptHistoryORM.selected_model_id,
            func.count().label("request_count"),
            func.sum(
                case((PromptHistoryORM.success == True, 1), else_=0)  # noqa: E712
            ).label("success_count"),
            func.avg(PromptHistoryORM.response_time).label("avg_response_time"),
        )
        .where(PromptHistoryORM.created_at > cutoff_date)
        .group_by(PromptHistoryORM.selected_model_id)
    )

    result = await self.session.execute(query)
    rows = result.all()

    return {
        row.selected_model_id: {
            "request_count": row.request_count,
            "success_count": row.success_count,
            "avg_response_time": float(row.avg_response_time or 0.0),
        }
        for row in rows
    }
```

**Ключевые особенности:**
- Использует `func.count()`, `func.sum()`, `func.avg()`
- Использует `case()` для условного счёта (success_count)
- Использует `group_by()` для группировки
- **Не загружает записи в память** — возвращает только агрегированные данные

### 3.3 Паттерн для применения

Для `get_statistics_for_period()` нужен **похожий паттерн**, но **БЕЗ GROUP BY** (агрегация по всем записям):

```python
query = (
    select(
        func.count().label("total"),
        func.sum(case((PromptHistoryORM.success == True, 1), else_=0)).label("success"),
    )
    .where(
        PromptHistoryORM.created_at >= start_date,
        PromptHistoryORM.created_at <= end_date
    )
)
```

---

## 4. Анализ индексов БД

### 4.1 Существующие индексы на `prompt_history`

Из миграции `20250117_0001_initial_schema.py` (строки 70-78):

```python
# Create indexes on prompt_history
op.create_index(op.f("ix_prompt_history_user_id"), "prompt_history", ["user_id"], unique=False)
op.create_index(
    op.f("ix_prompt_history_selected_model_id"), "prompt_history", ["selected_model_id"], unique=False
)
op.create_index(op.f("ix_prompt_history_success"), "prompt_history", ["success"], unique=False)
op.create_index(
    op.f("ix_prompt_history_created_at"), "prompt_history", ["created_at"], unique=False
)
```

### 4.2 Индексы для оптимизации

| Индекс | Использование в query | Эффективность |
|--------|----------------------|---------------|
| `ix_prompt_history_created_at` | `WHERE created_at >= ? AND created_at <= ?` | ✅ Высокая |
| `ix_prompt_history_selected_model_id` | `WHERE selected_model_id = ?` (optional) | ✅ Высокая |
| `ix_prompt_history_success` | Фильтр в `func.sum(case(...))` | ⚠️ Не используется напрямую |

### 4.3 Composite Index (оптимально)

Для максимальной производительности при фильтрации по `model_id` + `created_at` можно добавить **composite index**:

```python
# В будущей миграции (опционально)
op.create_index(
    "ix_prompt_history_model_created",
    "prompt_history",
    ["selected_model_id", "created_at"]
)
```

**Но**: Существующие индексы достаточны для F017. Composite index — опциональная оптимизация для будущего.

---

## 5. SQLAlchemy функции для aggregation

### 5.1 Доступные функции

| Функция | Использование | Пример |
|---------|---------------|--------|
| `func.count()` | Подсчёт строк | `func.count()` |
| `func.count(column)` | Подсчёт NOT NULL | `func.count(PromptHistoryORM.id)` |
| `func.sum(expression)` | Сумма значений | `func.sum(case(...))` |
| `func.avg(column)` | Среднее значение | `func.avg(PromptHistoryORM.response_time)` |
| `case()` | Условное выражение | `case((condition, 1), else_=0)` |

### 5.2 Паттерн для `success_count`

**Два подхода:**

**Подход 1: func.sum(case())**
```python
func.sum(case((PromptHistoryORM.success == True, 1), else_=0)).label("success")
```

**Подход 2: func.count().filter()**
```python
func.count().filter(PromptHistoryORM.success == True).label("success")
```

**Оба подхода работают**, но `filter()` более читаемо. Однако в проекте уже используется `func.sum(case())` (см. `get_recent_stats_for_all_models`), поэтому для **консистентности** рекомендую **Подход 1**.

---

## 6. Модель данных PromptHistoryORM

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/models.py`

**Строки**: 75-106

### 6.1 Релевантные поля

| Поле | Тип | Использование |
|------|-----|---------------|
| `id` | Integer, PK | Уникальный ID |
| `user_id` | String(255), indexed | Фильтр по user (не используется в F017) |
| `selected_model_id` | Integer, indexed | Фильтр по model (optional в F017) |
| `success` | Boolean, indexed | Условие для success_count |
| `created_at` | DateTime(tz), indexed | Фильтр по периоду |

### 6.2 Nullable поля

**Важно для aggregation:**
- `response_text`: Optional[str] — может быть NULL
- `error_message`: Optional[str] — может быть NULL
- `response_time`: Decimal — NOT NULL (всегда имеет значение)

---

## 7. Тестирование

### 7.1 Существующие тесты

**Найденные тесты**:
- `tests/unit/test_ai_model_repository.py` — есть юнит-тесты для AIModel repository
- **НЕ НАЙДЕНЫ** тесты для `PromptHistoryRepository`

### 7.2 Требуемые тесты для F017

| Тест | Описание | Критерий приёмки |
|------|----------|------------------|
| `test_get_statistics_empty` | Пустой период | `total_requests=0, success_rate=0.0` |
| `test_get_statistics_all_success` | Все успешные | `success_rate=1.0` |
| `test_get_statistics_mixed` | Смешанные | Корректные count и rate |
| `test_get_statistics_with_model_id` | Фильтр по model_id | Только записи для model_id |
| `test_get_statistics_performance` | 1000 записей | Выполняется < 50ms |

### 7.3 Паттерн тестов

Использовать `pytest.mark.unit` и `test_db` fixture (как в `test_ai_model_repository.py`):

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.prompt_history_repository import PromptHistoryRepository

@pytest.mark.unit
class TestPromptHistoryRepository:
    async def test_get_statistics_for_period(self, test_db: AsyncSession):
        # ...
```

---

## 8. Оптимизированное решение

### 8.1 Предлагаемая реализация

```python
async def get_statistics_for_period(
    self, start_date: datetime, end_date: datetime, model_id: Optional[int] = None
) -> dict:
    """
    Get statistics for a specific time period using SQL aggregation.

    Args:
        start_date: Start of period
        end_date: End of period
        model_id: Optional filter by model ID

    Returns:
        Dictionary with statistics:
        {
            "total_requests": int,
            "successful_requests": int,
            "failed_requests": int,
            "success_rate": float
        }
    """
    # Используем SQL aggregation вместо загрузки всех записей
    query = select(
        func.count().label("total"),
        func.sum(
            case((PromptHistoryORM.success == True, 1), else_=0)
        ).label("success")
    ).where(
        PromptHistoryORM.created_at >= start_date,
        PromptHistoryORM.created_at <= end_date
    )

    if model_id is not None:
        query = query.where(PromptHistoryORM.selected_model_id == model_id)

    result = await self.session.execute(query)
    row = result.one()

    total_requests = row.total or 0
    successful_requests = row.success or 0
    failed_requests = total_requests - successful_requests
    success_rate = successful_requests / total_requests if total_requests > 0 else 0.0

    return {
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "success_rate": success_rate,
    }
```

### 8.2 Ключевые изменения

| До | После | Выигрыш |
|----|----|---------|
| `result.scalars().all()` | `result.one()` | Память: O(n) → O(1) |
| `len(histories)` | `func.count()` | CPU: Python → SQL |
| `sum(1 for h in histories if h.success)` | `func.sum(case(...))` | CPU: Python loop → SQL |
| ~500ms для 100K записей | ~10ms для 100K записей | Скорость: **50x** |

### 8.3 Обратная совместимость

**Response format**: Идентичен существующему

```python
# До и После — одинаковый формат
{
    "total_requests": int,
    "successful_requests": int,
    "failed_requests": int,
    "success_rate": float
}
```

**Breaking changes**: НЕТ

---

## 9. Зависимости и импорты

### 9.1 Существующие импорты (строки 1-15)

```python
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PromptHistory
from app.infrastructure.database.models import PromptHistoryORM
```

### 9.2 Требуемые для F017

| Импорт | Статус | Описание |
|--------|--------|----------|
| `func` | ✅ УЖЕ ЕСТЬ | Для func.count(), func.sum() |
| `case` | ✅ УЖЕ ЕСТЬ | Для условного подсчёта |
| `select` | ✅ УЖЕ ЕСТЬ | Для SELECT запроса |

**Вывод**: Все необходимые импорты уже присутствуют. Изменения НЕ требуются.

---

## 10. Технические ограничения

### 10.1 PostgreSQL версия

**Требуется**: PostgreSQL 9.4+ (для поддержки `FILTER`)

**Текущая версия проекта**: PostgreSQL 16 (из `docker-compose.yml`)

**Статус**: ✅ Поддерживается

### 10.2 SQLAlchemy версия

**Требуется**: SQLAlchemy 2.0+ (для async API и `case()`)

**Текущая версия проекта**: SQLAlchemy 2.0 (из imports)

**Статус**: ✅ Поддерживается

### 10.3 NULL handling

**Проблема**: `func.sum(case(...))` может вернуть NULL если нет записей

**Решение**: Использовать `or 0` при присваивании:

```python
total_requests = row.total or 0
successful_requests = row.success or 0
```

---

## 11. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Разница в NULL handling между Python и SQL | Low | Med | Unit tests с пустым периодом |
| 2 | Индекс `ix_prompt_history_created_at` не используется | Low | High | Проверить EXPLAIN ANALYZE |
| 3 | Регрессия: существующий код использует этот метод | Med | High | Regression tests, идентичный response format |

---

## 12. План тестирования производительности

### 12.1 Benchmark сценарии

| Сценарий | Объём данных | Ожидаемое время (SQL) |
|----------|--------------|----------------------|
| Пустой период | 0 записей | < 5ms |
| Малый объём | 100 записей | < 10ms |
| Средний объём | 10K записей | < 20ms |
| Большой объём | 100K записей | < 50ms |

### 12.2 SQL EXPLAIN ANALYZE

```sql
EXPLAIN ANALYZE
SELECT
    count(*) AS total,
    sum(CASE WHEN success = true THEN 1 ELSE 0 END) AS success
FROM prompt_history
WHERE created_at >= '2026-01-01' AND created_at <= '2026-01-30';
```

**Ожидаемый план**:
- Index Scan на `ix_prompt_history_created_at`
- Aggregate cost < 1000

---

## 13. Примеры использования метода

### 13.1 Поиск вызовов в коде

```bash
cd services/free-ai-selector-data-postgres-api
grep -r "get_statistics_for_period" --include="*.py"
```

**Результат**: Метод НЕ используется в текущем коде (новый метод из F010?)

### 13.2 Потенциальные вызывающие

- Data API endpoints: `/statistics` (если есть)
- Health Worker: для мониторинга (если планируется)
- Analytics: для отчётов (будущее использование)

**Вывод**: Метод может быть **неиспользуемым** или использоваться через Data API. Требуется проверка endpoints.

---

## 14. Связь с другими фичами

### 14.1 F010: Rolling Window Reliability

**Связь**: F010 добавила метод `get_recent_stats_for_all_models()` который **УЖЕ ИСПОЛЬЗУЕТ SQL aggregation**.

**Паттерн F010** (строки 155-202) — это **reference implementation** для F017.

### 14.2 Консистентность с F010

| Аспект | F010 | F017 (предлагаемое) |
|--------|------|---------------------|
| SQL aggregation | ✅ func.count(), func.sum() | ✅ func.count(), func.sum() |
| `case()` для success | ✅ Использует | ✅ Использует |
| Память | O(1) | O(1) |
| GROUP BY | ✅ По model_id | ❌ Не требуется |

**Вывод**: F017 применяет тот же паттерн, что и F010, обеспечивая консистентность.

---

## 15. Выводы и рекомендации

### 15.1 Ключевые находки

1. **Существующий паттерн**: Метод `get_recent_stats_for_all_models()` уже демонстрирует правильный подход SQL aggregation
2. **Индексы**: Все необходимые индексы существуют (`ix_prompt_history_created_at`, `ix_prompt_history_selected_model_id`)
3. **Импорты**: Все требуемые импорты уже присутствуют
4. **Тесты**: Нет существующих тестов для PromptHistoryRepository — требуется создать
5. **Использование**: Метод может быть неиспользуемым или вызываться через API (требует проверки)

### 15.2 Рекомендации

| # | Рекомендация | Приоритет | Обоснование |
|---|--------------|-----------|-------------|
| 1 | Использовать паттерн из `get_recent_stats_for_all_models()` | ✅ High | Консистентность кода |
| 2 | Использовать `func.sum(case())` вместо `filter()` | ✅ High | Соответствие существующему стилю |
| 3 | Добавить unit tests для PromptHistoryRepository | ✅ High | Покрытие для regression |
| 4 | Проверить EXPLAIN ANALYZE после реализации | ⚠️ Medium | Убедиться в использовании индекса |
| 5 | Composite index (model_id, created_at) | 🔵 Low | Опциональная оптимизация |

### 15.3 Готовность к реализации

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| Паттерн определён | ✅ Да | Reference implementation в F010 |
| Индексы готовы | ✅ Да | `ix_prompt_history_created_at` существует |
| Импорты готовы | ✅ Да | Все импорты присутствуют |
| Тесты готовы | ❌ Нет | Требуется создать test_prompt_history_repository.py |
| Breaking changes | ✅ Нет | Response format идентичен |

**Вывод**: Готово к переходу на этап PLAN.

---

## 16. Следующие шаги

1. **План** (`/aidd-plan-feature`): Детальный план реализации
2. **Код** (`/aidd-code`): Реализация + unit tests
3. **Валидация** (`/aidd-validate`): Code review, QA, deployment

---

## Чеклист ворот RESEARCH_DONE

- [x] 🔴 Research отчёт создан в правильной папке: `_research/2026-01-30_F017_repositories-sql-optimization.md`
- [x] 🔴 Существующий код проанализирован: метод `get_statistics_for_period()` (строки 204-244)
- [x] 🔴 Зависимости определены: func, case, select (уже импортированы)
- [x] 🔴 Паттерн найден: `get_recent_stats_for_all_models()` как reference implementation
- [x] 🔴 Индексы проверены: `ix_prompt_history_created_at` существует
- [x] 🟡 Риски идентифицированы: NULL handling, индекс использование, регрессия
- [x] 🟡 Технические ограничения описаны: PostgreSQL 16, SQLAlchemy 2.0
- [x] 🟡 Производительность оценена: 50-100x ускорение для больших объёмов

---

**Статус**: ✅ RESEARCH_DONE
**Готов к**: `/aidd-plan-feature F017`
