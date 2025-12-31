---
feature_id: "F007"
feature_name: "response-time-none-fix"
title: "Исследование бага response_time=None"
created: "2025-12-31"
author: "AI (Researcher)"
type: "research"
status: "RESEARCH_DONE"
version: 1
mode: "FEATURE"

related_prd: "prd/2025-12-31_F007_response-time-none-fix-prd.md"
---

# Research: Исправление бага response_time=None

**Feature ID**: F007
**Версия**: 1.0
**Дата**: 2025-12-31
**Автор**: AI Agent (Researcher)
**Статус**: RESEARCH_DONE

---

## 1. Резюме исследования

### 1.1 Проблема

При выполнении команды `/test` в Telegram боте, статистика ошибок провайдеров не записывается в базу данных из-за бага с передачей `response_time=None`.

### 1.2 Ключевые находки

| Находка | Описание |
|---------|----------|
| **Корневая причина** | `dict.get(key, default)` возвращает `None` когда ключ присутствует со значением `None`, а не `default` |
| **Затронутый файл** | `test_all_providers.py` — строки 232 и 241 |
| **Health-worker** | НЕ затронут — использует прямое значение переменной, не `dict.get()` |
| **Telegram bot** | НЕ затронут — не обновляет статистику напрямую |
| **Правильный паттерн** | Уже существует в том же файле на строке 123 |

### 1.3 Рекомендуемое решение

```python
# Было (строки 232, 241):
response_time = test_result.get("response_time", 0.0)  # ❌ Вернёт None!

# Должно быть:
response_time = test_result.get("response_time") or 0.0  # ✅ Вернёт 0.0 если None
```

---

## 2. Анализ кода

### 2.1 Место инициализации бага

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/test_all_providers.py`

```python
# Строки 168-174: Инициализация result dict
result = {
    "provider": provider_name,
    "model": model_name,
    "status": "unknown",
    "response_time": None,  # ← Ключ присутствует со значением None
    "error": None,
}
```

### 2.2 Место проявления бага

```python
# Строка 232: success branch
if test_result["status"] == "success":
    response_time = test_result.get("response_time", 0.0)  # ❌ Вернёт None если тест не успешен
    await self.data_api_client.increment_success(
        model_id=model["id"],
        response_time=response_time,  # ← Передаёт None
    )

# Строка 241: failure branch
else:
    response_time = test_result.get("response_time", 0.0)  # ❌ Вернёт None если ключ есть с None
    await self.data_api_client.increment_failure(
        model_id=model["id"],
        response_time=response_time,  # ← Передаёт None
    )
```

### 2.3 Правильный паттерн в том же файле

```python
# Строка 123: Уже используется правильный паттерн!
fastest = min(
    successful_results,
    key=lambda r: r.get("response_time") or float("inf")  # ✅ Корректная обработка None
)
```

### 2.4 Health-worker НЕ затронут

**Файл**: `services/free-ai-selector-health-worker/app/main.py`

```python
# Строка 624: Прямое использование переменной из tuple
is_healthy, response_time = await check_func(endpoint)

# Строки 643, 655: Передача напрямую
async with httpx.AsyncClient(timeout=10.0) as client:
    await client.post(
        f"{DATA_API_URL}/api/v1/models/{model_id}/increment-success",
        params={"response_time": response_time}  # ← Прямое значение, не dict.get()
    )
