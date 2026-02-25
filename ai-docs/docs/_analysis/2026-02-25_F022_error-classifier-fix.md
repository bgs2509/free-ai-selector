---
feature_id: "F022"
feature_name: "error-classifier-fix"
title: "Исправление классификации ошибок LLM-провайдеров и защита от больших payload"
created: "2026-02-25"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 1
mode: "FEATURE"

related_features: [F012, F013]
services: [free-ai-selector-business-api]
requirements_count: 7

pipelines:
  business: true
  data: false
  integration: true
  modified: [error-classification, provider-failover, payload-validation]
---

# PRD: Исправление классификации ошибок LLM-провайдеров и защита от больших payload

**Feature ID**: F022
**Версия**: 1.0
**Дата**: 2026-02-25
**Автор**: AI Agent (Аналитик)
**Статус**: Approved

---

## 1. Обзор

### 1.1 Проблема

При массовом прогоне LLM-запросов (3686 запросов, 2026-02-24) зафиксирован **66% error rate**. Анализ prod-логов выявил три корневых причины:

1. **Потеря HTTP-кода в провайдерах**: `OpenAICompatibleProvider.generate()` оборачивает `httpx.HTTPStatusError` в generic `ProviderError`, теряя HTTP status code. После этого `classify_error()` не может правильно классифицировать ошибку — она всегда остаётся generic `ProviderError`.

2. **Отсутствие классификации HTTP 402/404**: `classify_error()` не обрабатывает коды 402 (Payment Required) и 404 (Not Found). 8 из 13 провайдеров возвращают именно эти коды (DeepSeek 402, HuggingFace 402, Hyperbolic 402, Fireworks 404, Novita 404, OpenRouter 404, Cerebras 404, Nebius 401). Все они попадают в generic `ProviderError`.

3. **Слишком длинный payload**: Промпты ≥ 7000 символов вызывают 100% ошибок HTTP 422 от провайдеров. Pydantic-схема разрешает до 10 000 символов, но провайдеры не принимают такие длины.

**Масштаб проблемы** (prod-логи за 48ч):
- 12 610 событий `all_models_failed`
- 14 526 бесполезных вызовов к Scaleway (403), 14 481 к Novita (404) и т.д.
- Средняя латентность ошибочных запросов: 4 591 мс (перебор всех мёртвых провайдеров)

### 1.2 Решение

Три точечных исправления в business-api, устраняющих ~70% ошибок:

1. **Не оборачивать HTTPStatusError** — пробрасывать `httpx.HTTPStatusError` напрямую из провайдера, чтобы `classify_error()` мог извлечь HTTP-код.

2. **Расширить classify_error()** — добавить обработку HTTP 402 → `AuthenticationError` и HTTP 404 → `ValidationError`.

3. **Payload budget** — обрезать промпт до 6000 символов перед отправкой провайдеру, с логированием факта обрезки.

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Пользователи Telegram-бота | Отправляют промпты через бот | Быстрый ответ от AI, а не HTTP 500 |
| Пользователи Web UI | Используют веб-интерфейс | Стабильная работа, fallback на рабочие провайдеры |
| Скрипт массового прогона | Пакетная обработка (reclassification) | Минимальный error rate, быстрый failover |

### 1.4 Ценностное предложение

Снижение error rate с ~66% до ожидаемых ~15-20% (остаются только реальные rate limits у рабочих провайдеров). Ускорение failover за счёт немедленного пропуска мёртвых провайдеров вместо retry.

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | Проброс HTTPStatusError из провайдеров | В `OpenAICompatibleProvider.generate()` пробрасывать `httpx.HTTPStatusError` напрямую, не оборачивая в `ProviderError`. Generic `httpx.HTTPError` (сетевые ошибки) оборачивать как раньше. | `httpx.HTTPStatusError` с кодом 404 доходит до `classify_error()` как `httpx.HTTPStatusError`, а не как `ProviderError`. Unit-тест подтверждает. |
| FR-002 | Классификация HTTP 402 | В `classify_error()` добавить ветку: HTTP 402 → `AuthenticationError("Payment required: ...")`. | Тест: `classify_error(HTTPStatusError(402))` возвращает `AuthenticationError`. |
| FR-003 | Классификация HTTP 404 | В `classify_error()` добавить ветку: HTTP 404 → `ValidationError("Endpoint/model not found: ...")`. | Тест: `classify_error(HTTPStatusError(404))` возвращает `ValidationError`. |
| FR-004 | Payload budget | Перед отправкой провайдеру обрезать промпт до `MAX_PROMPT_CHARS` (env, default 6000). Логировать `prompt_truncated` warning с `original_length` и `max_length`. | Тест: промпт 8000 символов обрезается до 6000. В логах — `prompt_truncated`. Провайдер получает ≤ 6000 символов. |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-010 | Обработка HTTPStatusError в failover-цикле | В `ProcessPromptUseCase` fallback loop добавить `except httpx.HTTPStatusError` перед `except Exception`, с маршрутизацией через `classify_error()`. | Тест: провайдер бросает `httpx.HTTPStatusError(403)` → failover переходит к следующему провайдеру без retry. |
| FR-011 | Сохранение имени провайдера в ProviderError | При пробросе `httpx.HTTPStatusError` добавить имя провайдера в сообщение ошибки для корректного логирования. | В логах `generation_failed` видно `provider=Scaleway` и `error=403 Forbidden`. |

