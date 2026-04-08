# Бенчмарк тегов моделей — План действий для модернизации

**Дата:** 2026-04-08
**Цель:** Максимизировать количество сценариев использования каждой модели: разные языки, размеры промптов, JSON/без JSON, reasoning, tool calling.
**Источник данных:** `docs/research/2026-04-08-model-tags-benchmark-results.md`

---

## Критерий: каждое изменение должно быть направлено на расширение возможностей маршрутизации

---

## 1. КРИТИЧЕСКИЕ БАГИ (ломают функциональность)

### 1.1 OpenRouter DeepSeek R1 0528: поле reasoning не парсится

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:159-185`

**Проблема:** `_parse_response()` проверяет `message.get("reasoning_content")`, но OpenRouter возвращает поле `reasoning` (без суффикса `_content`). Также есть массив `reasoning_details`. Когда reasoning заполняет весь max_tokens, OpenRouter возвращает `content: null` — текущий код вернёт пустую строку.

**Эмпирические данные из Block 1:**
```json
"message": {
  "role": "assistant",
  "content": null,
  "reasoning": "Hmm, the user wants me to say \"hello\"...",
  "reasoning_details": [{"type": "reasoning.text", "text": "...", "format": "unknown", "index": 0}]
}
```

**Что исправить:**
```python
# base.py:_parse_response(), после строки 171
# Текущий код: reasoning = message.get("reasoning_content", "")
# Нужно:
reasoning = (
    message.get("reasoning_content", "")
    or message.get("reasoning", "")
)
```

**Влияние на маршрутизацию:** Без этого фикса OpenRouter R1 возвращает пустые ответы → считается ошибкой → reliability_score падает → модель перестаёт выбираться маршрутизатором.

---

### 1.2 Fireworks GPT-OSS-20B: reasoning в проприетарных тегах

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`

**Проблема:** Fireworks помещает reasoning прямо в `content` с тегами `<|channel|>analysis<|message|>...<|end|><|start|>assistant`. Текущий `_parse_response()` вернёт весь мусор включая теги.

**Эмпирические данные из Block 1:**
```json
"content": "<|channel|>analysis<|message|>User instruction: \"Say hello in one word.\" We must say hello in one word: \"Hello\" or \"Hi\". The user says \"Say hello in one word.\" So respond with \"Hello\". Probably acceptable.<|end|><|start|>assistant"
```

**Что исправить:** Переопределить `_parse_response()` в `FireworksProvider`:
```python
# fireworks.py
import re

class FireworksProvider(OpenAICompatibleProvider):
    # ...существующие поля...

    def _parse_response(self, result: dict[str, Any]) -> str:
        content = super()._parse_response(result)
        # Strip proprietary reasoning tags from gpt-oss-20b
        if "<|channel|>" in content:
            # Extract text after last <|start|>assistant or <|end|>
            match = re.search(r"<\|end\|><\|start\|>assistant\s*(.*)", content, re.DOTALL)
            if match and match.group(1).strip():
                return match.group(1).strip()
            # Fallback: extract text between <|message|> and <|end|>
            match = re.search(r"<\|message\|>(.*?)<\|end\|>", content, re.DOTALL)
            if match:
                return match.group(1).strip()
        return content
```

**Влияние на маршрутизацию:** Без фикса пользователь получает мусорный текст с тегами → ухудшает качество → модель бесполезна для конечного пользователя.

---

### 1.3 Названия моделей в БД не совпадают с API

**Файл:** `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py:27-122`

**Проблема (данные из Block 0):**

| Провайдер | Имя в seed.py | Реальный API model ID | Реальный размер |
|-----------|--------------|----------------------|-----------------|
| Cerebras | "Llama 3.3 70B" | `llama3.1-8b` | **8B** (не 70B!) |
| Fireworks | "Llama 3.1 70B (Fireworks)" | `gpt-oss-20b` | **20B** (не 70B!) |
| Novita | "Llama 3.1 70B (Novita)" | `llama-3.1-8b-instruct` | **8B** (не 70B!) |

