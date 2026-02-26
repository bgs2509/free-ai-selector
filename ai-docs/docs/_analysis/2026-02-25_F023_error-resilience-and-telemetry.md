---
feature_id: "F023"
feature_name: "error-resilience-and-telemetry"
title: "Cooldown для постоянных ошибок, exponential backoff и per-request telemetry"
created: "2026-02-25"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 1
mode: "FEATURE"

related_features: [F012, F022]
services: [free-ai-selector-business-api]
requirements_count: 10

pipelines:
  business: true
  data: false
  integration: true
  modified: [provider-failover, retry-mechanism, telemetry]
---

# PRD: Cooldown для постоянных ошибок, exponential backoff и per-request telemetry

**Feature ID**: F023
**Версия**: 1.0
**Дата**: 2026-02-25
**Автор**: AI Agent (Аналитик)
**Статус**: Draft

---

## 1. Обзор

### 1.1 Проблема

После внедрения F022 (этапы 1-3) система корректно классифицирует ошибки 402/404 и обрезает длинные payload. Однако три серьёзных проблемы остаются нерешёнными:

1. **Мёртвые провайдеры перебираются в каждом запросе**. Провайдеры с невалидными ключами (401/403) или исчерпанным free tier (402) правильно классифицируются как `AuthenticationError`/`ValidationError`, но НЕ исключаются из выборки. В результате 8 заведомо мёртвых провайдеров генерируют 108 000+ бесполезных вызовов за 48 часов. Каждый запрос тратит ~4 591 мс на перебор нерабочих провайдеров перед тем, как добраться до рабочего.

2. **Фиксированная задержка retry неадекватна**. `retry_service.py` использует `MAX_RETRIES=10` с фиксированной задержкой `10 сек`, что даёт 100 секунд максимального ожидания на один провайдер. Нет адаптации к нагрузке, нет jitter для предотвращения thundering herd.

3. **Невозможна диагностика без SSH на prod**. В HTTP response от Business API есть `selected_model` и `provider`, но нет `duration_ms`, `http_status`, `attempts`, `fallback_used`. Batch-прогон записывает в `results.jsonl` только `status` и `response`/`error`. Каждый анализ требует парсинга docker logs вручную.

**Масштаб проблемы** (prod-логи за 48ч):

| Провайдер | HTTP код | Кол-во вызовов | Статус |
|-----------|----------|----------------|--------|
| Scaleway | 403 | 14 526 | Мёртв (невалидный ключ) |
| Kluster | 403 | 14 513 | Мёртв (невалидный ключ) |
| DeepSeek | 402 | 14 321 | Мёртв (free tier исчерпан) |
| Novita | 404 | 14 481 | Мёртв (endpoint не найден) |
| Fireworks | 404 | 14 353 | Мёртв (endpoint не найден) |
| OpenRouter | 404 | 13 070 | Мёртв (endpoint не найден) |
| Cerebras | 404 | 12 628 | Мёртв (endpoint не найден) |

- Success rate: 33.91%
- Error rate: 66.09%
- Средняя латентность ошибочных запросов: 4 591 мс

### 1.2 Решение

Три улучшения, соответствующие этапам 4-6 из fix plan:

1. **Cooldown 24ч для 401/402/403/404** (Этап 4) -- при получении `AuthenticationError` или `ValidationError` в fallback loop вызывать `set_availability(model_id, cooldown=86400)` через Data API. Мёртвые провайдеры автоматически исключаются на 24 часа.

2. **Exponential backoff в retry-service** (Этап 5) -- заменить фиксированную задержку `10 сек x 10 retry` на экспоненциальный backoff `2s -> 4s -> 8s` с jitter. Снизить `MAX_RETRIES` с 10 до 3.

3. **Per-request telemetry** (Этап 6) -- расширить `PromptResponse` и `ProcessPromptResponse` полями метаданных (`attempts`, `fallback_used`, `error_type`). Внешние скрипты получают диагностику из HTTP response без SSH.

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Пользователи Telegram-бота | Отправляют промпты через бот | Быстрый ответ (< 5 сек), без ожидания перебора мёртвых провайдеров |
| Пользователи Web UI / API | Используют REST API напрямую | Стабильная работа, информативные метаданные в response |
| Скрипт массового прогона | Пакетная обработка запросов | Быстрый failover, полная диагностика в results.jsonl |
| DevOps / разработчик | Мониторинг и отладка | Диагностика без SSH, данные для графиков и алертов |

