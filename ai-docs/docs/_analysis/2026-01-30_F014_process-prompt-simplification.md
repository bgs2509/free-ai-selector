---
feature_id: "F014"
feature_name: "process-prompt-simplification"
title: "Упрощение ProcessPromptUseCase: Error Handling Consolidation"
created: "2026-01-30"
author: "AI (Analyst)"
type: "prd"
status: "PRD_READY"
version: 1
mode: "FEATURE"

related_features: [F012, F013]
services: [free-ai-selector-business-api]
requirements_count: 4

pipelines:
  business: true
  data: false
  integration: false
  modified: [process_prompt]
---

# PRD: Упрощение ProcessPromptUseCase (Error Handling Consolidation)

**Feature ID**: F014
**Версия**: 1.0
**Дата**: 2026-01-30
**Автор**: AI Agent (Аналитик)
**Статус**: PRD_READY
**Тип**: Рефакторинг (Quality Cascade QC-2/KISS, QC-4/SRP)

---

## 1. Обзор

### 1.1 Проблема

В файле `process_prompt.py` метод `execute()` содержит **5 отдельных except блоков** с почти идентичной логикой:

```python
# Строки 177-301 — ~125 строк error handling

except RateLimitError as e:
    # Логика A: _handle_rate_limit()

except (ServerError, TimeoutError) as e:
    # Логика B: _handle_transient_error()

except (AuthenticationError, ValidationError) as e:
    # Логика B: _handle_transient_error() — ИДЕНТИЧНА!

except ProviderError as e:
    # Логика B: _handle_transient_error() — ИДЕНТИЧНА!

except Exception as e:
    # classify() + Логика A или B
```

**Проблемы:**
- **Цикломатическая сложность `execute()`**: ~25-30 (рекомендуется < 10)
- **Дублирование**: 3 блока с идентичной "Логикой B"
- **Сложность понимания**: требуется несколько проходов чтения
- **F012 усугубил проблему**: добавил rate limit handling, увеличив сложность

### 1.2 Решение

Консолидировать error handling в **2 приватных метода**:

```python
async def _handle_rate_limit(self, provider: str, error: RateLimitError) -> None:
    """Обработка rate limit: cooldown + retry."""
    pass

async def _handle_transient_error(self, provider: str, error: Exception) -> None:
    """Обработка временных ошибок: log + fallback."""
    pass
```

**После рефакторинга:**
```python
try:
    result = await provider.generate(prompt, ...)
except RateLimitError as e:
    await self._handle_rate_limit(provider_name, e)
except (ServerError, TimeoutError, AuthenticationError, ValidationError, ProviderError) as e:
    await self._handle_transient_error(provider_name, e)
except Exception as e:
    error_type = self.error_classifier.classify(e)
    if error_type == ErrorType.RATE_LIMIT:
        await self._handle_rate_limit(provider_name, e)
    else:
        await self._handle_transient_error(provider_name, e)
```

### 1.3 Целевая аудитория

| Сегмент | Описание | Потребности |
|---------|----------|-------------|
| Разработчики | Те кто поддерживает код | Читаемость, низкая сложность |
| QA | Те кто тестирует | Предсказуемое поведение |

### 1.4 Ценностное предложение

- **Цикломатическая сложность**: ~25 → ~15
- **Строк кода**: ~125 → ~50 (error handling)
- **Читаемость**: один проход чтения

---

## 2. Функциональные требования

### 2.1 Core Features (Must Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-001 | _handle_rate_limit() | Приватный метод для обработки rate limit | Метод существует, вызывается из execute() |
| FR-002 | _handle_transient_error() | Приватный метод для обработки временных ошибок | Метод существует, вызывается из execute() |
| FR-003 | Консолидация except | Объединить 3 идентичных блока в один | Один except для ServerError, TimeoutError, Auth, Validation, Provider |
| FR-004 | Сохранить поведение | Результат работы должен быть идентичен | Все тесты проходят без изменений |

### 2.2 Important Features (Should Have)

| ID | Название | Описание | Критерий приёмки |
|----|----------|----------|------------------|
| FR-010 | Типизация | Полные type hints для методов | mypy проходит |
| FR-011 | Docstrings | Google-style docstrings | Методы задокументированы |

---

## 3. User Stories

### US-001: Разработчик читает execute()

**Как** разработчик
**Я хочу** понять логику execute() за один проход
**Чтобы** быстрее находить и исправлять баги

**Критерии приёмки:**
- [ ] Цикломатическая сложность < 20
- [ ] Error handling вынесен в приватные методы
- [ ] Основной flow читается линейно

**Связанные требования:** FR-001, FR-002, FR-003

---

## 4. Пайплайны

### 4.0 Тип изменений

| Параметр | Значение |
|----------|----------|
| Режим | FEATURE (рефакторинг) |
| Затрагиваемые пайплайны | process_prompt (application layer) |

### 4.1 Бизнес-пайплайн

**Текущий flow (без изменений):**
```
Request → Select Provider → Generate → Handle Error → Fallback → Response
```

Рефакторинг не меняет бизнес-логику, только структуру кода.

### 4.4 Влияние на существующие пайплайны

**Режим:** FEATURE (рефакторинг)

| Пайплайн | Тип изменения | Обратная совместимость |
|----------|---------------|------------------------|
| process_prompt | modify (internal) | Да |

**Breaking changes:**
- [x] Нет breaking changes

---

## 5. UI/UX требования

Не применимо — backend рефакторинг.

---

## 6. Нефункциональные требования

### 6.1 Код качество

| ID | Метрика | Требование | Измерение |
|----|---------|------------|-----------|
| NF-001 | Cyclomatic complexity | < 20 (было ~25-30) | radon |
| NF-002 | Lines in execute() | < 150 (было ~200) | wc -l |

### 6.5 Требования к тестированию

| ID | Тип | Требование | Обязательно |
|----|-----|-----------|-------------|
| TRQ-001 | Regression | Все существующие тесты проходят | ✅ Да |
| TRQ-002 | Unit | Тесты для _handle_rate_limit() | ✅ Да |
| TRQ-003 | Unit | Тесты для _handle_transient_error() | ✅ Да |

---

## 7. Технические ограничения

### 7.1 Файлы для изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `process_prompt.py` | Modify | Рефакторинг execute(), добавление приватных методов |

### 7.2 Зависимости

- Зависит от F013: После консолидации провайдеров error types могут измениться
- Связан с F012: Использует ErrorClassifier и RetryService

---

## 8. Допущения и риски

### 8.1 Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|------|-------------|---------|-----------|
| 1 | Изменение поведения | Low | High | 100% покрытие тестами |
| 2 | Конфликт с F012 | Med | Med | Выполнять после F012 merge |

---

## 9. Открытые вопросы

| # | Вопрос | Статус | Решение |
|---|--------|--------|---------|
| 1 | Выполнять до или после F013? | Resolved | После F013 — меньше конфликтов |

---

## Качественные ворота

### PRD_READY Checklist

- [x] Все секции заполнены
- [x] Требования имеют уникальные ID
- [x] Критерии приёмки определены
- [x] Риски идентифицированы

---

## Ожидаемый результат

**До рефакторинга:**
```
execute(): ~200 строк, сложность ~25-30
5 отдельных except блоков
```

**После рефакторинга:**
```
execute(): ~120 строк, сложность ~15
2 приватных метода для error handling
```
