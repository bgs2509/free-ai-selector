---
feature_id: "F001"
feature_name: "project-cleanup-audit"
title: "Аудит и очистка проекта Free AI Selector"
created: "2025-12-23"
author: "AI (Researcher)"
type: "_research"
status: "RESEARCH_DONE"
version: 1
migrated_from: "project-cleanup-audit-_research.md"
migrated_at: "2025-12-23"
---
# Отчёт исследования: Аудит и очистка проекта

**Версия**: 1.0
**Дата**: 2025-12-23
**Автор**: AI Agent (Исследователь)
**Статус**: Завершён
**Связанный PRD**: `ai-docs/docs/_analysis/2025-12-23_F001_project-cleanup-audit-_analysis.md`

---

## 1. Резюме исследования

Проведена верификация всех функциональных требований из PRD. Все 7 FR подтверждены с конкретными доказательствами.

| Требование | Статус | Доказательство |
|------------|--------|----------------|
| FR-001: shared/ не используется | **ПОДТВЕРЖДЕНО** | `grep "from shared\|import shared"` = пусто |
| FR-002: PROMPT_FOR_AI_GENERATION.md устарел | **ПОДТВЕРЖДЕНО** | Ссылки на `.ai-framework/` — не существует |
| FR-003: README.md ссылки | **ПОДТВЕРЖДЕНО** | 7 ссылок на `.ai-framework/` (строки 7,8,257,334,350,365,366,372) |
| FR-004: is_sensitive_key_present() мёртвый код | **ПОДТВЕРЖДЕНО** | Определена 4 раза, вызовов = 0 |
| FR-005: Decimal import | **ПОДТВЕРЖДЕНО** | Строка 21 в health_worker/main.py, не используется |
| FR-006: дублирующиеся импорты | **ПОДТВЕРЖДЕНО** | models.py строки 99-100, 181, 219 |
| FR-007: deploy.sh | **АКТУАЛЕН** | Использует современный `docker compose` |

---

## 2. Анализ архитектуры

### 2.1 Структура проекта

```
free-ai-selector/
├── services/                      # 5 микросервисов ✅
│   ├── free-ai-selector-business-api/    # FastAPI, DDD/Hexagonal ✅
│   ├── free-ai-selector-data-postgres-api/ # FastAPI, DDD ✅ (⚠ без Application слоя)
│   ├── free-ai-selector-telegram-bot/    # Aiogram ⚠ (монолит в main.py)
│   ├── free-ai-selector-health-worker/   # APScheduler ✅
│   └── free-ai-selector-nginx/           # Reverse proxy ✅
├── shared/                        # ❌ НЕ ИСПОЛЬЗУЕТСЯ — удалить
├── ai-docs/                       # AIDD артефакты ✅
├── .aidd/                         # Фреймворк (submodule) ✅
├── PROMPT_FOR_AI_GENERATION.md    # ❌ УСТАРЕЛ — удалить
├── deploy.sh                      # ✅ АКТУАЛЕН
└── docker-compose.yml             # ✅ АКТУАЛЕН
```

### 2.2 Выявленные паттерны

| Паттерн | Сервисы | Соответствие |
|---------|---------|--------------|
| DDD/Hexagonal | business_api, data_api, health_worker | ✅ Полное |
| DDD/Hexagonal | telegram_bot | ❌ Нарушено (монолит) |
| HTTP-only доступ к данным | Все | ✅ Полное |
| Async/await | Все | ✅ Полное |
| Type hints | Все | ✅ Полное |

### 2.3 Зависимости между модулями

```
telegram_bot ──HTTP──▶ business_api ──HTTP──▶ data_api ──SQL──▶ PostgreSQL
                              ▲
health_worker ───────────────┘
```

Все сервисы корректно изолированы. Прямого доступа к БД из бизнес-сервисов нет.

---

## 3. Детальный анализ мёртвого кода

### 3.1 Директория shared/

```
shared/
├── utils/
│   ├── __init__.py    # Пустой файл
│   └── security.py    # 155 строк — дубликат
```

**Доказательство неиспользования:**
```bash
$ grep -r "from shared\|import shared" .
# Результат: пусто (кроме PRD-документа)
```

**Вывод**: Каждый сервис содержит локальную копию `app/utils/security.py`. Директория `shared/` — артефакт неудачной попытки централизации.

### 3.2 Функция is_sensitive_key_present()

**Местоположение** (4 файла):
- `services/free-ai-selector-business-api/app/utils/security.py:121`
- `services/free-ai-selector-data-postgres-api/app/utils/security.py:121`
- `services/free-ai-selector-telegram-bot/app/utils/security.py:121`
- `services/free-ai-selector-health-worker/app/utils/security.py:121`

