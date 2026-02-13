# План фичи: F020 — Web UI выбор конкретной модели (Stage 1)

**Feature ID**: F020
**Дата**: 2026-02-13
**Статус**: Approved
**Режим**: FEATURE
**Связанные артефакты**:
- PRD: `_analysis/2026-02-13_F020_web-model-selection-stage1.md`
- Research: `_research/2026-02-13_F020_web-model-selection-stage1.md`

---

## 1. Обзор

Добавляем в Web UI режим выбора модели для одного запроса:
- `Авто` (по умолчанию, без `model_id`);
- `Конкретная` (отправка `model_id`).

Ключевые правила Stage 1:
- список для ручного выбора загружается из `/api/v1/models/stats`;
- в список попадают только модели с `is_active=true` и `reliability_score > 0.4`;
- в label каждой модели показывается score числом (`0.90`);
- если список пуст или произошла ошибка загрузки, UI показывает ошибку и автоматически переключается в `Авто`.

### 1.1 Scope

**В scope:**
- изменения только в `services/free-ai-selector-business-api/app/static/index.html`;
- расширение UI (HTML/CSS/JS) для выбора модели;
- передача `model_id` в `POST /api/v1/prompts/process` только в ручном режиме;
- сохранение текущей поддержки `system_prompt` и `response_format`.

**Вне scope:**
- Telegram bot;
- пользовательские настройки (persisted default model);
- изменения Business API/Data API контрактов и БД;
- новые внешние зависимости.

---

## 2. Анализ существующего кода

### 2.1 Затронутые сервисы

| Сервис | Изменение | Комментарий |
|--------|-----------|-------------|
| `free-ai-selector-business-api` | Да | Только статический Web UI файл |
| `free-ai-selector-telegram-bot` | Нет | Явно исключено из scope |
| `free-ai-selector-data-postgres-api` | Нет | Переиспользуются существующие endpoint-ы |

### 2.2 Точки интеграции

| Точка | Текущее состояние | План |
|-------|-------------------|------|
| `index.html` чат-форма | Есть `prompt`, `system_prompt`, `response_format` | Добавить `model mode` + `model select` |
| `sendPrompt()` | Отправляет payload без `model_id` | Добавить условную отправку `model_id` |
| `GET /api/v1/models/stats` | Используется для вкладки рейтинга | Переиспользовать для model selector |
| Backend `POST /prompts/process` | Уже поддерживает `model_id` | Без изменений backend |

### 2.3 Существующие зависимости

| Зависимость | Использование | Изменения |
|-------------|---------------|-----------|
| `apiCall()` | Универсальный fetch helper | Переиспользуется |
| `show()/hide()/showError()` | UI-state helpers | Переиспользуются |
| `/api/v1/models/stats` | Источник моделей | Переиспользуется с клиентской фильтрацией |
| `/api/v1/prompts/process` | Обработка prompt | Переиспользуется, добавляется `model_id` |

---

## 3. План изменений

### Шаг 1: Добавить UI-контролы выбора модели

**Файл**: `services/free-ai-selector-business-api/app/static/index.html`

Добавить в чат-секцию:
- radio group `name="model-mode"` со значениями `auto` (default) и `manual`;
- контейнер `model-select-wrapper` (скрыт при `auto`);
- `<select id="model-select">` для моделей;
- кнопку обновления списка моделей;
- отдельный `model-error` для ошибок manual-режима.

### Шаг 2: Добавить JS-логику загрузки и фильтрации моделей

**Файл**: `services/free-ai-selector-business-api/app/static/index.html`

Добавить константы и функции:
- `MANUAL_MODEL_MIN_SCORE = 0.4`;
- `loadManualModelOptions()`:
  1. запрос `GET /api/v1/models/stats`;
  2. фильтрация `is_active && reliability_score > 0.4`;
  3. сортировка по `reliability_score` убыванию;
  4. рендер опций с текстом `"{name} ({provider}) — score: {score.toFixed(2)}"`.
