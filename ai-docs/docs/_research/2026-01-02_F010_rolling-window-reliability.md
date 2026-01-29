---
feature_id: "F010"
feature_name: "rolling-window-reliability"
title: "Research: Rolling Window Reliability Score"
created: "2026-01-03"
author: "AI (Researcher)"
type: "_research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"
---

# Research: Rolling Window Reliability Score

**Feature ID**: F010
**Дата**: 2026-01-03
**Автор**: AI Agent (Исследователь)
**Статус**: RESEARCH_DONE

---

## 1. Обзор анализа

### 1.1 Цель исследования

Анализ существующего кода для определения:
- Точек расширения для добавления recent metrics
- Паттернов кодовой базы
- Технических ограничений
- Рекомендаций по реализации

### 1.2 Сервисы для анализа

| Сервис | Роль в F010 |
|--------|-------------|
| `free-ai-selector-data-postgres-api` | Источник данных, расчёт recent stats |
| `free-ai-selector-business-api` | Потребитель данных, выбор модели |

---

## 2. Анализ текущей архитектуры

### 2.1 Существующий механизм выбора модели

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

```python
# Строка 79: Выбор модели
best_model = self._select_best_model(models)

# Строка 202-212: Алгоритм выбора
def _select_best_model(self, models: list[AIModelInfo]) -> AIModelInfo:
    return max(models, key=lambda m: m.reliability_score)
```

**Вывод**: Выбор основан на `reliability_score` из `AIModelInfo`. Для F010 нужно заменить на `effective_reliability_score`.

### 2.2 Источник reliability_score

**Файл**: `services/free-ai-selector-data-postgres-api/app/domain/models.py`

```python
# Строки 69-74: Формула расчёта (кумулятивная)
@property
def reliability_score(self) -> float:
    """Calculate reliability score (0.0 - 1.0)."""
    return (self.success_rate * 0.6) + (self.speed_score * 0.4)
```

**Зависимые метрики** (строки 40-66):
- `success_rate` = `success_count / request_count` (все запросы за всё время)
- `speed_score` = `1.0 - (avg_response_time / 10.0)`

**Вывод**: Все метрики кумулятивные. Нужно добавить параллельные recent_* свойства.

### 2.3 Таблица prompt_history

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/database/models.py`

```python
class PromptHistoryORM(Base):
    __tablename__ = "prompt_history"

    id: Mapped[int]
    user_id: Mapped[str]                    # index=True
    prompt_text: Mapped[str]
    selected_model_id: Mapped[int]          # index=True
    response_text: Mapped[Optional[str]]
    response_time: Mapped[Decimal]
    success: Mapped[bool]                   # index=True
    error_message: Mapped[Optional[str]]
    created_at: Mapped[datetime]            # index=True ✅
```

**Существующие индексы** (из миграции `20250117_0001_initial_schema.py`):
- `ix_prompt_history_created_at` — ✅ Идеально подходит для `WHERE created_at > NOW() - N days`
- `ix_prompt_history_selected_model_id` — для группировки по model_id
- `ix_prompt_history_success` — для фильтрации по успешности

**Вывод**: Все необходимые индексы существуют. Миграция БД не требуется.

### 2.4 Существующий метод get_statistics_for_period

**Файл**: `services/free-ai-selector-data-postgres-api/app/infrastructure/repositories/prompt_history_repository.py`

```python
# Строки 152-192: Существующий метод для периода
async def get_statistics_for_period(
    self, start_date: datetime, end_date: datetime, model_id: Optional[int] = None
) -> dict:
    """Get statistics for a specific time period."""
    query = select(PromptHistoryORM).where(
        PromptHistoryORM.created_at >= start_date,
        PromptHistoryORM.created_at <= end_date
    )

    if model_id is not None:
        query = query.where(PromptHistoryORM.selected_model_id == model_id)

    # ... подсчёт статистики