**Что исправить в seed.py:**
```python
# Cerebras: строка ~35
"name": "Llama 3.1 8B (Cerebras)",  # было: "Llama 3.3 70B"

# Fireworks: строка ~90
"name": "GPT-OSS-20B (Fireworks)",  # было: "Llama 3.1 70B (Fireworks)"

# Novita: строка ~105
"name": "Llama 3.1 8B Instruct (Novita)",  # было: "Llama 3.1 70B (Novita)"
```

**Влияние на маршрутизацию:** Неправильные названия вводят в заблуждение при выборе модели по тегу `code` (>=70B). Cerebras и Novita — это 8B модели, но в БД числятся как 70B. Тег `lightweight` невозможно назначить корректно.

---

## 2. ПАРСИНГ ОТВЕТОВ (расширение совместимости)

### 2.1 HuggingFace: finish_reason = "eos_token"

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py`

**Проблема:** HuggingFace Meta-Llama-3-8B-Instruct возвращает `finish_reason: "eos_token"` вместо стандартного `"stop"`. Если код где-либо проверяет `finish_reason == "stop"` для определения успеха — HuggingFace будет считаться сбоем.

**Данные из Block 1:**
```json
"choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello."}, "finish_reason": "eos_token"}]
```

**Что проверить:** Найти все места где проверяется `finish_reason` и добавить `"eos_token"` как эквивалент `"stop"`. Если нигде не проверяется — не нужно менять, но задокументировать.

---

### 2.2 Cloudflare: usage может быть нулевым

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/cloudflare.py`

**Проблема:** Cloudflare нативный API возвращает `usage` внутри `result`, а значения `prompt_tokens`/`completion_tokens` могут быть 0 или отсутствовать.

**Данные из Block 1:**
```json
{"result": {"response": "Hello.", "tool_calls": [], "usage": {"prompt_tokens": 41, "completion_tokens": 3, "total_tokens": 44, "prompt_tokens_details": {"cached_tokens": 0}}}}
```

**Что учесть:** Если проект логирует или использует `usage` для биллинга/статистики — Cloudflare может давать неточные данные. Не критично для маршрутизации, но важно для мониторинга.

---

### 2.3 OpenRouter: content: null при исчерпании max_tokens reasoning

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:159-185`

**Проблема:** Когда DeepSeek R1 тратит все `max_tokens` на reasoning, OpenRouter возвращает `content: null`, `finish_reason: "length"`. Текущий `_parse_response()` после фикса 1.1 вернёт reasoning — но это `<think>` контент, не финальный ответ.

**Данные из Block 1 (max_tokens=50):**
```json
"message": {"role": "assistant", "content": null, "reasoning": "Hmm, the user wants me to say \"hello\"..."}
```

**Что учесть:** Для reasoning-моделей нужен больший `max_tokens` чтобы хватило и на reasoning, и на ответ. Рекомендация: для model_id=7 (OpenRouter R1) использовать `max_tokens >= 4096` (или вообще 8192) вместо дефолтного 2048.

---

## 3. MAX_TOKENS (расширение длины ответов)

### 3.1 Текущий дефолт 2048 — безопасен, но ограничивает

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:141`

**Текущий код:**
```python
"max_tokens": kwargs.get("max_tokens", 2048),
```

**Данные из Block 2 — фактические лимиты:**

| Провайдер | Фактический Max | Безопасный max_tokens | Как определён |
|-----------|----------------|----------------------|---------------|
| Groq Llama 3.3 70B Versatile | 32,768 | 32,768 | Ошибка 400 раскрывает |
| Cerebras Llama 3.1 8B | Неизвестен (тихо обрезает) | 8,192 (документация) | 200 OK на 99999 |
| HuggingFace Meta-Llama-3-8B-Instruct | 8,192 | 8,192 | Ошибка 400 раскрывает |
| Cloudflare Llama 3.3 70B FP8 Fast | 24,000 (контекст) | 4,096 | Ошибка 400 |
| OpenRouter DeepSeek R1 0528 | Неизвестен (тихо принимает) | 65,536 (документация) | 200 OK на 99999 |
| GitHub Models GPT-4o Mini | 16,384 | 16,384 | Ошибка 400 раскрывает |
| Fireworks GPT-OSS-20B | 4,096 (без стриминга) | 4,096 | Ошибка 400 |
| Novita Llama 3.1 8B Instruct | 16,384 | 16,384 | Ошибка 400 раскрывает |

