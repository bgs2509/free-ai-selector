# План фичи: F019 — Выбор модели по model_id с fallback на авто-выбор

**Feature ID**: F019
**Дата**: 2026-02-11
**Статус**: Approved
**Режим**: FEATURE
**Связанные артефакты**:
- PRD: `_analysis/2026-02-11_F019_model-id-priority-fallback.md`
- Research: `_research/2026-02-11_F019_model-id-priority-fallback.md`

---

## 1. Обзор

Добавляем в `POST /api/v1/prompts/process` опциональное поле `model_id`.

Целевое поведение:
- если `model_id` задан и модель доступна/сконфигурирована, она пробуется первой;
- если такой модели нет или она не отвечает, используется текущий fallback по остальным моделям;
- если `model_id` не задан, логика выбора остаётся прежней.

### 1.1 Scope

**В scope:**
- расширение API schema и domain DTO;
- изменение `ProcessPromptUseCase` (forced-first + fallback);
- unit-тесты для новых сценариев;
- сохранение обратной совместимости.

**Вне scope:**
- изменение Data API контрактов;
- UI выбора `model_id` в Web/Telegram;
- новые внешние зависимости.

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Изменение | Комментарий |
|--------|-----------|-------------|
| `free-ai-selector-business-api` | Да | Основная реализация фичи |
| `free-ai-selector-data-postgres-api` | Нет | Используются существующие endpoint-ы |
| `free-ai-selector-telegram-bot` | Нет | Опциональное поле, текущие запросы не ломаются |

### 2.2 Точки интеграции

| Точка | Текущее состояние | План |
|-------|-------------------|------|
| `ProcessPromptRequest` | `prompt`, `system_prompt`, `response_format` | добавить `model_id: Optional[int]` |
| `PromptRequest` DTO | без `model_id` | добавить `model_id: Optional[int] = None` |
| `ProcessPromptUseCase.execute` | сортировка по score + fallback | forced-first reorder + существующий fallback |
| История/статистика | пишутся по успешной/ошибочной модели | сохранить текущую семантику |

---

## 3. План изменений

### Шаг 1: Расширить API и DTO

**Файл**: `services/free-ai-selector-business-api/app/api/v1/schemas.py`
- Добавить `model_id: Optional[int] = Field(None, gt=0, description=...)` в `ProcessPromptRequest`.

**Файл**: `services/free-ai-selector-business-api/app/domain/models.py`
- Добавить `model_id: Optional[int] = None` в `PromptRequest`.

**Файл**: `services/free-ai-selector-business-api/app/api/v1/prompts.py`
- Пробросить `model_id=prompt_data.model_id` в `PromptRequest(...)`.

### Шаг 2: Реализовать forced-first selection в use case

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

Добавить helper, например:

```python
    def _build_candidate_models(
        self,
        sorted_models: list[AIModelInfo],
        requested_model_id: Optional[int],
    ) -> list[AIModelInfo]:
        """Собрать список кандидатов: forced-first, затем остальные без дубликатов."""
```

Алгоритм:
1. если `requested_model_id is None` -> вернуть `sorted_models`;
2. найти `requested` в `sorted_models`;
3. если не найдено -> вернуть `sorted_models`;
4. если найдено -> вернуть `[requested] + [m for m in sorted_models if m.id != requested.id]`.

Интеграция в `execute()`:
- после сортировки сформировать `candidate_models`;
- основной fallback loop выполнять по `candidate_models`.

### Шаг 3: Логирование решений выбора

**Файл**: `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`

Добавить structured-логи (через `log_decision`/`logger`) с полями:
- `requested_model_id`
- `requested_model_found`
- `selection_mode`: `auto | forced_first | forced_not_found`

### Шаг 4: Обновить unit-тесты

**Файл**: `services/free-ai-selector-business-api/tests/unit/test_f011b_schemas.py`
- тест на валидный `model_id`;
- тест на невалидный `model_id=0/-1` (ожидаем `ValidationError`).

**Файл**: `services/free-ai-selector-business-api/tests/unit/test_process_prompt_use_case.py`
- forced модель выбирается первой (даже при меньшем score);
- forced модель отсутствует -> обычный авто-выбор;
- forced модель падает -> fallback на следующую;
- без `model_id` поведение не изменилось;
- F011-B поля сохраняются при forced/fallback.

### Шаг 5: Верификация

- `pytest` таргетно по обновлённым тестам Business API;
- проверка отсутствия регрессии в сценарии без `model_id`.

---

## 4. API контракт

### 4.1 Request

`POST /api/v1/prompts/process`

**Было:**
```json
{
    "prompt": "...",
    "system_prompt": "...",
    "response_format": {"type": "json_object"}
}
```

**Станет:**
```json
{
    "prompt": "...",
    "model_id": 3,
    "system_prompt": "...",
    "response_format": {"type": "json_object"}
}
```

`model_id` — опциональное поле, `> 0`.

### 4.2 Response

Без обязательных изменений (совместимость сохраняется).

---

## 5. Breaking changes и миграции

- Breaking changes: **нет**.
- Миграции БД: **не требуются**.
- Новые зависимости: **не требуются**.

---

## 6. План интеграции

| # | Шаг | Зависимости | Результат |
|---|-----|-------------|-----------|
| 1 | Schema + DTO | — | Контракт поддерживает `model_id` |
| 2 | Use case forced-first | Шаг 1 | Приоритет указанной модели |
| 3 | Логирование решений | Шаг 2 | Наблюдаемость выбора |
| 4 | Unit tests | Шаги 1-3 | Покрытие новых сценариев |
| 5 | Верификация | Шаг 4 | Подтверждение обратной совместимости |

---

## 7. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Forced модель не найдена в кандидатах | Medium | fallback на стандартный список |
| Дубли в цепочке кандидатов | Low | дедупликация по `model.id` |
| Регрессия без `model_id` | Low | отдельный regression test |
| Недостаточная диагностика выбора | Medium | structured logging с `selection_mode` |

---

## 8. Проверки готовности к `aidd-code`

- [x] Интеграция с существующим кодом описана
- [x] Изменения ограничены одним сервисом
- [x] Обратная совместимость описана
- [x] Риски и тестовый план определены
- [x] План-файл создан в правильной папке (`_plans/features/`)
- [x] План утверждён пользователем

---

## 9. Следующий шаг

После утверждения плана:

```bash
/aidd-code
```