### 1.4 Ценностное предложение

- Снижение средней латентности запроса с ~4 591 мс до < 2 000 мс (пропуск 8 мёртвых провайдеров)
- Снижение максимального retry-ожидания на провайдер с 100 сек до ~14 сек
- Устранение 108 000+ бесполезных вызовов за 48ч (экономия ресурсов)
- Полная диагностика из HTTP response без SSH на prod

### 1.5 Зависимости от F022

Данная фича **зависит от F022 (этапы 1-3)**:

| F022 этап | Требование | Почему нужен для F023 |
|-----------|------------|----------------------|
| Этап 1 | classify_error: 402 -> AuthenticationError, 404 -> ValidationError | Без этого 402/404 попадают в generic ProviderError и не могут быть отфильтрованы для cooldown |
| Этап 2 | Проброс HTTPStatusError из провайдеров | Без этого classify_error не получает HTTP-код от 12 из 14 провайдеров |
| Этап 3 | Payload budget | Не блокирует F023, но снижает базовый уровень ошибок |

**Порядок внедрения**: F022 (этапы 1-3) -> F023 (этапы 4-6).

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Приоритет | Критерий приёмки |
|----|----------|----------|-----------|------------------|
| FR-001 | Cooldown 24ч для AuthenticationError | В `_handle_transient_error()` добавить проверку: если ошибка `AuthenticationError` (401/402/403), вызывать `set_availability(model_id, AUTH_ERROR_COOLDOWN_SECONDS)`. Значение cooldown: 86400 сек (24ч), конфигурируемо через env `AUTH_ERROR_COOLDOWN_SECONDS`. | Must | 1) Провайдер с 401/403 помечается unavailable на 24ч после первой ошибки. 2) Data API endpoint `PUT /api/v1/models/{id}/set-availability` вызывается с seconds=86400. 3) При следующем запросе мёртвый провайдер не попадает в candidate_models (фильтр `available_only=True`). 4) Unit-тест: mock data_api_client.set_availability вызван с (model_id, 86400). |
| FR-002 | Cooldown 24ч для ValidationError (404) | В `_handle_transient_error()` добавить проверку: если ошибка `ValidationError`, вызывать `set_availability(model_id, VALIDATION_ERROR_COOLDOWN_SECONDS)`. Значение cooldown: 86400 сек (24ч), конфигурируемо через env `VALIDATION_ERROR_COOLDOWN_SECONDS`. | Must | 1) Провайдер с 404 помечается unavailable на 24ч. 2) set_availability вызывается с seconds=86400. 3) Unit-тест подтверждает. |
| FR-003 | Exponential backoff в retry_service | Заменить `asyncio.sleep(delay_seconds)` на `asyncio.sleep(min(base_delay * 2^(attempt-1), max_delay) + random.uniform(0, jitter))`. Новые env-параметры: `RETRY_BASE_DELAY` (default: 2.0), `RETRY_MAX_DELAY` (default: 30.0), `RETRY_JITTER` (default: 1.0). | Must | 1) Задержки: 2s -> 4s -> 8s (при base_delay=2, max_retries=3). 2) Jitter добавляет случайную величину [0, RETRY_JITTER]. 3) Unit-тест: mock asyncio.sleep вызван с корректными значениями. |
| FR-004 | Снижение MAX_RETRIES с 10 до 3 | Изменить значение по умолчанию `MAX_RETRIES` с 10 на 3. Env-переменная `MAX_RETRIES` продолжает работать для override. | Must | 1) Максимальное ожидание на провайдер: ~14 сек (2+4+8) вместо 100 сек (10x10). 2) Логи `all_retries_exhausted` показывают `total_attempts=4` (initial + 3 retry). |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Приоритет | Критерий приёмки |
|----|----------|----------|-----------|------------------|
| FR-010 | Telemetry: расширить PromptResponse | Добавить в domain model `PromptResponse` поля: `attempts: int` (количество попыток до успеха, включая fallback), `fallback_used: bool` (True если ответ не от первой модели). | Should | 1) PromptResponse содержит поля attempts и fallback_used. 2) При успешном ответе от первой модели: attempts=1, fallback_used=False. 3) При fallback на вторую модель: attempts>=2, fallback_used=True. |
| FR-011 | Telemetry: расширить ProcessPromptResponse schema | Добавить в Pydantic schema `ProcessPromptResponse` поля: `attempts: int`, `fallback_used: bool`. HTTP response от Business API возвращает эти поля. | Should | 1) `POST /api/v1/prompts/process` возвращает `attempts` и `fallback_used` в JSON body. 2) Swagger/OpenAPI docs отражают новые поля. 3) Обратная совместимость: новые поля добавлены (аддитивное изменение). |
| FR-012 | Telemetry: error_type в failed response | При ошибке (все провайдеры упали) в HTTP 500 response включать `error_type` (последний тип ошибки: AuthenticationError, ValidationError и т.д.) в detail message. | Should | 1) HTTP 500 detail содержит тип последней ошибки. 2) Скрипт может парсить error_type из response. |