```

**Проблема**: Метод возвращает статистику для одной модели. Для F010 нужен batch-метод для всех моделей одним запросом.

---

## 3. Выявленные паттерны

### 3.1 Архитектурные паттерны

| Паттерн | Применение | Файлы |
|---------|------------|-------|
| **HTTP-only** | Business → Data API | `data_api_client.py` |
| **Repository** | Data access layer | `ai_model_repository.py`, `prompt_history_repository.py` |
| **Domain Model** | Computed properties | `domain/models.py` |
| **DTO mapping** | API ↔ Domain | `_model_to_response()` в `models.py` (API) |

### 3.2 Паттерн передачи данных

```
Business API                    Data API                      PostgreSQL
     │                              │                             │
     │ GET /api/v1/models          │                             │
     │ ?active_only=true ─────────►│                             │
     │                              │ Repository.get_all()        │
     │                              │────────────────────────────►│
     │                              │◄────────────────────────────│
     │                              │                             │
     │◄───────────────────────────  │                             │
     │ AIModelResponse[]            │                             │
     │ (с вычисленным reliability)  │                             │
```

**Вывод**: Recent metrics должны вычисляться в Data API и передаваться в ответе.

### 3.3 Паттерн вычисляемых полей

**Файл**: `services/free-ai-selector-data-postgres-api/app/api/v1/models.py`

```python
# Строки 264-293: Маппинг domain → response
def _model_to_response(model: AIModel) -> AIModelResponse:
    return AIModelResponse(
        # ... базовые поля ...
        success_rate=model.success_rate,           # вычисляемое
        average_response_time=model.average_response_time,  # вычисляемое
        speed_score=model.speed_score,             # вычисляемое
        reliability_score=model.reliability_score, # вычисляемое
    )
```

**Вывод**: Recent metrics нужно добавить по тому же паттерну.

---

## 4. Точки расширения

### 4.1 Data API — Уровни изменений

| # | Уровень | Файл | Изменения |
|---|---------|------|-----------|
| 1 | Repository | `prompt_history_repository.py` | Новый метод `get_recent_stats_for_all_models(window_days)` |
| 2 | API Schema | `schemas.py` | Новые поля в `AIModelResponse`: `recent_*`, `effective_*` |
| 3 | API Route | `models.py` | Новые query params: `include_recent`, `window_days` |
| 4 | Route Logic | `models.py` | Вызов `get_recent_stats` + расчёт effective score |

### 4.2 Business API — Уровни изменений

| # | Уровень | Файл | Изменения |
|---|---------|------|-----------|
| 1 | Domain Model | `domain/models.py` | Новые поля в `AIModelInfo`: `recent_*`, `effective_*` |
| 2 | HTTP Client | `data_api_client.py` | Парсинг новых полей из ответа |
| 3 | Use Case | `process_prompt.py` | Заменить `reliability_score` на `effective_reliability_score` |
| 4 | Logging | `process_prompt.py` | Добавить `decision_reason: recent_score | fallback` |

### 4.3 Диаграмма изменений

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA API (Новые компоненты)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐     ┌──────────────────────────────────────┐   │
│  │  GET /api/v1/models │     │      prompt_history_repository.py    │   │
│  │  +include_recent    │────►│  +get_recent_stats_for_all_models()  │   │
│  │  +window_days       │     │                                      │   │
│  └──────────┬──────────┘     │  SQL:                                │   │
│             │                │  SELECT model_id,                    │   │
│             │                │         COUNT(*) as request_count,   │   │
│             │                │         SUM(success) as success_count│   │
│             ▼                │         AVG(response_time)           │   │
│  ┌─────────────────────┐     │  FROM prompt_history                 │   │
│  │  AIModelResponse    │     │  WHERE created_at > NOW() - N days   │   │
│  │  +recent_success_rate│    │  GROUP BY model_id                   │   │
│  │  +recent_request_count│   └──────────────────────────────────────┘   │
│  │  +recent_reliability │                                               │
│  │  +effective_score    │                                               │
│  └─────────────────────┘                                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      BUSINESS API (Изменённые компоненты)                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐     ┌──────────────────────────────────────┐   │
│  │   AIModelInfo       │     │       process_prompt.py               │   │
│  │  +recent_reliability │    │                                       │   │
│  │  +effective_score   │────►│  _select_best_model():               │   │
│  │  +recent_request_cnt│     │    max(models, key=effective_score)  │   │
│  └─────────────────────┘     │                                       │   │
│                              │  log_decision():                      │   │
│                              │    decision_reason: recent | fallback │   │
│                              └──────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Технические ограничения

### 5.1 Подтверждённые ограничения

| # | Ограничение | Статус | Комментарий |
|---|-------------|--------|-------------|
| 1 | HTTP-only архитектура | ✅ Совместимо | Изменения в Data API, Business потребляет |
| 2 | Нет миграций БД | ✅ Совместимо | Используем существующую `prompt_history` |
| 3 | Индекс `created_at` | ✅ Существует | `ix_prompt_history_created_at` |
| 4 | Backward compatibility | ✅ Возможно | `include_recent=false` по умолчанию |

### 5.2 Потенциальные ограничения

| # | Ограничение | Вероятность | Митигация |
|---|-------------|-------------|-----------|
| 1 | Производительность SQL | Низкая | Индексы существуют, GROUP BY эффективен |
| 2 | Cold start (мало данных) | Средняя | Fallback на long-term score |
| 3 | Объём данных за 7 дней | Низкая | Агрегация в SQL, не загрузка всех записей |

---

## 6. SQL-запрос для recent stats

### 6.1 Рекомендуемый SQL

```sql
SELECT
    selected_model_id as model_id,
    COUNT(*) as request_count,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
    AVG(response_time) as avg_response_time
