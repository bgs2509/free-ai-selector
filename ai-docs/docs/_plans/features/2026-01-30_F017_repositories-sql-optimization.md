---
feature_id: "F017"
feature_name: "repositories-sql-optimization"
title: "Data API Repositories: SQL Aggregation Optimization"
created: "2026-01-30"
author: "AI (Architect)"
type: "implementation_plan"
status: "DRAFT"
version: 1
mode: "FEATURE"

related_features: [F010]
services: [free-ai-selector-data-postgres-api]
---

# Implementation Plan: Repositories SQL Aggregation Optimization

**Feature ID**: F017
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Архитектор)
**Статус**: DRAFT (ожидает утверждения)
**Тип**: Рефакторинг (Performance Optimization)

---

## 1. Обзор

### 1.1 Цель изменений

Оптимизировать метод `get_statistics_for_period()` в `PromptHistoryRepository` через замену Python aggregation на SQL aggregation для достижения:
- **Производительность**: 50-100x ускорение для больших объёмов данных
- **Память**: O(n) → O(1) memory usage
- **Масштабируемость**: Поддержка любых объёмов данных

### 1.2 Связь с существующим функционалом

**Связанная фича**: F010 (Rolling Window Reliability)

F010 добавила метод `get_recent_stats_for_all_models()` (строки 155-202), который **уже использует SQL aggregation** и служит **reference implementation** для F017.

**Консистентность паттернов**:
- F010: SQL aggregation для статистики по всем моделям (с GROUP BY)
- F017: SQL aggregation для статистики за период (без GROUP BY)

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Изменения | Тип |
|--------|-----------|-----|
| `free-ai-selector-data-postgres-api` | Оптимизация repository метода | Internal refactoring |

### 2.2 Целевой файл

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/repositories/prompt_history_repository.py`

**Метод**: `get_statistics_for_period()` (строки 204-244)

**Текущая реализация** (проблемная):
```python
async def get_statistics_for_period(
    self, start_date: datetime, end_date: datetime, model_id: Optional[int] = None
) -> dict:
    query = select(PromptHistoryORM).where(
        PromptHistoryORM.created_at >= start_date, PromptHistoryORM.created_at <= end_date
    )

    if model_id is not None:
        query = query.where(PromptHistoryORM.selected_model_id == model_id)

    result = await self.session.execute(query)
    histories = result.scalars().all()  # ❌ Загружает ВСЕ записи в память

    total_requests = len(histories)  # ❌ Python len()
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

### 2.3 Reference Implementation

**Метод**: `get_recent_stats_for_all_models()` (строки 155-202)

**Уже использует SQL aggregation**:
```python
async def get_recent_stats_for_all_models(
    self, window_days: int = 7
) -> Dict[int, Dict[str, Any]]:
    cutoff_date = datetime.utcnow() - timedelta(days=window_days)

    query = (
        select(
            PromptHistoryORM.selected_model_id,
            func.count().label("request_count"),
            func.sum(
                case((PromptHistoryORM.success == True, 1), else_=0)
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

**Ключевые паттерны**:
- ✅ `func.count()` для подсчёта
- ✅ `func.sum(case(...))` для условного подсчёта
- ✅ Возвращает только агрегированные данные (не загружает записи)

### 2.4 Точки интеграции

| Компонент | Интеграция | Влияние |
|-----------|------------|---------|
| API Endpoints | Может вызывать через API route | Нет (внутреннее изменение) |
| Tests | Существующие тесты (если есть) | Нужны regression tests |
| Data API Client | Business API может использовать | Нет (response format сохранён) |

### 2.5 Существующие зависимости

**Все необходимые импорты уже присутствуют** (строки 1-15):

```python
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PromptHistory
from app.infrastructure.database.models import PromptHistoryORM
```

**Вывод**: Новые импорты НЕ требуются.

---

## 3. План изменений

### 3.1 Новые компоненты

**Нет новых компонентов** — только оптимизация существующего метода.

### 3.2 Модификации существующего кода

| # | Файл | Строки | Изменение | Причина |
|---|------|--------|-----------|---------|
| 1 | `prompt_history_repository.py` | 204-244 | Переписать `get_statistics_for_period()` | Заменить Python aggregation на SQL aggregation |

**Детальный план изменения**:

#### До (строки 224-237):
```python
result = await self.session.execute(query)
histories = result.scalars().all()  # Загружает все записи