### 2.3 Nice to Have (Could Have)

| ID | Название | Описание | Приоритет | Критерий приёмки |
|----|----------|----------|-----------|------------------|
| FR-020 | Логирование cooldown с причиной | При установке cooldown логировать `permanent_error_cooldown` с полями: `model_id`, `model_name`, `provider`, `error_type`, `cooldown_seconds`, `http_status_code`. | Could | В structlog логах видно полную причину cooldown. |
| FR-021 | Сохранение retry_with_fixed_delay как deprecated alias | Оставить функцию `retry_with_fixed_delay` как wrapper вокруг новой `retry_with_exponential_backoff` для обратной совместимости тестов. | Could | Существующие тесты, вызывающие `retry_with_fixed_delay`, продолжают работать. |

---

## 3. User Stories

### US-001: Мгновенный пропуск мёртвых провайдеров

**Как** пользователь Telegram-бота
**Я хочу** получить ответ за < 5 секунд
**Чтобы** не ждать, пока система перебирает 8 нерабочих провайдеров

**Критерии приёмки:**
- [ ] Провайдеры с 401/402/403 помечаются unavailable на 24ч после первого AuthenticationError
- [ ] Провайдеры с 404 помечаются unavailable на 24ч после первого ValidationError
- [ ] При следующем запросе мёртвые провайдеры не попадают в candidate_models
- [ ] Средняя латентность запроса < 2 000 мс (при наличии 3+ рабочих провайдеров)

**Связанные требования:** FR-001, FR-002, FR-020

### US-002: Быстрый retry при 5xx ошибках

**Как** система маршрутизации
**Я хочу** быстро повторить запрос к перегруженному провайдеру с нарастающей задержкой
**Чтобы** не тратить 100 секунд на один провайдер и не перегружать его одинаковыми интервалами

**Критерии приёмки:**
- [ ] Retry с exponential backoff: 2s -> 4s -> 8s
- [ ] Максимум 3 retry (вместо 10)
- [ ] Jitter предотвращает thundering herd
- [ ] Общее время retry на провайдер < 15 сек

**Связанные требования:** FR-003, FR-004, FR-021

### US-003: Диагностика без SSH

**Как** разработчик
**Я хочу** видеть attempts, fallback_used в HTTP response от Business API
**Чтобы** диагностировать проблемы из results.jsonl без SSH на prod

**Критерии приёмки:**
- [ ] `POST /api/v1/prompts/process` возвращает `attempts` и `fallback_used`
- [ ] Batch-скрипт записывает telemetry-поля в results.jsonl
- [ ] Полная диагностика одного запроса из одной строки jsonl

**Связанные требования:** FR-010, FR-011, FR-012

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE |
| Затрагиваемые пайплайны | provider-failover, retry-mechanism, telemetry |

### 4.1 Бизнес-пайплайн

**Основной flow (изменённый):**

```
[Запрос от клиента]
  -> [Валидация Pydantic]
    -> [Payload budget (F022 FR-004)]
      -> [Получить active+available модели из Data API]
        -> [Фильтрация по API key]
          -> [Сортировка по reliability_score]
            -> [Fallback loop по моделям]:
               -> [retry_with_exponential_backoff(generate)]  <-- ИЗМЕНЕНО (FR-003, FR-004)
                 -> [Успех -> response с telemetry]           <-- ИЗМЕНЕНО (FR-010, FR-011)
                 -> [RateLimitError -> set_availability(3600) + continue]
                 -> [AuthenticationError -> set_availability(86400) + continue]  <-- НОВОЕ (FR-001)
                 -> [ValidationError -> set_availability(86400) + continue]      <-- НОВОЕ (FR-002)
                 -> [ServerError/TimeoutError -> increment_failure + continue]
```

