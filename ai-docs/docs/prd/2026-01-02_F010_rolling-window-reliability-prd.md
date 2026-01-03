---
feature_id: "F010"
feature_name: "rolling-window-reliability"
title: "Rolling Window Reliability Score"
created: "2026-01-02"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 2
mode: "FEATURE"
related_features: ["F008"]
services: ["free-ai-selector-data-postgres-api", "free-ai-selector-business-api"]
requirements_count: 17
pipelines:
  business: true
  data: true
  integration: true
  modified: ["model-selection", "statistics-calculation"]
---

# PRD: Rolling Window Reliability Score

**Feature ID**: F010
**Версия**: 2.0
**Дата**: 2026-01-02
**Автор**: AI Agent (Аналитик)
**Статус**: PRD_READY

---

## 1. Обзор

### 1.1 Проблема

Текущая формула расчёта `reliability_score` использует **кумулятивные метрики за всё время**:

```python
success_rate = success_count / request_count  # ВСЕ запросы за ВСЁ время
reliability_score = (success_rate × 0.6) + (speed_score × 0.4)
```

**Это создаёт критическую проблему устаревания данных:**

| Сценарий | Старая модель A | Новая модель B | Результат |
|----------|-----------------|----------------|-----------|
| История | 9900 запросов @ 99% успех | 20 запросов @ 95% успех | — |
| Последние 7 дней | 100 запросов @ **50%** успех | 20 запросов @ **95%** успех | — |
| `reliability_score` | **0.911** (высокий из-за истории) | **0.910** | A выбирается! |
| Реальное качество | **50%** (деградировала!) | **95%** (отличная) | B лучше! |

**Последствия:**
- Система выбирает деградировавшую модель, игнорируя текущее качество
- Новые качественные модели не получают шанса из-за малой истории
- Пользователи получают ответы от нестабильных провайдеров

### 1.2 Решение

**Rolling Window** — учитывать только запросы за последние **7 дней** из таблицы `prompt_history`.

```python
# Новый расчёт
recent_success_rate = recent_successes / recent_requests  # за 7 дней
recent_reliability_score = (recent_success_rate × 0.6) + (recent_speed_score × 0.4)

# Fallback для новых моделей
if recent_requests < 3:
    effective_score = long_term_reliability_score  # старая формула
else:
    effective_score = recent_reliability_score     # актуальные данные
```

**Параметры:**
- **Окно:** 7 дней
- **Минимум запросов:** 3 (для статистической значимости)
- **Fallback:** если < 3 запросов за период → использовать long-term score

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Конечные пользователи | Пользователи Telegram-бота и Web UI | Получать ответы от наиболее стабильных AI-моделей |
| Администраторы | Операторы системы | Видеть актуальный рейтинг моделей |

### 1.4 Ценностное предложение

- **Актуальность:** Выбор модели основан на текущем качестве, а не исторических данных
- **Быстрая реакция:** Деградация модели отражается в рейтинге за дни, не месяцы
- **Справедливость:** Новые качественные модели быстрее поднимаются в рейтинге
- **Backward compatible:** Старая метрика сохраняется для отчётности

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | Recent Stats Calculation | Data API рассчитывает статистику из `prompt_history` за последние N дней | SQL-запрос возвращает `{model_id: {success_count, request_count, avg_response_time}}` для всех моделей |
| FR-002 | Recent Reliability Score | Domain Model вычисляет `recent_reliability_score` по формуле `(recent_success_rate × 0.6) + (recent_speed_score × 0.4)` | Тест подтверждает корректность расчёта |
| FR-003 | Effective Score with Fallback | `effective_reliability_score` возвращает `recent_reliability_score` если запросов >= 3, иначе `reliability_score` | Тест проверяет fallback при недостаточных данных |
| FR-004 | API Parameter include_recent | `GET /api/v1/models` принимает `include_recent=true` для включения recent метрик в ответ | cURL запрос с параметром возвращает recent поля |
| FR-005 | Model Selection by Effective Score | Business API выбирает модель по `effective_reliability_score` вместо `reliability_score` | При деградации старой модели выбирается новая |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-010 | Configurable Window | Параметр `window_days` в API (default: 7) | API принимает `window_days=3` и возвращает данные за 3 дня |
| FR-011 | Recent Metrics in Response | `AIModelResponse` включает `recent_success_rate`, `recent_request_count`, `effective_reliability_score` | Swagger показывает новые поля |
| FR-012 | Logging Selection Decision | Логировать почему выбрана модель (effective score, fallback) | Лог содержит `decision_reason: recent_score | fallback` |