FROM prompt_history
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY selected_model_id;
```

### 6.2 Использование индексов

```
Index Scan using ix_prompt_history_created_at on prompt_history
  Filter: (created_at > now() - '7 days'::interval)
```

**Вывод**: Запрос будет использовать индекс `ix_prompt_history_created_at`.

---

## 7. Рекомендации по реализации

### 7.1 Порядок реализации

| # | Компонент | Приоритет | Зависимости |
|---|-----------|-----------|-------------|
| 1 | `PromptHistoryRepository.get_recent_stats_for_all_models()` | 1 | — |
| 2 | `AIModelResponse` schema + новые поля | 2 | 1 |
| 3 | `GET /api/v1/models` route + query params | 3 | 1, 2 |
| 4 | `AIModelInfo` (Business) + новые поля | 4 | 3 |
| 5 | `DataAPIClient.get_all_models()` + парсинг | 5 | 4 |
| 6 | `ProcessPromptUseCase._select_best_model()` | 6 | 5 |
| 7 | Логирование `decision_reason` | 7 | 6 |
| 8 | Тесты | 8 | 1-7 |

### 7.2 Рекомендуемый подход к effective_reliability_score

```python
# В Data API, после получения recent_stats
MIN_REQUESTS = 3

def calculate_effective_score(model, recent_stats):
    if recent_stats.request_count >= MIN_REQUESTS:
        recent_success_rate = recent_stats.success_count / recent_stats.request_count
        recent_speed_score = 1.0 - (recent_stats.avg_response_time / 10.0)
        recent_reliability = (recent_success_rate * 0.6) + (recent_speed_score * 0.4)
        return recent_reliability, "recent_score"
    else:
        return model.reliability_score, "fallback"
```

### 7.3 Рекомендации по тестированию

| Сценарий | Тест |
|----------|------|
| Модель с 100+ запросов за 7 дней | Должен использовать recent_score |
| Модель с 2 запросами за 7 дней | Должен использовать fallback (long-term) |
| Модель с 0 запросов за 7 дней | Должен использовать fallback |
| Старая модель деградировала | Новая модель с лучшим recent должна победить |
| `include_recent=false` | Поведение как до F010 |

---

## 8. Риски и открытые вопросы

### 8.1 Идентифицированные риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Запросы к prompt_history медленные | Низкая | Средняя | Индекс существует, мониторинг EXPLAIN |
| 2 | Все модели попадают в fallback | Средняя | Низкая | Уменьшить window_days или min_requests |
| 3 | Recent score слишком волатильный | Низкая | Средняя | Увеличить min_requests до 5 |

### 8.2 Закрытые вопросы

| # | Вопрос | Решение |
|---|--------|---------|
| 1 | Размер окна | 7 дней (параметр `window_days`) |
| 2 | Минимум запросов | 3 (параметр в будущем `min_requests`) |
| 3 | Хранить recent в БД? | Нет, вычислять на лету из prompt_history |

---

## 9. Checklist RESEARCH_DONE

- [x] Код проанализирован (process_prompt.py, domain/models.py, repositories)
- [x] Архитектурные паттерны выявлены (HTTP-only, Repository, Domain Model)
- [x] Технические ограничения определены (индексы существуют, миграция не нужна)
- [x] Точки расширения идентифицированы (4 в Data API, 4 в Business API)
- [x] Рекомендации сформулированы (порядок реализации, SQL, тесты)
- [x] Риски идентифицированы и имеют план митигации

---

## 10. Следующий шаг

```bash
/aidd-feature-plan
```

Создание детального плана реализации на основе выявленных точек расширения.
