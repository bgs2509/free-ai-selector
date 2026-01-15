# Research Report: F011-C — Web UI Advanced Parameters

**Feature ID**: F011-C
**Feature Name**: web-ui-advanced-params
**Title**: Веб-интерфейс: System Prompt и JSON Response
**Дата**: 2026-01-15
**Автор**: AI Agent (Researcher)
**Статус**: RESEARCH_DONE

---

## 1. Executive Summary

Проведён анализ веб-интерфейса `index.html` для интеграции параметров `system_prompt` и `response_format`. Backend API уже поддерживает эти параметры (F011-B), требуется только frontend-интеграция.

**Ключевые выводы**:
- Существующий код чистый, vanilla JS без фреймворков
- Форма отправки промпта минималистична и легко расширяема
- Стилизация через CSS Custom Properties (переменные), согласована с дизайн-системой
- Интеграция не требует изменения архитектуры

**Риски**: LOW (только UI-изменения, backend готов)

---

## 2. Анализ существующего кода

### 2.1 Структура файла index.html

| Секция | Строки | Описание |
|--------|--------|----------|
| CSS Variables | 10-22 | Дизайн-система (цвета, шрифты) |
| Layout Styles | 23-198 | Компоненты (карточки, кнопки, формы) |
| HTML Structure | 200-278 | 3 таба: Чат, Рейтинг, Тест |
| JavaScript | 280-425 | API calls, tabs, form handlers |

**Архитектура**: Монолитный HTML с inline CSS и JavaScript, без зависимостей.

### 2.2 Форма отправки промпта (Чат таб)

**Текущая реализация** (строки 213-218):

```html
<div id="chat" class="tab-pane active">
    <textarea id="prompt-input" placeholder="Введите ваш запрос к AI..." rows="4"></textarea>
    <button id="send-btn" class="btn-primary" onclick="sendPrompt()">
        <span id="send-btn-text">Отправить</span>
        <span id="send-btn-loader" class="loader hidden"></span>
    </button>
    <!-- Response boxes -->
</div>
```

**Функция отправки** (строки 327-346):

```javascript
async function sendPrompt() {
    const input = document.getElementById('prompt-input');
    const prompt = input.value.trim();
    if (!prompt) { showError(errorBox, 'Введите текст запроса'); return; }
    // ... UI state management
    try {
        const data = await apiCall('/api/v1/prompts/process', {
            method: 'POST',
            body: JSON.stringify({ prompt })  // ← ТОЛЬКО prompt
        });
        // ... display response
    } catch (e) { showError(errorBox, e.message); }
    finally { /* cleanup */ }
}
```

**Проблема**: Отправляется только `{prompt: str}`, нужно добавить `system_prompt` и `response_format`.

### 2.3 Стилизация

**CSS переменные** (строки 10-22):

```css
:root {
    --primary: #0066ff;
    --primary-hover: #0052cc;
    --bg: #f0f2f5;
    --card-bg: #ffffff;
    --text: #333333;
    --border: #e0e0e0;
    /* ... */
}
```

**Стили textarea** (строки 65-78):

```css
textarea {
    width: 100%;
    padding: 16px;
    border: 2px dashed var(--border);
    border-radius: 8px;
    font-size: 16px;
    resize: vertical;
    min-height: 120px;
    transition: border-color 0.2s;
    margin-bottom: 16px;
}
textarea:focus {
    outline: none;
    border-color: var(--primary);
    border-style: solid;
}
```

**Выводы**:
- Можно переиспользовать существующие стили для нового textarea
- Консистентная дизайн-система, не нужны новые цвета

### 2.4 API Integration

**Функция apiCall** (строки 294-302):