### 2.3 Nice to Have (Could Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-020 | Configurable Min Requests | Параметр `min_requests` (default: 3) | API принимает `min_requests=5` |

---

## 3. User Stories

### US-001: Выбор модели по актуальным данным

**Как** пользователь Telegram-бота
**Я хочу** чтобы система выбирала AI-модель на основе её текущей надёжности
**Чтобы** получать ответы от наиболее стабильного провайдера

**Критерии приёмки:**
- [ ] Если модель A имела 99% успех год назад, но 50% за последнюю неделю — она НЕ выбирается
- [ ] Если модель B имеет 95% успех за последнюю неделю — она выбирается
- [ ] Выбор логируется с указанием причины

**Связанные требования:** FR-003, FR-005, FR-012

---

### US-002: Администратор видит актуальный рейтинг

**Как** администратор системы
**Я хочу** видеть и долгосрочную, и недавнюю статистику моделей
**Чтобы** понимать текущее состояние каждого провайдера

**Критерии приёмки:**
- [ ] API возвращает `reliability_score` (long-term) и `recent_reliability_score`
- [ ] API возвращает `recent_request_count` для понимания объёма данных
- [ ] Web UI показывает обе метрики

**Связанные требования:** FR-011, FR-004

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (изменение существующего функционала) |
| Затрагиваемые пайплайны | model-selection, statistics-calculation |

### 4.1 Бизнес-пайплайн

> Модификация пайплайна выбора AI-модели

**Основной flow (изменённый):**

```
[Пользовательский запрос] → [Получение списка моделей с recent metrics]
                                          ↓
                          [Расчёт effective_reliability_score]
                                          ↓
                       [Выбор модели с max(effective_score)]
                                          ↓
                          [Отправка запроса к AI провайдеру]
                                          ↓
                          [Логирование решения с причиной]
```

**Детализация этапов:**

| # | Этап | Описание | Условия перехода | Результат |
|---|------|----------|------------------|-----------|
| 1 | Получение моделей | Business API запрашивает модели с `include_recent=true` | Всегда | Список моделей с recent метриками |
| 2 | Расчёт effective score | Для каждой модели: если `recent_request_count >= 3` → `recent_reliability_score`, иначе → `reliability_score` | Для всех активных моделей | effective_reliability_score |
| 3 | Выбор лучшей | `max(models, key=effective_reliability_score)` | Есть хотя бы 1 активная модель | Выбранная модель |
| 4 | Логирование | Запись причины выбора: `recent_score` или `fallback` | После выбора | Лог-запись с decision_reason |

**Состояния сущности AIModel (расширение):**

| Поле | Тип | Описание |
|------|-----|----------|
| reliability_score | float | Долгосрочный score (существующий) |
| recent_reliability_score | float | Score за последние 7 дней (новый) |
| effective_reliability_score | float | Основной score для выбора (новый) |
| recent_request_count | int | Количество запросов за период (новый) |

### 4.2 Data Pipeline

> Поток данных для расчёта recent metrics

**Диаграмма потока данных:**

```
┌─────────────┐  GET /models?include_recent=true  ┌─────────────────┐
│ Business API│ ─────────────────────────────────▶│    Data API     │
└─────────────┘                                   └────────┬────────┘
      ▲                                                    │
      │                                                    │ 1. get_all()
      │                                                    │ 2. get_recent_stats()
      │                                                    ▼
      │                                           ┌─────────────────┐
      │ AIModelResponse[]                         │   Repository    │
      │ с recent полями                           │                 │
      │                                           │ SQL: SELECT     │
      │                                           │ FROM prompt_    │
      │                                           │ history WHERE   │
      └───────────────────────────────────────────│ created_at >    │
                                                  │ NOW() - 7 days  │
                                                  └────────┬────────┘
                                                           │
                                                           ▼
                                                  ┌─────────────────┐
                                                  │   PostgreSQL    │
                                                  │                 │
                                                  │ ┌─────────────┐ │
                                                  │ │prompt_history│ │
                                                  │ │(существует) │ │
                                                  │ └─────────────┘ │
                                                  │ ┌─────────────┐ │
                                                  │ │  ai_models  │ │
                                                  │ │(существует) │ │
                                                  │ └─────────────┘ │
                                                  └─────────────────┘
```

