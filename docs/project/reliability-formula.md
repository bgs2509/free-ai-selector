# Reliability Formula

> Документация по формуле расчёта надёжности AI-моделей.

## Формула

```
reliability_score = (success_rate × 0.6) + (speed_score × 0.4)
```

Где:

- **success_rate** = success_count / request_count (0.0 - 1.0)
- **speed_score** = max(0, 1.0 - avg_response_time / 10.0) (0.0 - 1.0)

## Компоненты

### Success Rate (60% веса)

Процент успешных запросов к модели.

```python
@property
def success_rate(self) -> float:
    if self.request_count == 0:
        return 0.0
    return self.success_count / self.request_count
```

**Примеры:**

| success_count | request_count | success_rate |
|---------------|---------------|--------------|
| 90 | 100 | 0.90 |
| 45 | 50 | 0.90 |
| 0 | 0 | 0.00 |

### Speed Score (40% веса)

Оценка скорости ответа. Baseline: 10 секунд = score 0.0.

```python
@property
def speed_score(self) -> float:
    avg_time = float(self.average_response_time)
    return max(0.0, 1.0 - avg_time / 10.0)
```

**Примеры:**

| avg_response_time | speed_score |
|-------------------|-------------|
| 0.0 sec | 1.00 |
| 1.0 sec | 0.90 |
| 2.0 sec | 0.80 |
| 5.0 sec | 0.50 |
| 10.0 sec | 0.00 |
| 15.0 sec | 0.00 (clamped) |

### Average Response Time

```python
@property
def average_response_time(self) -> Decimal:
    if self.request_count == 0:
        return Decimal("0.0")
    return self.total_response_time / self.request_count
```

---

## Примеры расчёта

### Пример 1: Идеальная модель

```
success_count = 100
request_count = 100
total_response_time = 200.0 (avg = 2.0 sec)

success_rate = 100/100 = 1.0
speed_score = 1.0 - 2.0/10.0 = 0.8

reliability_score = (1.0 × 0.6) + (0.8 × 0.4)
                  = 0.6 + 0.32
                  = 0.92
```

### Пример 2: Быстрая но нестабильная

```
success_count = 70
request_count = 100
total_response_time = 50.0 (avg = 0.5 sec)

success_rate = 70/100 = 0.7
speed_score = 1.0 - 0.5/10.0 = 0.95

reliability_score = (0.7 × 0.6) + (0.95 × 0.4)
                  = 0.42 + 0.38
                  = 0.80
```

### Пример 3: Стабильная но медленная

```
success_count = 95
request_count = 100
total_response_time = 600.0 (avg = 6.0 sec)

success_rate = 95/100 = 0.95
speed_score = 1.0 - 6.0/10.0 = 0.4

reliability_score = (0.95 × 0.6) + (0.4 × 0.4)
                  = 0.57 + 0.16
                  = 0.73
```

### Пример 4: Новая модель (нет данных)

```
success_count = 0
request_count = 0
total_response_time = 0.0

success_rate = 0.0
speed_score = 1.0 (avg = 0, так что 1.0 - 0/10 = 1.0)

reliability_score = (0.0 × 0.6) + (1.0 × 0.4)
                  = 0.0 + 0.4
                  = 0.40
```

---

## Почему такие веса?

### 60% Success Rate

Надёжность важнее скорости. Пользователь предпочтёт медленный но работающий ответ, чем быструю ошибку.

### 40% Speed Score

Скорость всё ещё важна для UX. Слишком медленные модели понижаются в рейтинге.

### Baseline 10 секунд

10 секунд — разумный максимум для ожидания AI-ответа. Более медленные модели получают speed_score = 0.

---

## Реализация в коде

```python
# services/free-ai-selector-data-postgres-api/app/domain/models.py

@dataclass
class AIModel:
    """Domain Entity для AI-модели с бизнес-логикой."""

    # ... fields ...

    @property
    def reliability_score(self) -> float:
        """
        Рассчитать итоговый reliability score.

        Formula: (success_rate * 0.6) + (speed_score * 0.4)

        Returns:
            Значение от 0.0 до 1.0
        """
        return (self.success_rate * 0.6) + (self.speed_score * 0.4)
```

---

## Выбор модели

```python
# services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py

def _select_best_model(self, models: list[AIModelInfo]) -> AIModelInfo:
    """Выбрать модель с максимальным reliability_score."""
    return max(models, key=lambda m: m.reliability_score)
```

Модели сортируются по `reliability_score` и выбирается лучшая.

---

## Обновление статистики

При каждом запросе:

1. **Успех:** `success_count += 1`, `request_count += 1`, `total_response_time += response_time`
2. **Ошибка:** `failure_count += 1`, `request_count += 1`

```python
# Business API вызывает Data API
await self.data_api_client.increment_success(model_id)
# или
await self.data_api_client.increment_failure(model_id)
```

---

## ADR

Подробнее о решении использовать эту формулу: [ADR-0001: Reliability Scoring](../adr/0001-reliability-scoring.md)

## Related Documentation

- [AI Providers](ai-providers.md) - Список провайдеров
- [Database Schema](database-schema.md) - Где хранится статистика
- [../ai-context/EXAMPLES.md](../ai-context/EXAMPLES.md) - Примеры кода