```javascript
async function apiCall(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Ошибка API: ${response.status}`);
    return data;
}
```

**Контракт Backend API** (из PRD, F011-B):

```typescript
// POST /api/v1/prompts/process
interface ProcessPromptRequest {
    prompt: string;
    system_prompt?: string;      // ← NEW
    response_format?: {          // ← NEW
        type: "json_object"
    };
}
```

**Вывод**: `apiCall` уже готова к передаче дополнительных полей.

---

## 3. Зависимости

### 3.1 Backend (F011-B)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| `ProcessPromptRequest` | ✅ DEPLOYED | Поддерживает `system_prompt`, `response_format` |
| Pydantic валидация | ✅ DEPLOYED | `system_prompt: max_length=5000`, `response_format: Optional[dict]` |
| OpenAI Providers | ✅ DEPLOYED | 14 провайдеров поддерживают параметры |

**Проверка**: F011-B находится в статусе `VALIDATE` с воротами `QA_PASSED`.

### 3.2 Frontend (F002 — исходный web-ui)

| Компонент | Использование | Изменения |
|-----------|---------------|-----------|
| `index.html` | Основной файл | ✏️ Расширить форму чата |
| CSS Custom Properties | Переиспользовать | ✅ Без изменений |
| JavaScript functions | `sendPrompt()` | ✏️ Добавить новые поля в payload |
| API Base Path | `API_BASE` (строка 284) | ✅ Без изменений |

### 3.3 Внешние зависимости

**НЕТ**. Проект использует vanilla JavaScript без npm-зависимостей.

---

## 4. Технические ограничения

### 4.1 Браузерная совместимость

| Технология | Минимальная версия | Покрытие |
|------------|-------------------|----------|
| CSS Custom Properties | Chrome 49, Firefox 31, Safari 9.1 | 97%+ |
| ES6 async/await | Chrome 55, Firefox 52, Safari 10.1 | 96%+ |
| Fetch API | Chrome 42, Firefox 39, Safari 10.1 | 98%+ |

**Вывод**: Все современные браузеры поддерживаются.

### 4.2 Ограничения валидации

| Поле | Ограничение | Источник |
|------|-------------|----------|
| `system_prompt` | ≤5000 символов | Backend Pydantic (F011-B) |
| `response_format` | `{type: "json_object"}` или `null` | OpenAI spec |
| `prompt` | Обязательное поле | Backend |

**Требуется**: Client-side валидация перед отправкой.

### 4.3 Размер страницы

| Метрика | Текущее | После изменений | Изменение |
|---------|---------|-----------------|-----------|
| Размер HTML | ~12 KB | ~13 KB | +~1 KB |
| Строки кода | 428 | ~480 | +~50 |
| Загрузка | <100ms | <100ms | Без изменений |

**Вывод**: Минимальное влияние на производительность.

---

## 5. Предложенные точки интеграции

### 5.1 HTML-структура (новые элементы)

**Добавить ПОСЛЕ строки 214**:

```html
<div id="chat" class="tab-pane active">
    <textarea id="prompt-input" placeholder="Введите ваш запрос к AI..." rows="4"></textarea>

    <!-- NEW: System Prompt -->
    <textarea id="system-prompt-input"
              placeholder="System prompt (опционально)"
              rows="3"
              maxlength="5000"></textarea>

    <!-- NEW: Response Format -->
    <div class="format-selector">
        <label class="format-label">Формат ответа:</label>
        <div class="radio-group">
            <label class="radio-option">
                <input type="radio" name="response-format" value="text" checked>
                <span>Текст</span>
            </label>
            <label class="radio-option">
                <input type="radio" name="response-format" value="json">
                <span>JSON</span>
            </label>
        </div>
    </div>

    <button id="send-btn" class="btn-primary" onclick="sendPrompt()">
        <!-- ... -->
    </button>