```

В health-worker `response_time` — это float, возвращаемый из функций `check_*()`, а не значение из словаря.

---

## 3. Поиск по кодовой базе

### 3.1 Grep результаты для `response_time`

```bash
# Команда: Grep pattern="response_time"
```

| Файл | Строки | Паттерн | Статус |
|------|--------|---------|--------|
| `test_all_providers.py` | 123 | `r.get("response_time") or float("inf")` | ✅ Корректный |
| `test_all_providers.py` | 172 | `"response_time": None` | ⚠️ Инициализация |
| `test_all_providers.py` | 232, 241 | `test_result.get("response_time", 0.0)` | ❌ Баг |
| `health-worker/main.py` | 624, 643, 655 | `response_time` (прямая переменная) | ✅ OK |
| `telegram-bot/main.py` | 330, 349-350 | `result.get("response_time")` | ✅ OK (не обновляет БД) |

### 3.2 API endpoints для статистики

| Endpoint | Параметр | Валидация |
|----------|----------|-----------|
| `POST /api/v1/models/{id}/increment-success` | `response_time: float` | Обязателен, должен быть float |
| `POST /api/v1/models/{id}/increment-failure` | `response_time: float` | Обязателен, должен быть float |

При передаче пустой строки или None → HTTP 422 Unprocessable Entity.

---

## 4. Объём изменений

### 4.1 Затрагиваемые файлы

| Файл | Изменение | Строки | Сложность |
|------|-----------|--------|-----------|
| `test_all_providers.py` | Fix `dict.get()` pattern | 232, 241 | Минимальная |

### 4.2 Опциональные улучшения

| Файл | Изменение | Описание |
|------|-----------|----------|
| `test_all_providers.py` | Инициализация | Изменить `"response_time": None` на `"response_time": 0.0` (строка 172) |
| `tests/unit/` | Новый тест | Добавить тест для edge case `response_time=None` |

---

## 5. Риски и митигация

### 5.1 Анализ рисков

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Регрессия в других местах | Низкая | Низкое | Grep показал все использования |
| Аналогичный баг в других сервисах | Низкая | Низкое | Health-worker проверен — OK |
| Data API не принимает 0.0 | Минимальная | Низкое | Data API валидирует float, 0.0 — валидный float |

### 5.2 Обратная совместимость

Изменение полностью обратно совместимо:
- API контракт не меняется
- Поведение для успешных тестов не меняется (response_time уже float)
- Поведение для failed тестов исправляется (response_time становится 0.0 вместо None)

---

## 6. Технические решения

### 6.1 Рекомендуемый подход

```python
# Использовать `or` для fallback на 0.0
response_time = test_result.get("response_time") or 0.0
```

### 6.2 Альтернативные подходы

| Подход | Код | Плюсы | Минусы |
|--------|-----|-------|--------|
| `or` operator | `x.get("key") or default` | Простой, идиоматичный | Не различает 0 и None |
| Тернарный | `x.get("key") if x.get("key") is not None else default` | Явный | Verbose |
| Инициализация | `"response_time": 0.0` | Устраняет причину | Может скрыть ошибки |

**Рекомендация**: `or` operator — простой, уже используется в том же файле (строка 123).

---

## 7. Зависимости

### 7.1 Внешние зависимости

Нет новых зависимостей. Изменение использует стандартный Python.

### 7.2 Зависимости от других фич

| Feature | Зависимость | Статус |
|---------|-------------|--------|
| F004 (dynamic-providers-list) | Использует test_all_providers.py | DEPLOYED |
| F006 (aidd-logging) | Добавил structlog в test_all_providers.py | DEPLOYED |

---

## 8. Выводы

### 8.1 Готовность к реализации

| Критерий | Статус |
|----------|--------|
| Причина бага идентифицирована | ✅ |
| Место исправления определено | ✅ |
| Влияние на другие сервисы проверено | ✅ |
| Обратная совместимость подтверждена | ✅ |
| Объём изменений минимален | ✅ |

### 8.2 Рекомендация

**Переходить к `/aidd-feature-plan`**. Исследование завершено, все вопросы из PRD закрыты.

---

## Качественные ворота

### RESEARCH_DONE Checklist

- [x] Причина бага установлена
- [x] Все файлы с паттерном `response_time` проверены
- [x] Health-worker проверен — не затронут
- [x] Telegram bot проверен — не затронут
- [x] Правильный паттерн найден в том же файле
- [x] Объём изменений определён (2 строки)
- [x] Риски оценены и минимальны
- [x] Обратная совместимость подтверждена

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-12-31 | AI Researcher | Первоначальная версия |