**Вызовы функции**: 0

**Причина мёртвого кода**: Функция была реализована для будущего использования, но никогда не интегрирована. Присутствует только в docstring-примерах.

### 3.3 Неиспользуемый импорт Decimal

**Файл**: `services/free-ai-selector-health-worker/app/main.py`
**Строка**: 21

```python
from decimal import Decimal  # ← Не используется
```

**Причина**: Импорт добавлен при создании, но функционал вычислений использует `float`.

### 3.4 Дублирующиеся локальные импорты

**Файл**: `services/free-ai-selector-data-postgres-api/app/api/v1/models.py`

| Строка | Содержимое | Проблема |
|--------|------------|----------|
| 99-100 | `from datetime import datetime; from decimal import Decimal` | Локальный импорт внутри функции |
| 181 | `from decimal import Decimal` | Дублирует строку 100 |
| 219 | `from decimal import Decimal` | Дублирует строку 100 |

**Рекомендация**: Переместить импорты на уровень модуля (начало файла).

---

## 4. Архитектурные проблемы (Future scope)

### 4.1 Telegram Bot — нарушение DDD

| Метрика | Значение |
|---------|----------|
| Файлов кода | 1 (main.py) |
| Строк кода | 411 |
| Тестовое покрытие | 0% |
| Слой api/ | Отсутствует |
| Слой application/ | Отсутствует |
| Слой domain/ | Отсутствует |
| Слой infrastructure/ | Пустая директория |

**Рекомендация**: Отложить рефакторинг — требует значительных усилий и не входит в scope текущей очистки.

### 4.2 Data API — отсутствие Application слоя

Бизнес-логика находится непосредственно в HTTP routes (`app/api/v1/models.py`). Отсутствует слой `application/use_cases/`.

**Рекомендация**: Отложить — не критично для текущего уровня зрелости (Level 2).

### 4.3 Дублирование security.py

| Сервис | Размер |
|--------|--------|
| business_api | 155 строк |
| data_api | 155 строк |
| telegram_bot | 155 строк |
| health_worker | 155 строк |
| **Итого дублирования** | **620 строк** |

**Рекомендация**: Сохранить дублирование — соответствует принципу независимости микросервисов.

---

## 5. Файлы для проверки (дополнительно)

| Файл | Статус | Рекомендация |
|------|--------|--------------|
| `API_EXAMPLES.md` | ✅ Актуален | Сохранить |
| `API_KEY_SETUP_GUIDE.md` | ✅ Актуален | Сохранить |
| `DEVELOPMENT.md` | ⚠ Требует проверки | Проверить актуальность команд |

---

## 6. План очистки (подтверждённый)

### Этап 1: Удаление файлов (низкий риск)

| # | Действие | Риск |
|---|----------|------|
| 1 | `rm -rf shared/` | Низкий |
| 2 | `rm PROMPT_FOR_AI_GENERATION.md` | Низкий |

### Этап 2: Редактирование документации (низкий риск)

| # | Действие | Риск |
|---|----------|------|
| 3 | README.md: заменить `.ai-framework/` → `.aidd/` | Низкий |

### Этап 3: Очистка кода (низкий-средний риск)

| # | Действие | Риск |
|---|----------|------|
| 4 | Удалить `is_sensitive_key_present()` из 4 файлов | Низкий |
| 5 | Удалить `from decimal import Decimal` в health_worker | Низкий |
| 6 | Исправить дублирующиеся импорты в models.py | Средний |

### Этап 4: Верификация (обязательно)

| # | Действие |
|---|----------|
| 7 | `make test` — все тесты |
| 8 | `make lint` — проверка качества |
| 9 | `make build && make health` — проверка здоровья |

---

## 7. Технические ограничения

1. **Нельзя удалять локальные копии security.py** — используется функция `sanitize_error_message()`
2. **Нельзя менять HTTP-only паттерн** — ключевой архитектурный принцип
3. **Рефакторинг Telegram Bot требует отдельного PRD** — объём работы ~2-3 дня

---

## 8. Качественные ворота: RESEARCH_DONE

| Критерий | Статус |
|----------|--------|
| Код проанализирован | ✅ |
| Архитектурные паттерны выявлены | ✅ |
| Технические ограничения определены | ✅ |
| Рекомендации сформулированы | ✅ |
| Риски идентифицированы | ✅ |

**Результат**: ✅ RESEARCH_DONE — ворота пройдены

---

## 9. Следующий шаг

```bash
/aidd-feature-plan    # Создать план реализации очистки
```

---

**Статус документа**: Завершён
**Следующий этап**: `/aidd-feature-plan`