**Потоки данных:**

| # | Источник | Назначение | Данные | Формат | Синхронность |
|---|----------|------------|--------|--------|--------------|
| 1 | Business API | Data API | Запрос моделей с recent | HTTP GET + query params | sync |
| 2 | Data API | PostgreSQL | SQL запрос recent stats | SQL | sync |
| 3 | PostgreSQL | Data API | Агрегированные метрики | Rows | sync |
| 4 | Data API | Business API | Модели с recent полями | JSON | sync |

**Трансформации данных:**

| # | Точка | Входные данные | Преобразование | Выходные данные |
|---|-------|----------------|----------------|-----------------|
| 1 | Repository | prompt_history rows | SQL GROUP BY model_id, COUNT, AVG | {model_id: {success_count, request_count, avg_response_time}} |
| 2 | Domain Model | recent_stats dict | Формула: (success_rate × 0.6) + (speed_score × 0.4) | recent_reliability_score |
| 3 | Domain Model | recent_request_count, MIN_REQUESTS | if count >= 3: recent else long-term | effective_reliability_score |
| 4 | Schema | AIModel + recent_stats | Маппинг в response | AIModelResponse с recent полями |

### 4.3 Интеграционный пайплайн

> Изменения в контрактах API между сервисами

**Карта сервисов (изменения выделены):**

```
┌─────────────────────────────────────────────────────────────────┐
│                         СИСТЕМА                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐       ┌──────────────────┐                │
│  │  Business API    │◄─────►│     Data API     │                │
│  │                  │       │                  │                │
│  │ [ИЗМЕНЕНО]       │       │ [ИЗМЕНЕНО]       │                │
│  │ _select_best()   │       │ get_all_models() │                │
│  │ использует       │       │ +include_recent  │                │
│  │ effective_score  │       │ +window_days     │                │
│  └──────────────────┘       └──────────────────┘                │
│                                                                  │
│  ┌──────────────────┐       ┌──────────────────┐                │
│  │  Telegram Bot    │       │  Health Worker   │                │
│  │  (без изменений) │       │  (без изменений) │                │
│  └──────────────────┘       └──────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

**Точки интеграции (изменения):**

| ID | От | К | Протокол | Endpoint | Изменение |
|----|----|----|----------|----------|-----------|
| INT-001 | Business API | Data API | HTTP/REST | GET /api/v1/models | Новые query params: `include_recent`, `window_days` |
| INT-002 | Business API | Data API | HTTP/REST | GET /api/v1/models | Новые поля в response: `recent_*`, `effective_*` |

**Контракты API (изменения):**

| Интеграция | Request (изменение) | Response (изменение) | Ошибки |
|------------|---------------------|----------------------|--------|
| INT-001 | `?include_recent=true&window_days=7` | — | 400 (invalid params) |
| INT-002 | — | `+recent_success_rate`, `+recent_request_count`, `+recent_reliability_score`, `+effective_reliability_score` | — |

**Новые API параметры:**

```yaml
# GET /api/v1/models
parameters:
  - name: include_recent
    in: query
    type: boolean
    default: false
    description: Включить recent метрики в ответ
  - name: window_days
    in: query
    type: integer
    default: 7
    description: Размер окна в днях для recent расчётов
```

**Новые поля в AIModelResponse:**

```yaml
AIModelResponse:
  # ... существующие поля ...
  recent_success_rate:
    type: number
    format: float
    minimum: 0.0
    maximum: 1.0
  recent_request_count:
    type: integer
    minimum: 0
  recent_reliability_score:
    type: number
    format: float
    minimum: 0.0
    maximum: 1.0
  effective_reliability_score:
    type: number
    format: float
    minimum: 0.0
    maximum: 1.0
```

### 4.4 Влияние на существующие пайплайны

> FEATURE режим — модификация существующих пайплайнов

**Режим:** FEATURE

| Пайплайн | Тип изменения | Затрагиваемые этапы | Обратная совместимость |
|----------|---------------|---------------------|------------------------|
| model-selection | modify | Выбор лучшей модели | Да — по умолчанию `include_recent=false` |
| statistics-calculation | add | Новый метод get_recent_stats | Да — существующие методы не изменены |
| API response | add | Новые поля в AIModelResponse | Да — поля опциональные, default values |

**Breaking changes:**
- [x] Нет breaking changes
- Все изменения аддитивные
- Существующие клиенты продолжат работать без изменений
- Новые поля имеют значения по умолчанию (0.0, 0)

**План обратной совместимости:**

```python
# Без include_recent — поведение не меняется
GET /api/v1/models
→ возвращает модели БЕЗ recent полей (или с defaults)