total_requests = len(histories)
successful_requests = sum(1 for h in histories if h.success)
failed_requests = total_requests - successful_requests
success_rate = successful_requests / total_requests if total_requests > 0 else 0.0
```

#### После:
```python
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
```

**Изменённые строки**: ~15
**LOC change**: -3 (упрощение кода)

### 3.3 Новые зависимости

**Нет новых зависимостей** — все необходимые функции уже импортированы.

---

## 4. API контракты

### 4.1 Response Format

**ВАЖНО**: Response format остаётся **идентичным** для обратной совместимости.

**До и После**:
```python
{
    "total_requests": int,
    "successful_requests": int,
    "failed_requests": int,
    "success_rate": float
}
```

### 4.2 Breaking Changes

**НЕТ breaking changes**:
- ✅ Сигнатура метода не изменена
- ✅ Response format идентичен
- ✅ Параметры не изменены
- ✅ Публичный API repository не затронут

---

## 5. План интеграции

### 5.1 Шаги реализации

| # | Шаг | Файл | Зависимости |
|---|-----|------|-------------|
| 1 | Модифицировать метод `get_statistics_for_period()` | `prompt_history_repository.py` | — |
| 2 | Создать unit tests | `tests/unit/test_prompt_history_repository.py` | Шаг 1 |
| 3 | Запустить regression tests | — | Шаг 2 |
| 4 | Проверить EXPLAIN ANALYZE | SQL query | Шаг 1 |

### 5.2 Детальный план по шагам

#### Шаг 1: Модификация метода

**Действие**: Заменить строки 224-237 на SQL aggregation

**Псевдокод**:
```python
def refactor_get_statistics_for_period():
    # 1. Заменить select(PromptHistoryORM) на select(func.count(), func.sum())
    # 2. Использовать case() для условного подсчёта success
    # 3. Заменить result.scalars().all() на result.one()
    # 4. Использовать row.total и row.success
    # 5. Сохранить NULL handling (or 0)
```

**Ожидаемый результат**: Метод выполняет SQL aggregation вместо Python loops

#### Шаг 2: Unit Tests

**Создать файл**: `tests/unit/test_prompt_history_repository.py`

**Тесты**:
1. `test_get_statistics_empty_period` — пустой период, total=0
2. `test_get_statistics_all_success` — все успешные, success_rate=1.0
3. `test_get_statistics_all_failed` — все неудачные, success_rate=0.0
4. `test_get_statistics_mixed` — смешанные результаты
5. `test_get_statistics_with_model_id` — фильтр по model_id
6. `test_get_statistics_without_model_id` — без фильтра

**Паттерн** (как в `test_ai_model_repository.py`):
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.prompt_history_repository import PromptHistoryRepository

@pytest.mark.unit
class TestPromptHistoryRepository:
    async def test_get_statistics_for_period(self, test_db: AsyncSession):
        # Arrange: создать тестовые записи
        # Act: вызвать get_statistics_for_period()
        # Assert: проверить результат
```

#### Шаг 3: Regression Tests

**Действие**: Запустить все существующие тесты для Data API

**Команда**:
```bash
docker compose exec free-ai-selector-data-postgres-api pytest tests/unit/ -v
```

**Ожидаемый результат**: Все существующие тесты проходят (0 regressions)

#### Шаг 4: Performance Verification

**Действие**: Проверить использование индекса через EXPLAIN ANALYZE

**SQL запрос**:
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
- Aggregate cost < 1000 для 100K записей

**С фильтром по model_id**:
```sql
EXPLAIN ANALYZE
SELECT
    count(*) AS total,
    sum(CASE WHEN success = true THEN 1 ELSE 0 END) AS success
FROM prompt_history
WHERE created_at >= '2026-01-01' AND created_at <= '2026-01-30'
  AND selected_model_id = 1;
```

**Ожидаемый план**:
- Index Scan на `ix_prompt_history_created_at` или `ix_prompt_history_selected_model_id`
- Aggregate cost < 500

### 5.3 Rollback Plan

**Если что-то пойдёт не так**:

1. **Git revert**: Откатить commit с изменениями
2. **Проверить тесты**: Убедиться что старая версия работает
3. **Исследовать проблему**: Проверить логи, EXPLAIN ANALYZE

**Условия rollback**:
- Regression tests не проходят
- Performance ухудшилась (невероятно, но возможно)
- NULL handling работает неправильно

---

## 6. Влияние на существующие тесты

### 6.1 Существующие тесты

**Статус**: НЕ НАЙДЕНЫ тесты для `PromptHistoryRepository`

**Файлы**:
- ❌ `tests/unit/test_prompt_history_repository.py` — не существует
- ✅ `tests/unit/test_ai_model_repository.py` — существует (паттерн для создания)

