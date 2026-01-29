---
feature_id: "F001"
feature_name: "project-cleanup-audit"
title: "План очистки проекта Free AI Selector"
created: "2025-12-23"
author: "AI (Architect)"
type: "plan"
status: "PLAN_APPROVED"
version: 1
_analysis_ref: "_analysis/2025-12-23_F001_project-cleanup-audit-_analysis.md"
_research_ref: "_research/2025-12-23_F001_project-cleanup-audit-_research.md"
---

# План фичи: Аудит и очистка проекта Free AI Selector

**Версия**: 1.0
**Дата**: 2025-12-23
**Автор**: AI Agent (Архитектор)
**Статус**: Утверждён

---

## 1. Обзор

### 1.1 Цель

Удаление мёртвого кода, устаревших файлов и исправление документации без изменения функциональности системы.

### 1.2 Scope

| В scope | Вне scope |
|---------|-----------|
| Удаление неиспользуемых файлов/директорий | Рефакторинг Telegram Bot |
| Удаление мёртвых функций | Изменение архитектуры Data API |
| Исправление ссылок в документации | Консолидация security.py |
| Очистка неиспользуемых импортов | Добавление новых функций |

### 1.3 Принципы

- **Минимизация изменений**: Только удаление мёртвого кода
- **Обратная совместимость**: API и функциональность не меняются
- **Безопасность**: Запуск тестов после каждого этапа

---

## 2. Анализ существующего кода

### 2.1 Затронутые файлы

| # | Файл | Действие | Тип изменения |
|---|------|----------|---------------|
| 1 | `shared/` | Удалить директорию | DELETE |
| 2 | `PROMPT_FOR_AI_GENERATION.md` | Удалить файл | DELETE |
| 3 | `README.md` | Исправить ссылки | EDIT |
| 4 | `services/free-ai-selector-business-api/app/utils/security.py` | Удалить функцию | EDIT |
| 5 | `services/free-ai-selector-data-postgres-api/app/utils/security.py` | Удалить функцию | EDIT |
| 6 | `services/free-ai-selector-telegram-bot/app/utils/security.py` | Удалить функцию | EDIT |
| 7 | `services/free-ai-selector-health-worker/app/utils/security.py` | Удалить функцию | EDIT |
| 8 | `services/free-ai-selector-health-worker/app/main.py` | Удалить импорт | EDIT |
| 9 | `services/free-ai-selector-data-postgres-api/app/api/v1/models.py` | Исправить импорты | EDIT |

### 2.2 Точки интеграции

Фича **не затрагивает** интеграции между сервисами:
- HTTP-коммуникация Business API ↔ Data API: **без изменений**
- Telegram Bot → Business API: **без изменений**
- Health Worker → Business API: **без изменений**

### 2.3 Существующие зависимости

Удаляемый код **не имеет зависимостей**:
- `shared/` — не импортируется ни одним сервисом
- `is_sensitive_key_present()` — функция не вызывается
- `from decimal import Decimal` — импорт не используется

---

## 3. План изменений

### 3.1 Этап 1: Удаление файлов (низкий риск)

| # | Действие | Команда | Риск |
|---|----------|---------|------|
| 1.1 | Удалить директорию shared/ | `rm -rf shared/` | Низкий |
| 1.2 | Удалить PROMPT_FOR_AI_GENERATION.md | `rm PROMPT_FOR_AI_GENERATION.md` | Низкий |

**Верификация**: `git status` — должно показать 2 файла удалены

### 3.2 Этап 2: Редактирование README.md (низкий риск)

**Файл**: `README.md`

**Изменения**:

| Строка | Было | Стало |
|--------|------|-------|
| 7 | `[![Framework](https://img.shields.io/badge/framework-.ai--framework-purple.svg)](.ai-framework/)` | Удалить badge или заменить на `.aidd/` |
| 8 | `[.ai-framework/docs](.ai-framework/docs/)` | `[.aidd/docs](.aidd/docs/)` |
| 257+ | Ссылки на `.ai-framework/` | Заменить на `.aidd/` или удалить |

**Верификация**: `grep -n ".ai-framework" README.md` — должно быть пусто

### 3.3 Этап 3: Удаление мёртвой функции (низкий риск)

**Функция**: `is_sensitive_key_present()`

**Затронутые файлы** (4 шт.):

```
services/free-ai-selector-business-api/app/utils/security.py:121-155
services/free-ai-selector-data-postgres-api/app/utils/security.py:121-155
services/free-ai-selector-telegram-bot/app/utils/security.py:121-155
services/free-ai-selector-health-worker/app/utils/security.py:121-155
```

**Действие**: Удалить функцию `is_sensitive_key_present()` (строки 121-155) из каждого файла

**Верификация**: `grep -r "is_sensitive_key_present" services/` — должно быть пусто

### 3.4 Этап 4: Удаление неиспользуемого импорта (низкий риск)

**Файл**: `services/free-ai-selector-health-worker/app/main.py`

**Изменение**: Удалить строку 21

```python
# Удалить:
from decimal import Decimal
```

**Верификация**: `grep "from decimal import Decimal" services/free-ai-selector-health-worker/app/main.py` — должно быть пусто