- `setAutoModeWithError(message)`:
  - показать ошибку;
  - программно переключить режим в `auto`;
  - скрыть/очистить manual UI.
- `initModelSelector()`:
  - подписка на переключение режима;
  - ленивый first-load списка при выборе `manual`;
  - кнопка refresh.

### Шаг 3: Расширить отправку payload в `sendPrompt()`

**Файл**: `services/free-ai-selector-business-api/app/static/index.html`

Поведение:
- если режим `auto`: payload без `model_id`;
- если режим `manual`:
  - требуется выбранная валидная модель (`model_id > 0`), иначе ошибка;
  - добавляется `payload.model_id = selectedModelId`.
- текущая логика `system_prompt` и `response_format` сохраняется без изменений.

### Шаг 4: Добавить CSS для новых элементов

**Файл**: `services/free-ai-selector-business-api/app/static/index.html`

Добавить компактные классы для:
- model selector блока;
- select-control;
- mobile адаптации (не ломать layout на узком экране).

### Шаг 5: Валидация результата (manual smoke)

Проверить вручную:
1. Auto mode отправляет prompt без `model_id`.
2. Manual mode отправляет `model_id`.
3. В manual списке только `is_active=true && score>0.4`.
4. В каждой опции виден score в формате `0.90`.
5. Пустой список переключает в `Авто` + показывает ошибку.
6. Ошибка загрузки stats переключает в `Авто` + показывает ошибку.
7. `system_prompt`/`response_format` работают в обоих режимах.

---

## 4. API контракт

### 4.1 Request

`POST /api/v1/prompts/process`

**Было (Web):**
```json
{
    "prompt": "...",
    "system_prompt": "...",
    "response_format": {"type": "json_object"}
}
```

**Станет (manual mode):**
```json
{
    "prompt": "...",
    "model_id": 7,
    "system_prompt": "...",
    "response_format": {"type": "json_object"}
}
```

**Станет (auto mode):**
```json
{
    "prompt": "...",
    "system_prompt": "...",
    "response_format": {"type": "json_object"}
}
```

### 4.2 Response

Без изменений.

---

## 5. Breaking changes и миграции

- Breaking changes: **нет**.
- Миграции БД: **не требуются**.
- Новые зависимости: **не требуются**.

---

## 6. План интеграции

| # | Шаг | Зависимости | Результат |
|---|-----|-------------|-----------|
| 1 | HTML UI controls | — | Появился режим `Авто/Конкретная` |
| 2 | JS load/filter logic | Шаг 1 | Ручной список моделей с фильтром `>0.4` и score |
| 3 | Payload update in `sendPrompt()` | Шаг 2 | `model_id` отправляется только в manual режиме |
| 4 | CSS/mobile update | Шаги 1-3 | Корректная верстка desktop/mobile |
| 5 | Manual smoke validation | Шаги 1-4 | Подтверждена обратная совместимость и UX-правила |

---

## 7. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| После фильтра `>0.4` нет моделей | Medium | Ошибка + автопереход в `Авто` |
| Кратковременный сбой `/models/stats` | Medium | Ошибка + автопереход в `Авто`, кнопка refresh |
| Непрозрачное поведение для пользователя | Medium | Явное сообщение о переключении в `Авто` |
| Регрессия существующих advanced params | Low | Отдельный smoke сценарий для `system_prompt/response_format` |

---

## 8. Проверки готовности к `aidd-code`

- [x] Интеграция с существующим кодом описана
- [x] Изменения ограничены одним сервисом и одним файлом
- [x] Обратная совместимость описана
- [x] Риски и валидационный план определены
- [x] План-файл создан в правильной папке (`_plans/features/`)
- [x] План утверждён пользователем

---

## 9. Следующий шаг

После утверждения плана:

```bash
/aidd-code
```