**Состояния провайдера:**

```
   AVAILABLE (available_at = null или < now)
       |
       |-- RateLimitError (429)
       |      -> COOLDOWN_RATE_LIMIT (available_at = now + 3600)
       |         -> через 1ч -> AVAILABLE
       |
       |-- AuthenticationError (401/402/403)      <-- НОВОЕ
       |      -> COOLDOWN_AUTH_ERROR (available_at = now + 86400)
       |         -> через 24ч -> AVAILABLE
       |
       |-- ValidationError (400/404/422)          <-- НОВОЕ
              -> COOLDOWN_VALIDATION_ERROR (available_at = now + 86400)
                 -> через 24ч -> AVAILABLE
```

### 4.2 Data Pipeline

Не затрагивается напрямую. Data API endpoint `PUT /api/v1/models/{id}/set-availability` уже существует и поддерживает произвольный cooldown в секундах. PostgreSQL, seed, миграции -- без изменений.

### 4.3 Интеграционный пайплайн

**Точки интеграции:**

| ID | От | К | Изменение |
|----|----|---|-----------|
| INT-001 | process_prompt._handle_transient_error | Data API (set_availability) | НОВЫЙ вызов для AuthenticationError/ValidationError с cooldown=86400 |
| INT-002 | process_prompt._generate_with_retry | retry_service | Вызов новой функции retry_with_exponential_backoff вместо retry_with_fixed_delay |
| INT-003 | prompts.py (HTTP endpoint) | ProcessPromptResponse | Новые поля attempts, fallback_used в HTTP response |

**Контракты:**

1. **Data API set_availability** (существующий):
   - `PUT /api/v1/models/{id}/set-availability?seconds={cooldown}`
   - Устанавливает `available_at = now + seconds` в PostgreSQL
   - Модели с `available_at > now` не возвращаются при `available_only=True`

2. **Business API ProcessPromptResponse** (расширяемый):
   - Добавляются `attempts: int` и `fallback_used: bool`
   - Аддитивное изменение, обратно совместимо

### 4.4 Влияние на существующие пайплайны

| Пайплайн | Тип изменения | Затрагиваемые этапы | Обратная совместимость |
|----------|---------------|---------------------|------------------------|
| provider-failover | modify | _handle_transient_error() | Да -- добавляется cooldown ДО increment_failure, логика failure не меняется |
| retry-mechanism | modify | retry_with_fixed_delay -> retry_with_exponential_backoff | Да -- функция переименовывается, старое имя оставляется как alias |
| telemetry | add | PromptResponse, ProcessPromptResponse, prompts.py | Да -- новые поля в response (аддитивное изменение) |

**Breaking changes:**
- [x] Нет breaking changes для внешнего API (HTTP контракты расширяются аддитивно)
- [x] Внутренний: `retry_with_fixed_delay` заменяется на `retry_with_exponential_backoff`, но alias сохраняется (FR-021)
- [x] `MAX_RETRIES` default меняется с 10 на 3 -- может повлиять на production если не задано через env

---

## 5. UI/UX требования

Не применимо. Изменения backend-only. Telegram-бот и API клиенты не требуют обновления (новые поля в response -- аддитивные).

---

## 6. Нефункциональные требования

### 6.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Средняя латентность запроса при мёртвых провайдерах | < 2 000 мс (при 3+ рабочих провайдерах) | Прогон 50 запросов, замер p50 |
| NF-002 | Максимальное время retry на один провайдер | < 15 сек (при MAX_RETRIES=3) | Логи retry_service: сумма delay |
| NF-003 | Кол-во бесполезных вызовов к мёртвым провайдерам за 48ч | < 100 (1 вызов при автовосстановлении через 24ч) | Подсчёт по prod-логам |

### 6.2 Надёжность

| ID | Метрика | Требование |
|----|---------|------------|
| NF-010 | Обратная совместимость API | HTTP контракт /api/v1/prompts/process не ломается. Новые поля аддитивны |
| NF-011 | Обратная совместимость env | Существующий `MAX_RETRIES` env var продолжает работать. Новые env vars имеют defaults |
| NF-012 | Graceful degradation при ошибке set_availability | Если Data API недоступен, cooldown не устанавливается, но запрос продолжается (try/except) |
| NF-013 | Jitter в backoff | Random jitter предотвращает synchronized retry storms |