### 2.3 Nice to Have (Could Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-020 | Обрезка по границе предложения | При truncation обрезать по последнему `.` / `!` / `?` до лимита, а не посимвольно. | Обрезанный промпт заканчивается целым предложением. |

---

## 3. User Stories

### US-001: Быстрый ответ от рабочего провайдера

**Как** пользователь Telegram-бота
**Я хочу** получить ответ от AI за < 10 секунд
**Чтобы** не ждать, пока система перебирает 8 нерабочих провайдеров

**Критерии приёмки:**
- [x] Провайдеры с 401/402/403/404 не ретраятся (non-retryable)
- [x] Failover к следующему провайдеру происходит за < 100 мс после получения ошибки
- [x] В логах видно правильный тип ошибки (AuthenticationError, не ProviderError)

**Связанные требования:** FR-001, FR-002, FR-003, FR-010

### US-002: Длинный промпт не ломает запрос

**Как** скрипт массового прогона
**Я хочу** отправлять промпты любой длины
**Чтобы** не получать HTTP 422 от провайдеров

**Критерии приёмки:**
- [x] Промпт > 6000 символов автоматически обрезается
- [x] В логах фиксируется факт обрезки
- [x] Ответ от провайдера возвращается успешно (200)

**Связанные требования:** FR-004, FR-020

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE |
| Затрагиваемые пайплайны | error-classification, provider-failover, payload-validation |

### 4.1 Бизнес-пайплайн

**Основной flow (изменённый):**

```
[Запрос от клиента]
  → [Валидация Pydantic (prompt ≤ 10000)]
    → [Payload budget: truncate до 6000] ← НОВОЕ (FR-004)
      → [Получить модели из Data API]
        → [Failover loop по моделям]:
           → [generate() → HTTPStatusError пробрасывается] ← ИЗМЕНЕНО (FR-001)
             → [classify_error() → 402=Auth, 404=Validation] ← ИЗМЕНЕНО (FR-002, FR-003)
               → [non-retryable → следующая модель]
                 → [Успех → ответ клиенту]
```

### 4.2 Data Pipeline

Не затрагивается. Data API, PostgreSQL, seed — без изменений.

### 4.3 Интеграционный пайплайн

**Точки интеграции (изменённые):**

| ID | От | К | Изменение |
|----|----|---|-----------|
| INT-001 | Business API | AI Providers | `httpx.HTTPStatusError` пробрасывается напрямую (FR-001) |
| INT-002 | retry_service | error_classifier | Получает `httpx.HTTPStatusError` вместо `ProviderError` (FR-001) |
| INT-003 | process_prompt | error_classifier | Новый `except httpx.HTTPStatusError` (FR-010) |

### 4.4 Влияние на существующие пайплайны

| Пайплайн | Тип изменения | Затрагиваемые этапы | Обратная совместимость |
|----------|---------------|---------------------|------------------------|
| error-classification | modify | classify_error() | Да — новые ветки, старые не меняются |
| provider-failover | modify | generate(), fallback loop | Да — тип исключения меняется, но обработка сохраняется |
| payload-validation | add | execute() | Да — новый шаг до отправки |

**Breaking changes:**
- [x] Нет breaking changes для внешнего API (HTTP контракты не меняются)
- [ ] Внутренний: `generate()` теперь бросает `httpx.HTTPStatusError` вместо `ProviderError` для HTTP-ошибок. Все catch-блоки в `retry_service` и `process_prompt` уже обрабатывают `Exception`, поэтому поведение сохраняется.

---

## 5. UI/UX требования

Не применимо. Изменения внутренние (backend-only).

---

## 6. Нефункциональные требования

### 6.1 Производительность

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Латентность failover при non-retryable | < 100 мс на пропуск мёртвого провайдера | Логи `duration_ms` |
| NF-002 | Общая латентность запроса | < 15 сек (p95) при 3+ рабочих провайдерах | Prod-метрики |
| NF-003 | Error rate при исправных провайдерах | < 20% | Прогон 100 запросов |