### 6.2 Необходимые тесты

| Тест | Описание | Критерий приёмки |
|------|----------|------------------|
| `test_get_statistics_empty` | Пустой период | `total=0, success_rate=0.0` |
| `test_get_statistics_all_success` | Все успешные | `success_rate=1.0` |
| `test_get_statistics_all_failed` | Все неудачные | `success_rate=0.0` |
| `test_get_statistics_mixed` | 60% успешных | `success_rate=0.6` |
| `test_get_statistics_with_model_id` | Фильтр работает | Только записи model_id |
| `test_get_statistics_without_model_id` | Без фильтра | Все записи |

### 6.3 Покрытие кода

**Цель**: ≥75% coverage (как в других сервисах)

**Метрика**:
```bash
docker compose exec free-ai-selector-data-postgres-api \
  pytest tests/unit/test_prompt_history_repository.py --cov=app/infrastructure/repositories/prompt_history_repository --cov-report=term
```

**Ожидаемое покрытие**: 80-90% (после добавления 6 тестов для метода)

---

## 7. Риски и митигация

### 7.1 Технические риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | NULL handling отличается (Python vs SQL) | Low | Med | Unit tests с пустым периодом, проверка `row.total or 0` |
| 2 | Индекс не используется (performance regression) | Low | High | EXPLAIN ANALYZE перед merge |
| 3 | Существующий код использует метод и ломается | Med | High | Regression tests, идентичный response format |
| 4 | `func.sum(case())` возвращает NULL вместо 0 | Med | Med | Использовать `or 0` при присваивании |

### 7.2 Операционные риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Deployment во время активной нагрузки | Low | Low | Deploy в off-peak hours |
| 2 | PostgreSQL версия не поддерживает `FILTER` | Very Low | Med | Использовать `func.sum(case())` вместо `filter()` |

### 7.3 План митигации

**Pre-deployment**:
1. ✅ Unit tests покрывают все edge cases
2. ✅ Regression tests проходят
3. ✅ EXPLAIN ANALYZE показывает использование индекса
4. ✅ Code review подтверждает корректность

**Post-deployment**:
1. Мониторинг performance метрик
2. Проверка логов на наличие ошибок
3. Rollback план готов (git revert)

---

## 8. DB Migrations

**Миграции БД**: НЕ ТРЕБУЮТСЯ

**Причина**: Используются существующие индексы:
- ✅ `ix_prompt_history_created_at` (создан в миграции `0001_initial_schema.py`)
- ✅ `ix_prompt_history_selected_model_id` (создан в миграции `0001_initial_schema.py`)

**Опциональная оптимизация (будущее)**:

Composite index для улучшения performance при фильтрации по `model_id` + `created_at`:

```python
# В будущей миграции (НЕ для F017)
op.create_index(
    "ix_prompt_history_model_created",
    "prompt_history",
    ["selected_model_id", "created_at"]
)
```

**Статус**: Опциональная оптимизация, НЕ блокер для F017

---

## 9. Checklist Implementation

### 9.1 Pre-Implementation

- [x] PRD утверждён
- [x] Research завершён
- [x] Plan создан
- [ ] **Plan утверждён пользователем** ← ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ

### 9.2 Implementation Phase

- [ ] Метод `get_statistics_for_period()` модифицирован
- [ ] Unit tests созданы (6 тестов)
- [ ] Regression tests проходят
- [ ] EXPLAIN ANALYZE проверен
- [ ] Code coverage ≥75%

### 9.3 Validation Phase

- [ ] Code review пройден
- [ ] QA tests пройдены
- [ ] Performance benchmarks удовлетворительны
- [ ] Документация обновлена (если требуется)

---

## 10. Метрики успеха

### 10.1 Performance Metrics

| Метрика | До | После (ожидаемое) | Измерение |
|---------|----|--------------------|-----------|
| Query time (100K записей) | ~500ms | ~10ms | EXPLAIN ANALYZE |
| Memory usage | O(n) ~100MB | O(1) ~1KB | Memory profiler |
| CPU usage | O(n) Python loop | O(1) SQL aggregate | Query plan |

### 10.2 Quality Metrics

| Метрика | Требование | Измерение |
|---------|------------|-----------|
| Test coverage | ≥75% | pytest --cov |
| Regression tests | 0 failures | pytest tests/unit/ |
| Code review | Approved | GitHub PR review |

### 10.3 Acceptance Criteria