**Что исправить:** Добавить `MAX_OUTPUT_TOKENS` как класс-переменную в каждый провайдер:

```python
# base.py
MAX_OUTPUT_TOKENS: ClassVar[int] = 2048  # безопасный дефолт

# groq.py
MAX_OUTPUT_TOKENS = 32768

# cerebras.py
MAX_OUTPUT_TOKENS = 8192

# huggingface.py
MAX_OUTPUT_TOKENS = 8192

# cloudflare.py
MAX_OUTPUT_TOKENS = 4096

# openrouter.py
MAX_OUTPUT_TOKENS = 16384  # консервативно для R1

# github_models.py
MAX_OUTPUT_TOKENS = 16384

# fireworks.py
MAX_OUTPUT_TOKENS = 4096  # без стриминга

# novita.py
MAX_OUTPUT_TOKENS = 16384
```

Маршрутизатор сможет выбирать провайдера исходя из ожидаемой длины ответа.

---

### 3.2 HuggingFace использует max_new_tokens, не max_tokens

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/base.py:141`

**Проблема:** HuggingFace API принимает `max_new_tokens` — но текущий `_build_payload()` отправляет `max_tokens`. Работает через OpenAI-совместимый роутер HuggingFace, который может конвертировать, но если дефолт у HF = 20 токенов при отсутствии параметра — ответы могут обрезаться.

**Данные из Block 2:** HuggingFace принял `max_tokens` через OpenAI-совместимый роутер без проблем. Но дефолт у HF без параметра = 20 токенов — критически мало.

**Что учесть:** Текущий дефолт 2048 всегда передаётся — проблема не проявляется. Но если когда-либо `max_tokens` не будет передан — ответы HuggingFace будут обрезаны до 20 токенов.

---

### 3.3 Fireworks: max_completion_tokens для reasoning моделей

**Файл:** `services/free-ai-selector-business-api/app/infrastructure/ai_providers/fireworks.py`

**Проблема:** Fireworks для reasoning-моделей (gpt-oss-20b) рекомендует `max_completion_tokens` вместо `max_tokens`. Также без стриминга лимит 4096 — ошибка 400 при `max_tokens > 4096`.

**Данные из Block 2:**
```
400: "Requests with max_tokens > 4096 must have stream=true"
```

**Что исправить:** Переопределить `_build_payload()` в `FireworksProvider`:
```python
def _build_payload(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
    payload = super()._build_payload(prompt, **kwargs)
    # Cap max_tokens for non-streaming
    if payload.get("max_tokens", 0) > 4096:
        payload["max_tokens"] = 4096
    return payload
```

---

## 4. МАРШРУТИЗАЦИЯ И ТЕГИ (расширение сценариев)

### 4.1 Добавить теги моделям

**Файл:** `services/free-ai-selector-data-postgres-api/app/infrastructure/database/seed.py`

**Текущее состояние:** В seed.py нет поля для тегов. Теги нужно хранить для маршрутизации по сценариям.

**Рекомендуемые теги (по результатам бенчмарка):**

| Провайдер + Модель | Теги |
|--------------------|------|
| Groq Llama 3.3 70B Versatile | `fast`, `json`, `code`, `russian`, `tools` |
| Cerebras Llama 3.1 8B | `fast`, `json`, `russian`, `lightweight` |
| HuggingFace Meta-Llama-3-8B-Instruct | `russian`, `lightweight` |
| Cloudflare Llama 3.3 70B FP8 Fast | `json`, `code`, `russian` |
| OpenRouter DeepSeek R1 0528 | `code`, `reasoning`, `russian`, `tools` |
| GitHub Models GPT-4o Mini | `fast`, `json`, `russian`, `tools` |
| Fireworks GPT-OSS-20B | `json`, `code`, `russian` |
| Novita Llama 3.1 8B Instruct | `json`, `russian`, `lightweight` |

**Что нужно:**
1. Добавить поле `tags` (список строк) в модель БД
2. Добавить теги в seed.py
3. В маршрутизаторе: фильтровать модели по запрошенным тегам

---

### 4.2 Маршрутизация по сценарию

**Файл:** `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py:162-182`

**Текущая фильтрация:** Только по `SUPPORTS_RESPONSE_FORMAT` при наличии `response_format` в запросе.

**Что добавить для расширения сценариев:**

| Сценарий запроса | Фильтр по тегам | Почему |
|-----------------|-----------------|--------|
| JSON ответ (`response_format` задан) | `json` | Уже реализовано через `SUPPORTS_RESPONSE_FORMAT` |
| Русский промпт (определяется по тексту) | `russian` | Все текущие модели поддерживают — пока не нужен |
| Длинный промпт (>3000 символов) | Не `lightweight` (предпочитать 70B+) | 70B генерирует более длинные ответы (данные Block 4) |
| Быстрый ответ нужен | `fast` | Groq, GitHub, Cerebras — <3с |
| Код/техническое задание | `code` | 70B+ и специализированные модели |
| Reasoning/анализ | `reasoning` | Только OpenRouter R1 (и частично Fireworks) |
| Tool calling | `tools` | Groq, OpenRouter, GitHub Models |

---

### 4.3 Проверить работу model_id в маршрутизации

**Файл:** `services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py:583-605`

**Текущий код (строка 600-604):**
```python
requested_model = next((model for model in sorted_models if model.id == requested_model_id), None)
if requested_model is None:
    return sorted_models, False
remaining_models = [model for model in sorted_models if model.id != requested_model.id]
return [requested_model, *remaining_models], True
```

**Данные из Block 3-6:** При запросе `model_id=1` (Groq) — ответы приходили от **Cerebras** с `fallback_used: false`.

**Возможные причины:**
1. `sorted_models` не содержит model_id=1 (Groq мог быть отфильтрован по availability)
2. Groq отвечает ошибкой → fallback на следующую модель
3. `fallback_used` неправильно определяется: `successful_model.id != first_model.id` — но если Groq был first и упал, Cerebras должен дать `fallback_used: true`

**Что проверить:** Добавить логирование в `_build_candidate_models()` — какой `selection_mode` и какой список `candidate_models` формируется.

---

## 5. СКОРОСТЬ И ТАЙМАУТЫ (расширение надёжности)

### 5.1 Скорость по результатам бенчмарка

**Данные из Block 4 (среднее по user_200 + user_1000):**

| Провайдер | Средняя скорость | Категория |
|-----------|-----------------|-----------|
| Groq Llama 3.3 70B Versatile | 1.1s | Ultra-fast |
| GitHub Models GPT-4o Mini | 1.4s | Ultra-fast |
| Cerebras Llama 3.1 8B | 2.0s | Fast |
| Cloudflare Llama 3.3 70B FP8 Fast | 8.4s | Medium |
| Fireworks GPT-OSS-20B | 9.0s | Medium |
| HuggingFace Meta-Llama-3-8B-Instruct | 9.9s | Medium |
| Novita Llama 3.1 8B Instruct | 13.6s | Slow |
| OpenRouter DeepSeek R1 0528 | 49.2s | Very slow |

**Что учесть:** OpenRouter R1 на длинных промптах (user_2000+) может отвечать 90-120с. Текущий таймаут может быть недостаточен.

### 5.2 Таймаут для reasoning моделей

**Проблема:** OpenRouter DeepSeek R1 0528 таймаут (120с) на `ru_medium`. Reasoning модели тратят время на цепочку рассуждений перед ответом.

**Что исправить:** Для моделей с тегом `reasoning` использовать увеличенный таймаут (180-300с) или warning пользователю о длительном ожидании.

---

## 6. RATE LIMITS И КРЕДИТЫ (расширение доступности)

### 6.1 Rate limits по провайдерам (документация + эмпирика)

| Провайдер | RPM | RPD | Критическое ограничение |
|-----------|-----|-----|------------------------|
| Groq | 30 | 1,000 | TPD = 100K токенов/день |
| Cerebras | 30 | 14,400 | Самый щедрый по RPD |
| HuggingFace | ~30 | ~14,400 | **$0.10/мес кредитов** — исчерпались за 11 запросов! |
| Cloudflare | 300 | ~1-3 для 70B | **10K нейронов/день** — хватит на 1-3 запроса к 70B! |
| OpenRouter | 20 | **50** | Самый жёсткий RPD — 50 запросов/день на ВСЕ free модели |
| GitHub Models | 15 | **150** | Малый RPD, но стабильный |
| Fireworks | 10 | Не документировано | Самый низкий RPM — 12 запросов → 429 |
| Novita | Не документировано | Не документировано | $0.50 кредитов при регистрации |

### 6.2 Cloudflare практически непригоден для 70B на free tier

**Данные из Block 7:** 10,000 нейронов/день, 70B модель стоит ~200K нейронов/M output tokens. Это ~1-3 коротких запроса в день.

**Рекомендация:** Использовать Cloudflare только как последний fallback, или переключить на меньшую модель (8B), или полностью исключить из бесплатного tier.

### 6.3 HuggingFace: мониторинг кредитов

**Данные из Block 7:** $0.10/месяц бесплатного кредита исчерпано за 11 запросов (каждый ~$0.009).

**Что добавить:** При получении HTTP 402 от HuggingFace — деактивировать провайдера до начала следующего месяца, а не просто retry.

### 6.4 OpenRouter: 50 RPD на ВСЕ free модели

**Данные из исследования:** 50 RPD — это общий лимит на все бесплатные модели OpenRouter, не на каждую.

**Что учесть:** OpenRouter R1 — самая ценная модель (единственная с полноценным reasoning), но самая медленная и с жёстким RPD. Использовать только для запросов требующих reasoning.

---

## 7. JSON ФОРМАТ (расширение поддержки)

### 7.1 Все модели генерируют JSON даже без response_format

**Данные из Block 5:** Все 8 провайдеров вернули валидный JSON на json_short. Даже HuggingFace (без поддержки `response_format` на уровне API) сгенерировала JSON просто по промпту.

**Вывод:** Тег `json` можно присвоить всем провайдерам для простых JSON-запросов. Различие в надёжности: 70B модели стабильнее на сложных JSON-структурах.

### 7.2 Fireworks GPT-OSS-20B: неполный JSON на json_medium

**Данные из Block 5:** Fireworks вернул только 1 фреймворк вместо 5 (178 символов vs 900+). Вероятно ограничение по max_tokens (дефолт 2048, но часть ушла на reasoning теги).

**Рекомендация:** Для JSON-запросов к Fireworks увеличить max_tokens или не использовать reasoning-модель для JSON.

### 7.3 GitHub GPT-4o Mini: транслитерация русского в JSON

**Данные из Block 5:** `{"cities": {"Moskva": 12700000, "Sankt-Peterburg": ...}}` — неожиданная транслитерация.

**Что учесть:** Для русскоязычных JSON-запросов предпочитать Cloudflare или OpenRouter (возвращают русские ключи: `{"города": [{"имя": "Москва"...}]}`).

---

## 8. RESPONSE_FORMAT API ПОДДЕРЖКА

**Данные из Block 1 + исследование:**

| Провайдер | json_object | json_schema | Если не поддерживает |
|-----------|:-----------:|:-----------:|---------------------|
| Groq | Да | Да | N/A |
| Cerebras | Да | Нет | N/A |
| HuggingFace | **Нет** | Нет | Параметр **игнорируется** |
| Cloudflare | Да | Да | N/A |
| OpenRouter | Да | Проксирует | Зависит от бэкенда |
| GitHub Models | Да | Да (structured output) | N/A |
| Fireworks | Да | Да (grammar) | N/A |
| Novita | Да | Частично | N/A |

**Текущий код (base.py:147-157):** Если `SUPPORTS_RESPONSE_FORMAT = False`, параметр не передаётся и логируется warning. Это правильное поведение.

**HuggingFace (SUPPORTS_RESPONSE_FORMAT = False):** Корректно не передаёт параметр. Но модель всё равно может генерировать JSON по промпту — нужно указать в промпте "respond in JSON format".

---

## 9. РУССКИЙ ЯЗЫК

### 9.1 Все модели отвечают на русском

**Данные из Block 6:** ВСЕ 8 провайдеров (включая 8B модели) ответили на русском с хорошим качеством. Это противоречит исследованию, которое предсказывало "poor" для 8B.

**Причина расхождения:** Исследование основывалось на общих данных о Llama 3.x. В реальности:
- Cerebras использует `llama3.1-8b` (не Llama 3.0) — улучшен для мультиязычности
- Промпт на русском ("Что такое Python?") — простой; для сложных тем качество 8B может падать
- Тест состоял из 2 промптов — недостаточно для статистической значимости

**Рекомендация:** Тег `russian` назначить всем моделям. Но для сложных русскоязычных запросов предпочитать 70B+ модели.

---

## 10. TOOL CALLING

**Данные из Block 1 (поле tool_calls в message):**

| Провайдер | tool_calls в ответе | Документация |
|-----------|:------------------:|-------------|
| Groq Llama 3.3 70B Versatile | **Да** | Поддерживает tools параметр |
| OpenRouter DeepSeek R1 0528 | **Да** | Проксирует tools к бэкенду |
| GitHub Models GPT-4o Mini | **Да** | Полная поддержка (Azure OpenAI) |
| Cerebras Llama 3.1 8B | Нет | 8B модель не поддерживает |
| HuggingFace Meta-Llama-3-8B-Instruct | Нет | 8B модель не поддерживает |
| Cloudflare Llama 3.3 70B FP8 Fast | Нет | Нативный API не поддерживает tools |
| Fireworks GPT-OSS-20B | Нет | Не подтверждено для этой модели |
| Novita Llama 3.1 8B Instruct | Нет | 8B модель не поддерживает |

**Что нужно для tool calling:**
1. Добавить тег `tools` в seed.py для Groq, OpenRouter, GitHub Models
2. В `_build_payload()` добавить передачу `tools` параметра (аналогично `response_format`)
3. В `_parse_response()` обработать `finish_reason: "tool_calls"` — вернуть tool_calls как структурированный ответ

---

## 11. CONTENT FILTER (Azure и Novita)

**Данные из Block 1:**

GitHub Models GPT-4o Mini и Novita возвращают `content_filter_results` в `choices[0]`:
```json
"content_filter_results": {
  "hate": {"filtered": false, "severity": "safe"},
  "self_harm": {"filtered": false, "severity": "safe"},
  "sexual": {"filtered": false, "severity": "safe"},
  "violence": {"filtered": false, "severity": "safe"}
}
```

**Что учесть:** Если `filtered: true` — ответ будет пустым или обрезанным. `finish_reason: "content_filter"` тоже возможен. Нужно обрабатывать как специальный тип ошибки (не retry, а fallback на другого провайдера без content filter).

---

## 12. ПРИОРИТЕТ РЕАЛИЗАЦИИ

### Фаза 1: Критические баги (сломанная функциональность)
1. **[1.1]** Фикс парсинга OpenRouter reasoning → `base.py`
2. **[1.2]** Фикс парсинга Fireworks reasoning тегов → `fireworks.py`
3. **[1.3]** Исправить названия моделей в seed.py
4. **[3.3]** Cap max_tokens=4096 для Fireworks без стриминга

### Фаза 2: Расширение возможностей маршрутизации
5. **[4.1]** Добавить поле tags в модель БД + seed.py
6. **[3.1]** Добавить MAX_OUTPUT_TOKENS per-provider
7. **[4.2]** Фильтрация по тегам в маршрутизаторе
8. **[5.2]** Увеличить таймаут для reasoning моделей

### Фаза 3: Мониторинг и устойчивость
9. **[6.3]** Мониторинг кредитов HuggingFace (402 → деактивация)
10. **[6.2]** Понизить приоритет Cloudflare (или переключить на 8B модель)
11. **[11]** Обработка content_filter как специальной ошибки
12. **[4.3]** Логирование и проверка маршрутизации model_id
