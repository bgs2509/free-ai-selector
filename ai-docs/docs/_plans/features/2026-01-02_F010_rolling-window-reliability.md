---
feature_id: "F010"
feature_name: "rolling-window-reliability"
title: "Implementation Plan: Rolling Window Reliability Score"
created: "2026-01-03"
author: "AI (Architect)"
type: "plan"
status: "PENDING_APPROVAL"
version: 1
mode: "FEATURE"
related__analysis: "_analysis/2026-01-02_F010_rolling-window-reliability-_analysis.md"
related__research: "_research/2026-01-02_F010_rolling-window-reliability-_research.md"
---

# Implementation Plan: Rolling Window Reliability Score

**Feature ID**: F010
**Дата**: 2026-01-03
**Автор**: AI Agent (Архитектор)
**Статус**: PENDING_APPROVAL

---

## 1. Обзор

### 1.1 Цель фичи

Заменить кумулятивный `reliability_score` на `effective_reliability_score`, который:
- Использует данные за последние 7 дней (`window_days`)
- Применяет fallback на long-term score если запросов < 3

### 1.2 Затрагиваемые сервисы

| Сервис | Роль | Изменения |
|--------|------|-----------|
| `free-ai-selector-data-postgres-api` | Источник данных | Новый метод + API params + schema |
| `free-ai-selector-business-api` | Потребитель | Новые поля + логика выбора |

### 1.3 Диаграмма изменений

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              ИЗМЕНЕНИЯ                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Business API                          Data API                          │
│  ┌──────────────────────────┐         ┌──────────────────────────┐      │
│  │ process_prompt.py        │         │ models.py (route)        │      │
│  │ ┌────────────────────┐   │         │ ┌────────────────────┐   │      │
│  │ │ _select_best_model │   │  HTTP   │ │ get_all_models()   │   │      │
│  │ │ key=effective_score│◄──┼─────────┼─┤ +include_recent    │   │      │
│  │ └────────────────────┘   │         │ │ +window_days       │   │      │
│  │                          │         │ └─────────┬──────────┘   │      │
│  │ domain/models.py         │         │           │               │      │
│  │ ┌────────────────────┐   │         │ ┌─────────▼──────────┐   │      │
│  │ │ AIModelInfo        │   │         │ │ prompt_history_    │   │      │
│  │ │ +effective_score   │   │         │ │ repository.py      │   │      │
│  │ │ +recent_request_cnt│   │         │ │ +get_recent_stats  │   │      │
│  │ │ +decision_reason   │   │         │ │  _for_all_models() │   │      │
│  │ └────────────────────┘   │         │ └────────────────────┘   │      │
│  └──────────────────────────┘         └──────────────────────────┘      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. План изменений: Data API

### 2.1 Новые компоненты

| # | Компонент | Файл | Описание |
|---|-----------|------|----------|
| D1 | `get_recent_stats_for_all_models()` | `prompt_history_repository.py` | SQL GROUP BY для всех моделей за N дней |

### 2.2 Модификации существующего кода

| # | Файл | Изменение | Строки |
|---|------|-----------|--------|
| D2 | `schemas.py` | Добавить поля в `AIModelResponse` | ~80-85 |
| D3 | `models.py` (route) | Добавить query params + logic | ~23-40 |
| D4 | `models.py` (route) | Функция `_model_to_response_with_recent()` | ~264-300 |

### 2.3 Детали реализации

#### D1: `PromptHistoryRepository.get_recent_stats_for_all_models()`

```python
async def get_recent_stats_for_all_models(
    self, window_days: int = 7
) -> Dict[int, Dict[str, Any]]:
    """
    Get aggregated statistics for all models within a time window.

    Returns:
        Dict[model_id, {request_count, success_count, avg_response_time}]
    """
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

#### D2: Новые поля в `AIModelResponse`

```python
# В schemas.py, класс AIModelResponse
# Добавить после reliability_score:

recent_success_rate: Optional[float] = Field(
    None, ge=0.0, le=1.0,
    description="Success rate for recent period (0.0 - 1.0)"
)
recent_request_count: Optional[int] = Field(
    None, ge=0,
    description="Request count for recent period"
)
recent_reliability_score: Optional[float] = Field(
    None, ge=0.0, le=1.0,
    description="Reliability score for recent period"
)
effective_reliability_score: Optional[float] = Field(
    None, ge=0.0, le=1.0,
    description="Score used for model selection (recent or fallback)"
)
decision_reason: Optional[str] = Field(
    None,
    description="Why effective score was chosen: 'recent_score' or 'fallback'"
)
```

#### D3: Новые query params в `GET /api/v1/models`

```python
@router.get("", response_model=List[AIModelResponse])
async def get_all_models(
    active_only: bool = True,
    include_recent: bool = Query(
        False,
        description="Include recent metrics calculated from prompt_history"
    ),
    window_days: int = Query(
        7,
        ge=1,
        le=30,
        description="Window size in days for recent metrics"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[AIModelResponse]:
    # ... implementation
```

#### D4: Логика расчёта effective score

```python
MIN_REQUESTS_FOR_RECENT = 3

def _calculate_recent_metrics(model: AIModel, recent_stats: Dict) -> Dict:
    """Calculate recent metrics for a model."""
    stats = recent_stats.get(model.id, {})
    request_count = stats.get("request_count", 0)
    success_count = stats.get("success_count", 0)
    avg_response_time = stats.get("avg_response_time", 0.0)

    if request_count >= MIN_REQUESTS_FOR_RECENT:
        recent_success_rate = success_count / request_count
        recent_speed_score = max(0.0, 1.0 - (avg_response_time / 10.0))
        recent_reliability = (recent_success_rate * 0.6) + (recent_speed_score * 0.4)

        return {
            "recent_success_rate": recent_success_rate,
            "recent_request_count": request_count,
            "recent_reliability_score": recent_reliability,
            "effective_reliability_score": recent_reliability,
            "decision_reason": "recent_score",
        }
    else:
        return {
            "recent_success_rate": None,
            "recent_request_count": request_count,
            "recent_reliability_score": None,
            "effective_reliability_score": model.reliability_score,
            "decision_reason": "fallback",
        }
```

---

## 3. План изменений: Business API

### 3.1 Модификации существующего кода

| # | Файл | Изменение | Строки |
|---|------|-----------|--------|
| B1 | `domain/models.py` | Добавить поля в `AIModelInfo` | ~19-28 |
| B2 | `data_api_client.py` | Парсинг новых полей + params | ~59-93 |
| B3 | `process_prompt.py` | Использовать `effective_reliability_score` | ~72, ~202-212 |
| B4 | `process_prompt.py` | Логирование `decision_reason` | ~82-92 |

### 3.2 Детали реализации

#### B1: Новые поля в `AIModelInfo`

```python
@dataclass
class AIModelInfo:
    """AI Model information DTO."""

    id: int
    name: str
    provider: str
    api_endpoint: str
    reliability_score: float
    is_active: bool
    api_format: str = "openai"
    env_var: str = ""
    # F010 new fields
    effective_reliability_score: float = 0.0
    recent_request_count: int = 0
    decision_reason: str = "fallback"
```

#### B2: Изменения в `DataAPIClient.get_all_models()`

```python
async def get_all_models(
    self, active_only: bool = True, include_recent: bool = True
) -> List[AIModelInfo]:
    """Get all AI models with optional recent metrics."""
    try:
        response = await self.client.get(
            f"{self.base_url}/api/v1/models",
            params={
                "active_only": active_only,
                "include_recent": include_recent,
                "window_days": 7,
            },
            headers=self._get_headers(),
        )
        response.raise_for_status()

        models_data = response.json()
        return [
            AIModelInfo(
                id=model["id"],
                name=model["name"],
                provider=model["provider"],
                api_endpoint=model["api_endpoint"],
                reliability_score=model["reliability_score"],
                is_active=model["is_active"],
                api_format=model.get("api_format", "openai"),
                env_var=model.get("env_var", ""),
                # F010 fields
                effective_reliability_score=model.get(
                    "effective_reliability_score", model["reliability_score"]
                ),
                recent_request_count=model.get("recent_request_count", 0),
                decision_reason=model.get("decision_reason", "fallback"),
            )
            for model in models_data
        ]
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch models: {sanitize_error_message(e)}")
        raise
```

#### B3: Изменение `_select_best_model()`

```python
def _select_best_model(self, models: list[AIModelInfo]) -> AIModelInfo:
    """
    Select best model based on effective reliability score (F010).

    Uses effective_reliability_score which is either:
    - recent_reliability_score (if >= 3 requests in window)
    - reliability_score (fallback)
    """
    return max(models, key=lambda m: m.effective_reliability_score)
```

#### B4: Расширенное логирование

```python
log_decision(
    logger,
    decision="ACCEPT",
    reason="highest_effective_reliability_score",
    evaluated_conditions={
        "models_count": len(models),
        "selected_model": best_model.name,
        "selected_provider": best_model.provider,
        "effective_score": float(best_model.effective_reliability_score),
        "long_term_score": float(best_model.reliability_score),
        "decision_reason": best_model.decision_reason,  # F010
        "recent_request_count": best_model.recent_request_count,  # F010
    },
)
```

---

## 4. API контракты

### 4.1 Изменения в GET /api/v1/models

**Endpoint**: `GET /api/v1/models`

**Новые Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_recent` | bool | `false` | Include recent metrics in response |
| `window_days` | int | `7` | Window size for recent metrics (1-30) |

**Response Schema Changes** (если `include_recent=true`):

```yaml
AIModelResponse:
  # ... existing fields ...
  recent_success_rate:
    type: number
    format: float
    nullable: true
    description: "Success rate for recent period (null if no data)"
  recent_request_count:
    type: integer
    nullable: true
    description: "Request count in recent period"
  recent_reliability_score:
    type: number
    format: float
    nullable: true
    description: "Reliability score for recent period"
  effective_reliability_score:
    type: number
    format: float
    description: "Score used for model selection"
  decision_reason:
    type: string
    enum: ["recent_score", "fallback"]
    description: "Reason for effective score choice"
```

**Example Response** (с `include_recent=true`):

```json
[
  {
    "id": 1,
    "name": "gemini-2.0-flash",
    "provider": "google",
    "reliability_score": 0.92,
    "recent_success_rate": 0.85,
    "recent_request_count": 47,
    "recent_reliability_score": 0.87,
    "effective_reliability_score": 0.87,
    "decision_reason": "recent_score"
  },
  {
    "id": 2,
    "name": "llama-3.3-70b",
    "provider": "groq",
    "reliability_score": 0.88,
    "recent_success_rate": null,
    "recent_request_count": 2,
    "recent_reliability_score": null,
    "effective_reliability_score": 0.88,
    "decision_reason": "fallback"
  }
]
```

### 4.2 Точки интеграции (INT-*)

| ID | От → К | Изменение | Backward Compatible |
|----|--------|-----------|---------------------|
| INT-001 | Business API → Data API | Новые query params | Да (`include_recent=false` по умолчанию) |
| INT-002 | Business API → Data API | Новые поля в response | Да (поля опциональные) |

---

## 5. План тестирования

### 5.1 Unit Tests — Data API

| # | Тест | Файл | Описание |
|---|------|------|----------|
| T1 | `test_get_recent_stats_for_all_models` | `test_prompt_history_repository.py` | SQL агрегация работает |
| T2 | `test_get_models_with_include_recent` | `test_models_route.py` | API возвращает recent поля |
| T3 | `test_effective_score_recent` | `test_models_route.py` | Модель с >=3 запросов получает recent |
| T4 | `test_effective_score_fallback` | `test_models_route.py` | Модель с <3 запросов получает fallback |
| T5 | `test_backward_compatibility` | `test_models_route.py` | Без `include_recent` поведение не меняется |

### 5.2 Unit Tests — Business API

| # | Тест | Файл | Описание |
|---|------|------|----------|
| T6 | `test_select_best_model_effective_score` | `test_process_prompt.py` | Выбирает по effective_score |
| T7 | `test_log_decision_reason` | `test_process_prompt.py` | Логирует decision_reason |

### 5.3 Integration Tests

| # | Тест | Описание |
|---|------|----------|
| T8 | Degraded model not selected | Старая модель с плохим recent score НЕ выбирается |
| T9 | New model selected | Новая модель с хорошим recent score выбирается |

---

## 6. План реализации

### 6.1 Порядок выполнения

| # | Этап | Зависимости | Файлы |
|---|------|-------------|-------|
| 1 | Repository method | — | `prompt_history_repository.py` |
| 2 | Schema update | — | `schemas.py` |
| 3 | Route logic | 1, 2 | `models.py` |
| 4 | Business domain model | 3 | `domain/models.py` |
| 5 | HTTP client update | 4 | `data_api_client.py` |
| 6 | Use case update | 5 | `process_prompt.py` |
| 7 | Unit tests | 1-6 | `tests/unit/` |
| 8 | Integration test | 7 | Manual/E2E |

### 6.2 Оценка объёма изменений

| Сервис | Новые строки | Модифицированные строки |
|--------|--------------|------------------------|
| Data API | ~80 | ~30 |
| Business API | ~20 | ~25 |
| Тесты | ~100 | ~20 |
| **Итого** | ~200 | ~75 |

---

## 7. Риски и митигация

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | SQL медленный при большом prompt_history | Низкая | Средняя | Индекс `ix_prompt_history_created_at` существует |
| 2 | Все модели в fallback (мало трафика) | Средняя | Низкая | Система работает как раньше |
| 3 | Recent score нестабильный | Низкая | Средняя | min_requests=3 сглаживает шум |
| 4 | Breaking change для клиентов | Низкая | Высокая | `include_recent=false` по умолчанию |

---

## 8. Обратная совместимость

### 8.1 Гарантии

| Аспект | Гарантия |
|--------|----------|
| API без `include_recent` | Идентичный ответ как до F010 |
| Существующие клиенты | Продолжают работать без изменений |
| Миграции БД | Не требуются |
| Существующие тесты | Не ломаются |

### 8.2 Стратегия rollback

```bash
# В случае проблем:
# 1. Business API продолжит работать на reliability_score
#    (effective_score == reliability_score при fallback)

# 2. Data API можно переключить:
#    include_recent=false (по умолчанию)
```

---

## 9. Checklist PLAN_APPROVED

- [x] Компоненты системы определены (Data API: 4, Business API: 4)
- [x] API контракты описаны (query params, response schema)
- [x] Точки интеграции (INT-001, INT-002) описаны
- [x] NFR учтены (производительность — индекс существует)
- [x] Зависимости между компонентами ясны (порядок 1-8)
- [x] Обратная совместимость обеспечена
- [ ] **План утверждён пользователем** ← ТРЕБУЕТСЯ

---

## 10. Следующий шаг

После утверждения плана:

```bash
/aidd-generate
```