| # | Критерий | Статус |
|---|----------|--------|
| 1 | SQL aggregation вместо Python loops | 🔵 Plan |
| 2 | Response format идентичен существующему | 🔵 Plan |
| 3 | Unit tests покрывают edge cases | 🔵 Plan |
| 4 | Regression tests проходят | 🔵 Plan |
| 5 | Performance улучшена ≥10x | 🔵 Plan |
| 6 | EXPLAIN ANALYZE показывает Index Scan | 🔵 Plan |

---

## 11. Timeline и Effort

### 11.1 Оценка трудозатрат

| Этап | Задачи | Время | Зависимости |
|------|--------|-------|-------------|
| **Implementation** | Модификация метода | 30 min | — |
| **Testing** | Создание 6 unit tests | 1 hour | Implementation |
| **Validation** | EXPLAIN ANALYZE, regression tests | 30 min | Testing |
| **Code Review** | Review и fixes | 30 min | Validation |
| **TOTAL** | | **2.5 hours** | |

### 11.2 Критический путь

```
PRD_READY → RESEARCH_DONE → PLAN_APPROVED → Implementation (30m) → Testing (1h) → Validation (30m) → Review (30m) → DEPLOYED
```

**Total pipeline duration**: ~2.5 hours (при последовательном выполнении)

---

## 12. Зависимости от других фич

### 12.1 Блокирует

**Нет** — F017 не блокирует другие фичи

### 12.2 Блокируется

**Нет** — F017 не блокируется другими фичами

### 12.3 Связанные фичи

| Фича | Связь | Влияние |
|------|-------|---------|
| F010 | Использует тот же паттерн SQL aggregation | Reference implementation |
| F015 | DRY refactoring в том же сервисе | Консистентность кода |
| F016 | SSOT для reliability_score | Консистентность паттернов |

---

## 13. Quality Cascade

### 13.1 Применённые принципы

| Принцип | Применение | Обоснование |
|---------|------------|-------------|
| **QC-1: DRY** | Использование паттерна из F010 | Консистентность, переиспользование решения |
| **QC-2: KISS** | Простое решение: func.count() вместо Python loops | Меньше кода, понятнее логика |
| **QC-10: SSoT** | SQL как единственный источник агрегации | Устранение дублирования (SQL vs Python) |
| **Performance** | SQL aggregation вместо загрузки всех записей | O(n) → O(1) память, 50-100x скорость |

### 13.2 Quality Gates

| Ворота | Критерий | Статус |
|--------|----------|--------|
| PRD_READY | Требования определены | ✅ Passed |
| RESEARCH_DONE | Код проанализирован | ✅ Passed |
| PLAN_APPROVED | План утверждён | 🔵 Pending |
| IMPLEMENT_OK | Код написан, тесты проходят | 🔵 Pending |
| REVIEW_OK | Code review пройден | 🔵 Pending |
| QA_PASSED | QA тесты пройдены | 🔵 Pending |

---

## 14. Заключение

### 14.1 Summary

Рефакторинг метода `get_statistics_for_period()` для замены Python aggregation на SQL aggregation — **низкорисковое изменение** с **высоким impact** на производительность.

**Ключевые преимущества**:
- ✅ 50-100x ускорение для больших объёмов
- ✅ O(n) → O(1) memory optimization
- ✅ Консистентность с F010 (тот же паттерн)
- ✅ Нет breaking changes
- ✅ Простая реализация (reference implementation уже есть)

**Минимальные риски**:
- ✅ Все импорты уже есть
- ✅ Индексы существуют
- ✅ Response format сохранён
- ✅ Unit tests покроют edge cases

### 14.2 Next Steps

1. **Ожидание утверждения плана** пользователем
2. После утверждения: `/aidd-code` для реализации
3. После реализации: `/aidd-validate` для review + QA + deployment

---

## Чеклист ворот PLAN_APPROVED

> ⚠️ **ВАЖНО**: Требуется явное утверждение пользователя перед переходом к реализации.

- [x] 🔴 Feature Plan создан в правильной папке: `_plans/features/2026-01-30_F017_repositories-sql-optimization.md`
- [x] 🔴 Интеграция с существующим кодом описана (reference implementation из F010)
- [ ] 🔴 **Пользователь утвердил план** ← КРИТИЧЕСКИ ВАЖНО
- [ ] 🔴 `.pipeline-state.json` обновлён (gate: PLAN_APPROVED)
- [x] 🟡 Breaking changes определены (нет breaking changes)
- [x] 🟡 Миграции БД описаны (не требуются)

---

**Статус**: 🔵 DRAFT — Ожидает утверждения пользователя
**Готов к**: Утверждению и переходу на `/aidd-code`