### 6.3 Наблюдаемость

| ID | Метрика | Требование |
|----|---------|------------|
| NF-020 | Логирование cooldown | Каждый cooldown логируется через structlog с model_id, error_type, cooldown_seconds |
| NF-021 | Логирование retry backoff | Каждый retry логируется с attempt, next_delay_seconds, error_type |
| NF-022 | Telemetry в HTTP response | attempts и fallback_used доступны в JSON response |

### 6.4 Требования к тестированию

#### Smoke тесты (ОБЯЗАТЕЛЬНО)
- [ ] Health check отвечает 200
- [ ] POST /api/v1/prompts/process с коротким промптом -> 200, response содержит `attempts` и `fallback_used`

#### Unit тесты
- **Требуются**: Да
- **Порог покрытия**: >= 75%
- **Критические модули**: `process_prompt.py`, `retry_service.py`

#### Сводная таблица

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Unit | AuthenticationError -> set_availability(86400) | Да |
| TRQ-002 | Unit | ValidationError -> set_availability(86400) | Да |
| TRQ-003 | Unit | Exponential backoff: delays 2s, 4s, 8s | Да |
| TRQ-004 | Unit | MAX_RETRIES=3 -> 4 total attempts max | Да |
| TRQ-005 | Unit | Jitter добавляется к delay | Да |
| TRQ-006 | Unit | PromptResponse содержит attempts и fallback_used | Да |
| TRQ-007 | Unit | ProcessPromptResponse содержит attempts и fallback_used | Да |
| TRQ-008 | Unit | set_availability ошибка не ломает запрос (graceful) | Да |
| TRQ-009 | Smoke | POST /process -> 200 с attempts и fallback_used | Да |
| TRQ-010 | Smoke | Health check -> 200 | Да |

---

## 7. Технические ограничения

### 7.1 Затрагиваемые файлы

| Файл | Изменение |
|------|-----------|
| `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py` | FR-001, FR-002: cooldown в _handle_transient_error(). FR-010: подсчёт attempts и fallback_used. Вызов retry_with_exponential_backoff |
| `services/free-ai-selector-business-api/app/application/services/retry_service.py` | FR-003, FR-004: exponential backoff, MAX_RETRIES=3. FR-021: deprecated alias |
| `services/free-ai-selector-business-api/app/domain/models.py` | FR-010: добавить attempts и fallback_used в PromptResponse |
| `services/free-ai-selector-business-api/app/api/v1/schemas.py` | FR-011: добавить attempts и fallback_used в ProcessPromptResponse |
| `services/free-ai-selector-business-api/app/api/v1/prompts.py` | FR-011: проброс attempts и fallback_used в HTTP response |

### 7.2 Env-переменные

| Переменная | Default | Описание |
|------------|---------|----------|
| `AUTH_ERROR_COOLDOWN_SECONDS` | 86400 | Cooldown для AuthenticationError (401/402/403) |
| `VALIDATION_ERROR_COOLDOWN_SECONDS` | 86400 | Cooldown для ValidationError (400/404/422) |
| `MAX_RETRIES` | 3 (было 10) | Максимум retry-попыток |
| `RETRY_BASE_DELAY` | 2.0 | Базовая задержка для exponential backoff (сек) |
| `RETRY_MAX_DELAY` | 30.0 | Максимальная задержка retry (сек) |
| `RETRY_JITTER` | 1.0 | Максимальный jitter (сек) |

### 7.3 Ограничения

- Cooldown применяется ко ВСЕМ `AuthenticationError` и `ValidationError`, без различия между временными и постоянными ошибками. Если ключ обновили -- провайдер станет доступен только через 24ч.
- `retry_with_exponential_backoff` заменяет `retry_with_fixed_delay` в вызове из `_generate_with_retry`. Alias `retry_with_fixed_delay` сохраняется для обратной совместимости тестов.
- Data API endpoint `set_availability` уже существует и протестирован в F012. Новых эндпоинтов не требуется.
- Cloudflare провайдер (свой `generate()`) не затрагивается -- cooldown работает на уровне use case, а не провайдера.

---

## 8. Допущения и риски