</div>
```

### 5.2 CSS-стили (новые классы)

**Добавить ПОСЛЕ строки 78**:

```css
.format-selector {
    margin-bottom: 16px;
}
.format-label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-light);
    margin-bottom: 8px;
}
.radio-group {
    display: flex;
    gap: 16px;
}
.radio-option {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    font-size: 15px;
}
.radio-option input[type="radio"] {
    cursor: pointer;
}
```

### 5.3 JavaScript (изменения в sendPrompt)

**Заменить строки 327-346**:

```javascript
async function sendPrompt() {
    const input = document.getElementById('prompt-input');
    const systemPromptInput = document.getElementById('system-prompt-input');
    const formatRadios = document.getElementsByName('response-format');

    const prompt = input.value.trim();
    if (!prompt) { showError(errorBox, 'Введите текст запроса'); return; }

    // Собрать payload
    const payload = { prompt };

    // Добавить system_prompt если заполнен
    const systemPrompt = systemPromptInput.value.trim();
    if (systemPrompt) {
        if (systemPrompt.length > 5000) {
            showError(errorBox, 'System prompt не может превышать 5000 символов');
            return;
        }
        payload.system_prompt = systemPrompt;
    }

    // Добавить response_format если JSON выбран
    const selectedFormat = Array.from(formatRadios).find(r => r.checked)?.value;
    if (selectedFormat === 'json') {
        payload.response_format = { type: "json_object" };
    }

    // Отправить запрос
    sendBtn.disabled = true; hide(sendBtnText); show(sendBtnLoader); hide(responseBox); hide(errorBox);
    try {
        const data = await apiCall('/api/v1/prompts/process', {
            method: 'POST',
            body: JSON.stringify(payload)  // ← Расширенный payload
        });
        // ... display response (без изменений)
    } catch (e) { showError(errorBox, e.message); }
    finally { sendBtn.disabled = false; show(sendBtnText); hide(sendBtnLoader); }
}
```

---

## 6. Риски и митигация

### 6.1 Идентифицированные риски

| ID | Риск | Вероятность | Влияние | Митигация |
|----|------|-------------|---------|-----------|
| R1 | Пользователи вводят >5000 символов в system_prompt | MEDIUM | LOW | Client-side валидация, `maxlength` атрибут |
| R2 | JSON response format некорректен (AI не возвращает JSON) | LOW | MEDIUM | Backend уже обрабатывает (F011-B) |
| R3 | UI загромождён дополнительными полями | LOW | LOW | Минималистичный дизайн, system_prompt опционален |
| R4 | Backward compatibility — старые клиенты | NONE | — | Параметры опциональны на backend |

### 6.2 План митигации

**R1**: Добавить `maxlength="5000"` на textarea + JS-валидация перед отправкой.

**R2**: Backend уже возвращает ошибку, если AI не может сгенерировать JSON (см. F011-B тесты).

**R3**: Использовать placeholder "опционально", минимальный дизайн без выпадающих списков.

---

## 7. Рекомендации

### 7.1 Приоритеты реализации

| # | Задача | Приоритет | Обоснование |
|---|--------|-----------|-------------|
| 1 | Добавить textarea для system_prompt | MUST | Основное требование FR-001 |
| 2 | Добавить radio buttons для format | MUST | Основное требование FR-003 |
| 3 | Изменить sendPrompt() для передачи параметров | MUST | Интеграция с backend FR-005 |
| 4 | Добавить client-side валидацию | MUST | Предотвращение ошибок FR-002 |
| 5 | Добавить CSS-стили | SHOULD | Консистентность дизайна |
| 6 | Тесты E2E | SHOULD | Проверка интеграции |

### 7.2 Альтернативные подходы (отклонены)

| Подход | Причина отклонения |
|--------|--------------------|
| Collapsible секция для system_prompt | Добавляет сложность, требование — "всегда видно" |
| Dropdown для format | Избыточно для 2 опций |
| Добавить textarea в отдельную вкладку | Нарушает UX, требуется в основной форме |
| Использовать React/Vue | Проект vanilla JS, избыточная зависимость |

---

## 8. Зависимости от других фич

| Фича | Статус | Зависимость | Действие |
|------|--------|-------------|----------|
| F011-B (Backend) | VALIDATE (QA_PASSED) | ✅ READY | Можно начинать интеграцию |
| F002 (Web UI) | DEPLOYED | ✅ READY | Расширяем существующий интерфейс |

**Блокеры**: НЕТ. Все зависимости готовы.

---

## 9. Следующие шаги

### 9.1 Переход к архитектурному плану

Команда: `/aidd-feature-plan`

**Входные данные для планирования**:
- ✅ PRD создан (ai-docs/docs/prd/2026-01-15_F011-C_web-ui-advanced-params-prd.md)
- ✅ Research завершён (этот документ)
- ✅ Backend API готов (F011-B)

**Ожидаемый результат**:
- План изменений в `index.html`
- Порядок реализации (HTML → CSS → JS → валидация)
- План тестирования (manual QA)

### 9.2 Чек-лист для архитектора

- [ ] Определить точное расположение новых элементов в DOM
- [ ] Спроектировать mobile-responsive дизайн
- [ ] Уточнить поведение при очистке формы (FR-008)
- [ ] Определить порядок tab navigation
- [ ] Спроектировать accessibility (ARIA-labels)

---

## 10. Приложения

### 10.1 Скриншоты текущего UI

```
Текущий Чат-таб:
┌────────────────────────────────────────┐
│ [Textarea: Prompt (4 строки)]          │
│                                        │
│ [Кнопка: Отправить]                    │
│                                        │
│ [Response Box — скрыт до отправки]     │
└────────────────────────────────────────┘

Предложенный Чат-таб:
┌────────────────────────────────────────┐
│ [Textarea: Prompt (4 строки)]          │
│                                        │
│ [Textarea: System Prompt (3 строки)]   │← NEW
│                                        │
│ Формат ответа:                         │← NEW
│   ○ Текст  ○ JSON                      │
│                                        │
│ [Кнопка: Отправить]                    │
│                                        │
│ [Response Box]                         │
└────────────────────────────────────────┘
```

### 10.2 Минимальный пример интеграции

**Пример запроса с новыми параметрами**:

```javascript
// Пользователь заполнил:
// - Prompt: "Explain AI in simple terms"
// - System Prompt: "You are a helpful teacher"
// - Format: JSON

// Отправится payload:
{
  "prompt": "Explain AI in simple terms",
  "system_prompt": "You are a helpful teacher",
  "response_format": {"type": "json_object"}
}

// Backend F011-B обработает и вернёт:
{
  "response": "{\"explanation\": \"AI is...\"}",
  "selected_model": "gemini-2.0-flash-exp",
  "provider": "GoogleGemini",
  "response_time_seconds": 1.23
}
```

---

## 11. Метаданные

| Параметр | Значение |
|----------|----------|
| Файлов проанализировано | 1 (index.html) |
| Строк кода изучено | 428 |
| Зависимостей выявлено | 2 (F011-B, F002) |
| Рисков идентифицировано | 4 (все LOW/MEDIUM) |
| Время анализа | ~15 минут |

---

**Подпись исследователя**: AI Agent (Researcher)
**Ворота**: RESEARCH_DONE ✅
**Дата завершения**: 2026-01-15