### 3.5 Этап 5: Исправление дублирующихся импортов (средний риск)

**Файл**: `services/free-ai-selector-data-postgres-api/app/api/v1/models.py`

**Проблема**: Локальные импорты внутри функций (строки 99-100, 181, 219)

**Решение**:
1. Добавить глобальные импорты в начало файла (если отсутствуют)
2. Удалить локальные импорты внутри функций

**Верификация**:
- `make test-data` — тесты проходят
- `make lint` — нет ошибок линтера

---

## 4. Новые компоненты

**Нет** — фича не добавляет новых компонентов.

---

## 5. Модификации существующего кода

| Файл | Изменение | Строки | Причина |
|------|-----------|--------|---------|
| `README.md` | Заменить/удалить ссылки | 7,8,257,334,350,365,366,372 | FR-003 |
| `security.py` (×4) | Удалить функцию | 121-155 | FR-004 |
| `health_worker/main.py` | Удалить импорт | 21 | FR-005 |
| `data_api/models.py` | Исправить импорты | 99-100,181,219 | FR-006 |

---

## 6. Новые зависимости

**Нет** — фича не добавляет новых зависимостей.

---

## 7. Влияние на существующие тесты

| Сервис | Ожидаемое влияние |
|--------|-------------------|
| Business API | Без изменений — удаляемая функция не тестируется |
| Data API | Возможны изменения из-за импортов — требуется `make test-data` |
| Telegram Bot | Без изменений — тестов нет |
| Health Worker | Без изменений — удаляемый импорт не используется |

**Обязательно**: Запустить `make test` после всех изменений.

---

## 8. План интеграции

| # | Шаг | Команда | Зависимости | Верификация |
|---|-----|---------|-------------|-------------|
| 1 | Удалить shared/ | `rm -rf shared/` | — | `ls shared/` → не существует |
| 2 | Удалить PROMPT_FOR_AI_GENERATION.md | `rm PROMPT_FOR_AI_GENERATION.md` | — | `ls PROMPT_*.md` → не существует |
| 3 | Исправить README.md | Edit | 1,2 | `grep ".ai-framework" README.md` → пусто |
| 4 | Удалить is_sensitive_key_present() | Edit (×4) | — | `grep -r "is_sensitive_key_present" services/` → пусто |
| 5 | Удалить Decimal импорт | Edit | — | `grep "from decimal" health_worker/main.py` → пусто |
| 6 | Исправить импорты в models.py | Edit | — | `make lint` → OK |
| 7 | Запустить тесты | `make test` | 1-6 | Все тесты проходят |
| 8 | Проверить сборку | `make build && make health` | 7 | Все сервисы здоровы |

---

## 9. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Тесты падают после удаления импортов | Низкая | Среднее | Проверить каждый файл отдельно |
| README содержит другие устаревшие ссылки | Средняя | Низкое | Полный аудит ссылок |
| Функция is_sensitive_key_present() используется скрыто | Очень низкая | Среднее | Grep по всему проекту подтвердил отсутствие вызовов |

---

## 10. Критерии приёмки

| # | Критерий | Метод проверки |
|---|----------|----------------|
| 1 | Директория `shared/` удалена | `ls shared/` → не существует |
| 2 | Файл `PROMPT_FOR_AI_GENERATION.md` удалён | `ls PROMPT_*.md` → не существует |
| 3 | Нет ссылок на `.ai-framework/` в README | `grep ".ai-framework" README.md` → пусто |
| 4 | Функция `is_sensitive_key_present()` удалена | `grep -r "is_sensitive_key_present" services/` → пусто |
| 5 | Импорт Decimal удалён из health_worker | `grep "from decimal" health_worker/main.py` → пусто |
| 6 | Дублирующиеся импорты исправлены | `make lint` → OK |
| 7 | Все тесты проходят | `make test` → OK |
| 8 | Сервисы работают | `make health` → OK |

---

## 11. Оценка сложности

| Метрика | Значение |
|---------|----------|
| Файлов для удаления | 3 (shared/utils/__init__.py, shared/utils/security.py, PROMPT_FOR_AI_GENERATION.md) |
| Файлов для редактирования | 6 |
| Строк кода для удаления | ~200 |
| Строк кода для изменения | ~15 |
| Риск регрессии | Низкий |

---

## 12. Чеклист перед реализацией

- [ ] PRD прочитан и понят
- [ ] Research отчёт прочитан и понят
- [ ] Все требования FR-001 — FR-007 учтены
- [ ] План интеграции последовательный
- [ ] Команды верификации определены
- [ ] **План утверждён пользователем**

---

## 13. Качественные ворота: PLAN_APPROVED

| Критерий | Статус |
|----------|--------|
| Точки интеграции определены | ✅ |
| Необходимые изменения описаны | ✅ |
| Потенциальные риски учтены | ✅ |
| План утверждён пользователем | ✅ Утверждён |

---

## 14. Следующий шаг

После утверждения плана:

```bash
/aidd-generate    # Выполнить очистку по плану
```

---

**Статус документа**: Ожидает утверждения
**Требуется**: Явное подтверждение от пользователя
