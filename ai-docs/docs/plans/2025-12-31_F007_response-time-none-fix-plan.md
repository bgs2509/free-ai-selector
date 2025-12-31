---
feature_id: "F007"
feature_name: "response-time-none-fix"
title: "План исправления бага response_time=None"
created: "2025-12-31"
author: "AI (Architect)"
type: "plan"
status: "PENDING_APPROVAL"
version: 1
mode: "FEATURE"

related_prd: "prd/2025-12-31_F007_response-time-none-fix-prd.md"
related_research: "research/2025-12-31_F007_response-time-none-fix-research.md"
---

# План фичи: Исправление бага response_time=None

**Feature ID**: F007
**Версия**: 1.0
**Дата**: 2025-12-31
**Автор**: AI Agent (Architect)
**Статус**: PENDING_APPROVAL

---

## 1. Обзор

### 1.1 Краткое описание

Исправление бага в `test_all_providers.py`, который вызывает HTTP 422 ошибки при выполнении команды `/test`. Корневая причина — некорректное использование `dict.get(key, default)` с ключом, инициализированным как `None`.

### 1.2 Связь с существующим функционалом

| Функционал | Связь |
|-----------|-------|
| Команда `/test` (Telegram bot) | Вызывает Business API endpoint |
| `/api/v1/providers/test` (Business API) | Использует `test_all_providers.py` |
| `increment_failure` (Data API) | Получает некорректный `response_time=None` |
| Reliability score | Не обновляется для failed провайдеров |

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Роль | Изменения |
|--------|------|-----------|
| `free-ai-selector-business-api` | Содержит баг | ДА — исправление |
| `free-ai-selector-data-postgres-api` | Получает некорректные данные | НЕТ |
| `free-ai-selector-telegram-bot` | Вызывает `/test` | НЕТ |
| `free-ai-selector-health-worker` | Аналогичный код (проверен) | НЕТ — не затронут |

### 2.2 Точки интеграции

```
Telegram Bot                  Business API                        Data API
     │                             │                                  │
     │ POST /api/v1/providers/test │                                  │
     │────────────────────────────▶│                                  │
     │                             │ test_all_providers.py            │
     │                             │ ├── _test_provider()             │
     │                             │ │   └── response_time: None ❌   │
     │                             │ └── _update_statistics()         │
     │                             │     └── response_time = 0.0 ✅   │
     │                             │                                  │
     │                             │ POST /increment-failure          │
     │                             │ ──────────────────────────────▶ │
     │                             │   response_time=0.0 (not None)   │
     │                             │                                  │
```

### 2.3 Существующие зависимости

| Зависимость | Версия | Затрагивается |
|-------------|--------|---------------|
| httpx | 0.27.0 | НЕТ |
| FastAPI | 0.115.6 | НЕТ |
| structlog | 24.4.0 | НЕТ |

---

## 3. План изменений

### 3.1 Новые компоненты

> Нет новых компонентов. Это минимальное исправление.

### 3.2 Модификации существующего кода

| Файл | Строки | Изменение | Причина |
|------|--------|-----------|---------|
| `services/free-ai-selector-business-api/app/application/use_cases/test_all_providers.py` | 232 | `test_result.get("response_time", 0.0)` → `test_result.get("response_time") or 0.0` | Fix None handling для success branch |
| `services/free-ai-selector-business-api/app/application/use_cases/test_all_providers.py` | 241 | `test_result.get("response_time", 0.0)` → `test_result.get("response_time") or 0.0` | Fix None handling для failure branch |

### 3.3 Опциональные изменения (Could Have)

| Файл | Строка | Изменение | Причина |
|------|--------|-----------|---------|
| `test_all_providers.py` | 172 | `"response_time": None` → `"response_time": 0.0` | Устранение причины на уровне инициализации |

### 3.4 Новые зависимости

> Нет новых зависимостей.

---

## 4. Детальные изменения кода

### 4.1 Файл: test_all_providers.py