### 6.2 Надёжность

| ID | Метрика | Требование |
|----|---------|------------|
| NF-010 | Обратная совместимость API | HTTP-контракт /api/v1/prompts/process не меняется |
| NF-011 | Логирование | Все новые ветки classify_error() логируются через structlog |

### 6.3 Требования к тестированию

#### Smoke тесты (ОБЯЗАТЕЛЬНО)
- [x] Health check отвечает 200
- [x] POST /api/v1/prompts/process с коротким промптом → 200

#### Unit тесты
- **Требуются**: Да
- **Порог покрытия**: ≥ 75%
- **Критические модули**: `error_classifier.py`, `base.py`, `process_prompt.py`

#### Сводная таблица

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Unit | classify_error: HTTP 402 → AuthenticationError | Да |
| TRQ-002 | Unit | classify_error: HTTP 404 → ValidationError | Да |
| TRQ-003 | Unit | OpenAICompatibleProvider пробрасывает HTTPStatusError | Да |
| TRQ-004 | Unit | Payload truncation при > MAX_PROMPT_CHARS | Да |
| TRQ-005 | Unit | Failover: HTTPStatusError → classify → next model | Да |
| TRQ-006 | Smoke | POST /process с prompt 8000 символов → 200 | Да |
| TRQ-007 | Smoke | Health check → 200 | Да |

---

## 7. Технические ограничения

### 7.1 Затрагиваемые файлы

| Файл | Строки | Изменение |
|------|--------|-----------|
| `app/application/services/error_classifier.py` | 56–76 | Добавить ветки 402, 404 |
| `app/infrastructure/ai_providers/base.py` | 174–200 | Разделить except на HTTPStatusError и HTTPError |
| `app/application/use_cases/process_prompt.py` | 78+, 196–219 | Payload budget + HTTPStatusError в fallback |

### 7.2 Ограничения

- Cloudflare провайдер имеет свой `generate()` и не наследует `OpenAICompatibleProvider` — его не затрагиваем (6 ошибок за 48ч, стабилен).
- `MAX_PROMPT_CHARS=6000` — консервативный лимит. Некоторые провайдеры могут принимать больше, но единый порог проще и безопаснее.

---

## 8. Допущения и риски

### 8.1 Допущения

| # | Допущение | Влияние если неверно |
|---|-----------|---------------------|
| 1 | HTTP 402 от провайдера = постоянная ошибка (баланс исчерпан) | Если баланс пополнили, провайдер заработает при следующем запросе (без cooldown) |
| 2 | HTTP 404 = ошибка конфигурации (неверный endpoint/model) | Если провайдер изменил URL, нужно обновить код |
| 3 | 6000 символов достаточно для большинства промптов | Если нет — увеличить через env `MAX_PROMPT_CHARS` |

### 8.2 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Код, ловящий `ProviderError`, не поймает `httpx.HTTPStatusError` | Low | Med | FR-010: явный catch в fallback loop. retry_service уже ловит Exception |
| 2 | Обрезка промпта ухудшает качество ответа AI | Med | Low | Лимит конфигурируем через env; обрезка логируется |
| 3 | Некоторые провайдеры возвращают 404 временно (maintenance) | Low | Low | 404 → ValidationError → non-retryable, но модель не блокируется на 24ч (это в этапе 4, не в F022) |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Нужен ли отдельный `ConfigurationError` для 404? | Resolved | Нет — используем `ValidationError` (уже non-retryable, достаточно) |
| 2 | Обрезать prompt или system_prompt? | Resolved | Только prompt. system_prompt обычно короткий (≤ 5000 по Pydantic) |

---

## 10. Глоссарий

| Термин | Определение |
|--------|-------------|
| classify_error | Функция, преобразующая исключение в типизированный `ProviderError` |
| failover loop | Цикл перебора моделей в `ProcessPromptUseCase.execute()` |
| non-retryable | Ошибка, которую бессмысленно повторять (401, 402, 403, 404, 422) |
| payload budget | Максимальный размер промпта перед отправкой провайдеру |

---

## 11. История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-02-25 | AI Analyst | Первоначальная версия |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID (FR-001–FR-020, NF-001–NF-011, TRQ-001–TRQ-007)
- [x] Критерии приёмки определены для каждого требования
- [x] User stories связаны с требованиями
- [x] Бизнес-пайплайн описан (основной flow)
- [x] Data Pipeline описан (не затрагивается)
- [x] Интеграционный пайплайн описан (INT-001–INT-003)
- [x] Раздел "Влияние на существующие пайплайны" заполнен
- [x] Нет блокирующих открытых вопросов
- [x] Риски идентифицированы и имеют план митигации