### 8.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | F022 (этапы 1-3) внедрён и работает: 402 -> AuthenticationError, 404 -> ValidationError, HTTPStatusError пробрасывается | Без F022 ошибки 402/404 остаются generic ProviderError и не триггерят cooldown. F023 FR-001/FR-002 не имеют эффекта |
| 2 | HTTP 401/402/403 от провайдера = постоянная ошибка (невалидный ключ, исчерпан баланс) | Если баланс пополнили, провайдер будет недоступен до 24ч. Можно сбросить cooldown через `set_availability(model_id, 0)` |
| 3 | HTTP 404 = ошибка конфигурации (неверный endpoint/model) | Если провайдер изменил URL и вернул 404 временно, cooldown 24ч избыточен |
| 4 | Data API endpoint set_availability работает корректно | Протестировано в F012. Если Data API недоступен -- cooldown не устанавливается (graceful degradation) |
| 5 | 3 retry достаточно для восстановления после 5xx | При длительном outage провайдера retry не поможет, но fallback loop перейдёт к следующему |

### 8.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение MAX_RETRIES default с 10 на 3 в production | Med | Med | Env-переменная MAX_RETRIES позволяет вернуть старое поведение. Документировать в CHANGELOG |
| 2 | Провайдер обновил ключ, но cooldown 24ч не истёк | Low | Low | Ручной reset через Data API: `set_availability(model_id, 0)`. Документировать в runbook |
| 3 | ValidationError (400/422) от некорректного payload вызывает cooldown провайдера | Med | Med | FR-002 применяет cooldown ко ВСЕМ ValidationError. Можно фильтровать только 404 -- но упрощение предпочтительнее. F022 payload budget снижает вероятность 422 |
| 4 | Jitter недостаточен для предотвращения thundering herd при высокой нагрузке | Low | Low | RETRY_JITTER конфигурируем, можно увеличить |
| 5 | Аддитивные поля в HTTP response ломают клиентов с strict parsing | Low | Low | Pydantic strict mode не используется. Telegram-бот парсит только нужные поля |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Применять ли cooldown к ValidationError 400/422 (некорректный payload), или только к 404? | Resolved | Применять ко всем ValidationError. F022 payload budget снижает риск ложных 422. 400 от провайдера = ошибка конфигурации, cooldown оправдан |
| 2 | Нужна ли отдельная env-переменная для cooldown ValidationError vs AuthenticationError? | Resolved | Да -- `AUTH_ERROR_COOLDOWN_SECONDS` и `VALIDATION_ERROR_COOLDOWN_SECONDS` для гибкости. Оба default 86400 |
| 3 | Сохранять ли retry_with_fixed_delay как deprecated alias? | Resolved | Да (FR-021), для обратной совместимости тестов |
| 4 | Добавлять ли error_type и http_status в успешный response? | Resolved | Нет -- в успешном response только attempts и fallback_used. error_type только при ошибке (FR-012) |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| cooldown | Период времени, в течение которого провайдер исключён из выборки. Реализован через `available_at` в PostgreSQL |
| exponential backoff | Стратегия retry, при которой задержка между попытками удваивается: base * 2^attempt |
| jitter | Случайная добавка к задержке для предотвращения синхронных retry от нескольких клиентов |
| thundering herd | Проблема, когда множество клиентов одновременно повторяют запросы после одинакового таймаута |
| fallback loop | Цикл перебора моделей в `ProcessPromptUseCase.execute()`, где каждая следующая модель пробуется при ошибке предыдущей |
| set_availability | Endpoint Data API для установки cooldown провайдера: `PUT /api/v1/models/{id}/set-availability?seconds=N` |
| telemetry | Метаданные запроса (attempts, fallback_used, error_type), возвращаемые в HTTP response для диагностики |

---

## 11. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-02-25 | AI Analyst | Первоначальная версия |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-001--FR-021, NF-001--NF-022, TRQ-001--TRQ-010, INT-001--INT-003)
- [x] Приоритеты расставлены (Must: FR-001--FR-004, Should: FR-010--FR-012, Could: FR-020--FR-021)
- [x] Критерии приёмки определены для каждого требования
- [x] User stories связаны с требованиями
- [x] Бизнес-пайплайн описан (основной flow, состояния провайдера)
- [x] Data Pipeline описан (не затрагивается, использует существующий set_availability)
- [x] Интеграционный пайплайн описан (INT-001--INT-003)
- [x] Раздел "Влияние на существующие пайплайны" заполнен
- [x] Нет блокирующих открытых вопросов
- [x] Зависимость от F022 явно указана (секция 1.5)
- [x] Риски идентифицированы и имеют план митигации