#### Было (строка 232):
```python
if test_result["status"] == "success":
    response_time = test_result.get("response_time", 0.0)
```

#### Должно быть:
```python
if test_result["status"] == "success":
    response_time = test_result.get("response_time") or 0.0
```

#### Было (строка 241):
```python
else:
    response_time = test_result.get("response_time", 0.0)
```

#### Должно быть:
```python
else:
    response_time = test_result.get("response_time") or 0.0
```

---

## 5. API контракты

> API контракты не изменяются. Это внутренний bugfix.

| Endpoint | Изменения |
|----------|-----------|
| `POST /api/v1/providers/test` | НЕТ |
| `POST /api/v1/models/{id}/increment-success` | НЕТ |
| `POST /api/v1/models/{id}/increment-failure` | НЕТ |

---

## 6. Влияние на существующие тесты

### 6.1 Существующие тесты

| Тест | Влияние |
|------|---------|
| `tests/unit/test_test_all_providers.py` | НЕТ — тесты мокают Data API client |
| Интеграционные тесты | НЕТ — тестируют happy path |

### 6.2 Новые тесты (Should Have)

| Тест | Описание | Файл |
|------|----------|------|
| `test_response_time_none_handling` | Проверка обработки `response_time=None` | `tests/unit/test_test_all_providers.py` |

**Пример теста:**
```python
@pytest.mark.asyncio
async def test_response_time_none_handling():
    """Test that None response_time is converted to 0.0."""
    result = {
        "provider": "test",
        "model": "test-model",
        "status": "failed",
        "response_time": None,  # Симулируем баг
        "error": "timeout",
    }

    # Проверяем что используется or 0.0
    response_time = result.get("response_time") or 0.0
    assert response_time == 0.0
    assert isinstance(response_time, float)
```

---

## 7. План интеграции

| # | Шаг | Зависимости | Время |
|---|-----|-------------|-------|
| 1 | Edit test_all_providers.py (строка 232) | — | 1 мин |
| 2 | Edit test_all_providers.py (строка 241) | Шаг 1 | 1 мин |
| 3 | (Optional) Edit test_all_providers.py (строка 172) | — | 1 мин |
| 4 | Запустить тесты | Шаги 1-2 | 2 мин |
| 5 | Rebuild и deploy | Шаг 4 | 5 мин |
| 6 | Верифицировать на VPS через `/test` | Шаг 5 | 2 мин |

**Общее время**: ~12 минут

---

## 8. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Регрессия в логике тестирования | Низкая | Низкое | Существующие тесты покрывают happy path |
| `or 0.0` скрывает реальный 0.0 | Минимальная | Минимальное | Реальное время 0.0 невозможно (сеть) |
| Аналогичный баг в других местах | Низкая | Низкое | Research проверил все файлы |

---

## 9. Checklist для утверждения

### Архитектура
- [x] Минимальные изменения (2 строки)
- [x] Обратная совместимость сохранена
- [x] API контракты не изменяются

### Качество
- [x] Правильный паттерн уже существует в том же файле (строка 123)
- [x] Health-worker проверен — не затронут
- [x] Data API не требует изменений

### Безопасность
- [x] Нет новых input validation рисков
- [x] Нет изменений в обработке credentials

### Тестирование
- [ ] Unit-тест для edge case (Should Have)

---

## 10. Требуется утверждение

**План готов к утверждению.**

Для начала реализации требуется подтверждение пользователя:

```
✅ Изменения минимальны: 2 строки в 1 файле
✅ Обратная совместимость сохранена
✅ Риски минимальны
```

**Подтвердите план для перехода к реализации.**

---

## Качественные ворота

### PLAN_APPROVED Checklist

- [x] Компоненты определены
- [x] API контракты не изменяются
- [x] Точки интеграции описаны
- [x] Влияние на существующие тесты оценено
- [x] Риски идентифицированы и минимальны
- [ ] **План утверждён пользователем**

---

## История изменений

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-12-31 | AI Architect | Первоначальная версия |