# С include_recent — новое поведение
GET /api/v1/models?include_recent=true
→ возвращает модели С recent полями
```

---

## 5. UI/UX требования

### 5.1 Экраны и интерфейсы

| ID | Экран | Описание | Приоритет |
|----|-------|----------|-----------|
| UI-001 | Web UI Statistics | Отображение `effective_reliability_score` вместо `reliability_score` | Must |
| UI-002 | Web UI Model Details | Показ обеих метрик (recent и long-term) | Should |

### 5.2 User Flows

**Flow 1: Просмотр статистики моделей**

```
[Открыть /static/index.html] → [Нажать "Statistics"]
                                        ↓
                     [Таблица с effective_reliability_score]
                                        ↓
                     [Сортировка по effective_reliability_score]
```

---

## 6. Нефункциональные требования

### 6.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Время расчёта recent stats | < 100ms | SQL EXPLAIN ANALYZE |
| NF-002 | Влияние на выбор модели | + < 50ms к текущему времени | Prometheus metrics |

### 6.2 Совместимость

| ID | Требование | Описание |
|----|------------|----------|
| NF-010 | Backward Compatibility | Старое поле `reliability_score` сохраняется и работает |
| NF-011 | API Compatibility | Без `include_recent` API возвращает тот же ответ что и раньше |

### 6.3 Надёжность

| ID | Требование | Описание |
|----|------------|----------|
| NF-020 | Graceful Fallback | При ошибке SQL — использовать long-term score |
| NF-021 | Index Usage | SQL использует существующий индекс `ix_prompt_history_created_at` |

---

## 7. Технические ограничения

### 7.1 Обязательные технологии

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL 16 (существующая)
- **ORM**: SQLAlchemy 2.x (async)

### 7.2 Существующие ресурсы

| Ресурс | Описание | Готовность |
|--------|----------|------------|
| `prompt_history` table | Полная история запросов с `created_at` | ✅ Существует |
| `ix_prompt_history_created_at` | Индекс для временных запросов | ✅ Существует |
| `AIModel` domain model | Доменная модель с вычисляемыми свойствами | ✅ Нужно расширить |

### 7.3 Ограничения

- **Нет миграций БД** — используем существующую структуру `prompt_history`
- **HTTP-only архитектура** — Business API получает данные через Data API

---

## 8. Допущения и риски

### 8.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | `prompt_history` содержит достаточно данных за 7 дней | Нужно увеличить окно или уменьшить min_requests |
| 2 | Индекс `created_at` достаточно эффективен | Возможно потребуется составной индекс |

### 8.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Медленный SQL при большом объёме данных | Low | Medium | Использовать существующий индекс, LIMIT |
| 2 | "Cold start" для всех моделей при малом трафике | Medium | Low | Fallback на long-term score |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Оптимальный размер окна? | Resolved | 7 дней (пользователь выбрал) |
| 2 | Минимум запросов для статистики? | Resolved | 3 запроса (пользователь выбрал) |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| Rolling Window | Скользящее окно — метод расчёта метрик только за последний период времени |
| Effective Score | Итоговый score для выбора модели (recent или fallback) |
| Fallback | Резервный механизм — использование long-term score при недостатке recent данных |

---

## 11. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-01-02 | AI Analyst | Первоначальная версия |
| 2.0 | 2026-01-03 | AI Analyst | Добавлена секция 4 (Пайплайны), INT-* требования |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-*, NF-*, UI-*, INT-*)
- [x] Критерии приёмки определены для каждого требования
- [x] User stories связаны с требованиями
- [x] Бизнес-пайплайн описан (основной flow, состояния сущностей)
- [x] Data Pipeline описан (диаграмма потоков, трансформации данных)
- [x] Интеграционный пайплайн описан (карта сервисов, точки интеграции, контракты)
- [x] Раздел "Влияние на существующие пайплайны" заполнен
- [x] Нет блокирующих открытых вопросов
- [x] Риски идентифицированы и имеют план митигации
