# Бенчмарк тегов моделей — Результаты

**Дата:** 2026-04-08
**Длительность:** ~45 мин (Блоки 0-6) + ~10 мин (Блок 7 + восстановление)
**Всего запросов:** ~170

## Блок 0: Подготовка

**Живые провайдеры (8 из 12):**

| ID | Провайдер + Модель | API Model ID | Статус | Время ответа |
|----|-------------------|-------------|--------|-------------|
| 1 | Groq Llama 3.3 70B Versatile | `llama-3.3-70b-versatile` | OK | 0.64s |
| 2 | Cerebras Llama 3.1 8B | `llama3.1-8b` | OK | 0.77s |
| 4 | HuggingFace Meta-Llama-3-8B-Instruct | `meta-llama/Meta-Llama-3-8B-Instruct` | OK | 0.93s |
| 5 | Cloudflare Llama 3.3 70B FP8 Fast | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | OK | 0.67s |
| 7 | OpenRouter DeepSeek R1 0528 | `deepseek/deepseek-r1-0528` | OK | 9.15s |
| 8 | GitHub Models GPT-4o Mini | `gpt-4o-mini` | OK | 1.79s |
| 9 | Fireworks GPT-OSS-20B | `accounts/fireworks/models/gpt-oss-20b` | OK | 1.61s |
| 11 | Novita Llama 3.1 8B Instruct | `meta-llama/llama-3.1-8b-instruct` | OK | 1.54s |

**Мёртвые провайдеры:** DeepSeek (402), Hyperbolic (402), SambaNova (402), Scaleway (403)

**Замечание:** Названия моделей в БД не совпадают с API: Cerebras (БД: "Llama 3.3 70B", API: `llama3.1-8b`), Fireworks (БД: "Llama 3.1 70B", API: `gpt-oss-20b`), Novita (БД: "Llama 3.1 70B", API: `llama-3.1-8b-instruct`).

## Блок 1: Исследование полей ответа

### Сравнение структуры ответов

| Поле                   |                 Groq Llama 3.3 70B Versatile                 |          Cerebras Llama 3.1 8B           | HuggingFace Meta-Llama-3-8B-Instruct | Cloudflare Llama 3.3 70B FP8 Fast |            OpenRouter DeepSeek R1 0528            | GitHub Models GPT-4o Mini |     Fireworks GPT-OSS-20B      | Novita Llama 3.1 8B Instruct |
| ---------------------- | :----------------------------------------------------------: | :--------------------------------------: | :----------------------------------: | :-------------------------------: | :-----------------------------------------------: | :-----------------------: | :----------------------------: | :--------------------------: |
| **Формат API**         |                            OpenAI                            |                  OpenAI                  |                OpenAI                |           **Нативный**            |                      OpenAI                       |          OpenAI           |             OpenAI             |            OpenAI            |
| **Путь к ответу**      | `choices[0].message.content` | `choices[0].message.content` | `choices[0].message.content` | **`result.response`** | `choices[0].message.content` (reasoning в `message.reasoning`) | `choices[0].message.content` | `choices[0].message.content` (ответ замешан с `<\|channel\|>` тегами) | `choices[0].message.content` |
| **finish_reason**      | `stop`, `length`, `tool_calls`, `content_filter` | `stop`, `length` | `stop`, `length`, **`eos_token`** | `stop`, `length` (внутри `result`) | `stop`, `length`, `tool_calls` | `stop`, `length`, `tool_calls`, `content_filter` | `stop`, `length` | `stop`, `length` |
| **response_format API** | **Да** (`json_object` + `json_schema`) | **Да** (`json_object` только) | **Нет** (параметр игнорируется) | **Да** (`json_object` + `json_schema`) | **Да** (проксирует к бэкенду) | **Да** (`json_object` + structured output) | **Да** (`json_object` + grammar) | **Да** (`json_object`) |
| **Имя параметра max_tokens** | `max_tokens` | `max_tokens` | **`max_new_tokens`** (дефолт всего 20!) | `max_tokens` (дефолт 256) | `max_tokens` | `max_tokens` | **`max_completion_tokens`** (для reasoning) | `max_tokens` |
| **tool_calls**         | **Да** | Нет | Нет | Нет | **Да** | **Да** | Нет | Нет |
| **reasoning_content**  |                              -                               |                    -                     |                  -                   |                 -                 |            **Нет** (поле `reasoning`)             |             -             | **Нет** (`<\|channel\|>` теги) |              -               |
| **reasoning поле**     |                              -                               |                    -                     |                  -                   |                 -                 |           **Да** + `reasoning_details`            |             -             |               -                |              -               |
| **content_filter**     | - | - | - | - | - | **Да** (Azure). Если `filtered: true` — ответ обрезан | - | **Да** |
| **system_fingerprint** |                             Есть                             |                   Есть                   |             `""` (пусто)             |                Н/Д                |                       null                        |           Есть            |              Нет               |         `""` (пусто)         |
| **usage доп. поля**    | `queue_time`, `prompt_time`, `completion_time`, `total_time` | `time_info`, `completion_tokens_details` |           `null` в details           |       Внутри `result.usage`       | `cost`, `cost_details`, полные `*_tokens_details` | Полные `*_tokens_details` |    `prompt_tokens_details`     |       `null` в details       |
| **формат id**          |                       `chatcmpl-uuid`                        |             `chatcmpl-uuid`              |               hex-хэш                |          Н/Д (нативный)           |                     `gen-xxx`                     |      `chatcmpl-xxx`       |        `chatcmpl-uuid`         |           hex-хэш            |
| **доп. top-level**     |                   `x_groq`, `service_tier`                   |                    -                     |                  -                   |  `success`, `errors`, `messages`  |                    `provider`                     |  `prompt_filter_results`  |               -                |              -               |

### Критические находки

1. **OpenRouter DeepSeek R1 0528 НЕ использует `reasoning_content`** — использует поле `reasoning` + массив `reasoning_details`. Текущий код, проверяющий `reasoning_content`, не работает с OpenRouter.
2. **Fireworks GPT-OSS-20B НЕ использует `reasoning_content`** — встраивает рассуждения в `content` тегами `<|channel|>analysis<|message|>...<|end|><|start|>`. Нестандартный формат.
3. **Cloudflare Llama 3.3 70B FP8 Fast использует нативный API** — ответ `{result: {response: "..."}}`, а не OpenAI `choices[]`.
4. **Novita Llama 3.1 8B Instruct содержит content_filter_results** — неожиданно, аналогично формату Azure.
5. **OpenRouter DeepSeek R1 0528 возвращает `content: null`** когда reasoning заполняет max_tokens — нужна явная обработка.
6. **OpenRouter показывает поле `provider`** — фактический бэкенд меняется (Nebius, AtlasCloud в наших тестах).

## Блок 2: Валидация max_tokens

| Провайдер + Модель                   | Документированный Max | Фактический Max (тест)         | max_tokens=99999                                 | max_tokens=1 | Context Window           |
| ------------------------------------ | --------------------- | ------------------------------ | ------------------------------------------------ | ------------ | ------------------------ |
| Groq Llama 3.3 70B Versatile         | 32,768                | **32,768**                     | 400: `"max_tokens must be <= 32768"`             | OK (1 токен) | 131,072                  |
| Cerebras Llama 3.1 8B                | 8,192                 | **Неизвестен (тихо обрезает)** | 200 OK (принял!)                                 | OK (1 токен) | 8K free / 32K paid       |
| HuggingFace Meta-Llama-3-8B-Instruct | ~2,048                | **8,192**                      | 400: `"must be between 0 and 8192"`              | OK (1 токен) | 8,192 общий              |
| Cloudflare Llama 3.3 70B FP8 Fast    | ~4,096                | **24,000 (контекст)**          | 400: `"maximum context length is 24000"`         | OK (1 токен) | 24,000                   |
| OpenRouter DeepSeek R1 0528          | 65,536                | **Неизвестен (тихо принял)**   | 200 OK                                           | OK           | 163,840                  |
| GitHub Models GPT-4o Mini            | 4,000                 | **16,384**                     | 400: `"supports at most 16384"`                  | OK (1 токен) | 128K модель, 8K+16K free |
| Fireworks GPT-OSS-20B                | 16,384                | **4,096 (без стриминга)**      | 400: `"max_tokens > 4096 must have stream=true"` | OK (1 токен) | 131,072                  |
| Novita Llama 3.1 8B Instruct         | 4,096                 | **16,384**                     | 400: `"must be between 0 and 16384"`             | OK (1 токен) | 16,384                   |

### Ключевые расхождения с планом

- **HuggingFace Meta-Llama-3-8B-Instruct**: реальный max = 8,192 (не ~2,048 как в плане)
- **GitHub Models GPT-4o Mini**: реальный max = **16,384** (не 4,000 — план устарел!)
- **Novita Llama 3.1 8B Instruct**: реальный max = **16,384** (не 4,096)
- **Fireworks GPT-OSS-20B**: без стриминга лимит **4,096**; со стримингом — больше
- **Cerebras Llama 3.1 8B и OpenRouter DeepSeek R1 0528**: тихо принимают/обрезают — ошибка не раскрывает лимит

## Блок 3: Длина системного промпта

Все провайдеры обработали все длины системного промпта (0-3000 символов) без ошибок.

| Провайдер + Модель | sys_0 | sys_500 | sys_1500 | sys_3000 | Тренд |
|--------------------|:-----:|:-------:|:--------:|:--------:|:-----:|
| Groq Llama 3.3 70B Versatile | 1.5s | 0.9s | 1.0s | 1.5s | **Стабильно** |
| Cerebras Llama 3.1 8B | 0.8s | 2.6s | 2.5s | 2.4s | **Стабильно** |
| HuggingFace Meta-Llama-3-8B-Instruct | 2.8s | 2.0s | 2.1s | 3.0s | **Стабильно** |
| Cloudflare Llama 3.3 70B FP8 Fast | 2.4s | 4.8s | 5.1s | 4.0s | **Стабильно** |
| OpenRouter DeepSeek R1 0528 | 5.6s | 7.4s | 3.7s | 10.1s | **Нестабильно** |
| GitHub Models GPT-4o Mini | 0.9s | 1.7s | 1.0s | 1.2s | **Стабильно** |
| Fireworks GPT-OSS-20B | 4.6s | 4.2s | 5.1s | 3.5s | **Стабильно** |
| Novita Llama 3.1 8B Instruct | 2.5s | 3.0s | 2.5s | 2.9s | **Стабильно** |

**Вывод:** Длина системного промпта (до 3000 символов / ~800 токенов) **не влияет значимо** на время ответа или процент успеха ни у одного провайдера.

## Блок 4: Длина пользовательского промпта

| Провайдер + Модель | user_200 | user_1000 | user_2000 | user_3000 | user_5000 |
|--------------------|:--------:|:---------:|:---------:|:---------:|:---------:|
| Groq Llama 3.3 70B Versatile | 1.0s | 1.3s | 1.5s | 3.4s | 4.7s |
| Cerebras Llama 3.1 8B | 2.4s | 1.7s | 1.7s | 1.9s | 1.6s |
| HuggingFace Meta-Llama-3-8B-Instruct | 6.4s | 13.4s | 24.6s | 17.9s | 25.3s |
| Cloudflare Llama 3.3 70B FP8 Fast | 3.0s | 13.7s | 29.2s | 32.1s | 33.0s |
| OpenRouter DeepSeek R1 0528 | 41.0s | 57.5s | 113.8s | 90.2s | 58.0s |
| GitHub Models GPT-4o Mini | 1.2s | 1.6s | 4.6s | 3.3s | 2.0s |
| Fireworks GPT-OSS-20B | 9.3s | 8.7s | 23.1s | 32.4s | 32.8s |
| Novita Llama 3.1 8B Instruct | 6.1s | 21.1s | 27.0s | 32.3s | 32.2s |

**Длина ответа (символы):**

| Провайдер + Модель | user_200 | user_1000 | user_2000 | user_3000 | user_5000 |
|--------------------|:--------:|:---------:|:---------:|:---------:|:---------:|
| Groq Llama 3.3 70B Versatile | 1,433 | 6,240 | 6,832 | 10,714 | 9,695 |
| Cerebras Llama 3.1 8B | 1,836 | 5,050 | 5,605 | 9,761 | 10,051 |
| HuggingFace Meta-Llama-3-8B-Instruct | 2,230 | 5,460 | 9,363 | 6,826 | 11,385 |
| Cloudflare Llama 3.3 70B FP8 Fast | 509 | 2,620 | 4,222 | 8,071 | 10,536 |
| OpenRouter DeepSeek R1 0528 | 1,759 | 2,527 | 3,874 | 5,434 | **4** (!!) |
| GitHub Models GPT-4o Mini | 1,264 | 7,023 | 5,487 | 8,016 | 9,611 |
| Fireworks GPT-OSS-20B | 1,509 | 2,568 | 5,055 | 10,710 | 9,674 |
| Novita Llama 3.1 8B Instruct | 1,330 | 5,722 | 7,184 | 10,706 | 9,244 |

**Находки:**
- **Лидеры по скорости**: Groq Llama 3.3 70B Versatile (1.1s), GitHub Models GPT-4o Mini (1.4s), Cerebras Llama 3.1 8B (2.0s) — все менее 3с на коротких промптах
- **OpenRouter DeepSeek R1 0528 user_5000**: вернул только 4 символа — вероятно таймаут или reasoning потребил все токены
- **Cloudflare Llama 3.3 70B FP8 Fast**: время ответа линейно растёт с длиной промпта (3с→33с) — медленный на длинных запросах
- **Ни один провайдер не упал** ни на одной длине промпта — подтверждает гипотезу что сбои вызваны rate limits, а не размером промпта

### Рейтинг скорости (среднее user_200 + user_1000, критерий тега fast: <3с)

1. **Groq Llama 3.3 70B Versatile: 1.1s** — FAST
2. **GitHub Models GPT-4o Mini: 1.4s** — FAST
3. **Cerebras Llama 3.1 8B: 2.0s** — FAST
4. Cloudflare Llama 3.3 70B FP8 Fast: 8.4s
5. Fireworks GPT-OSS-20B: 9.0s
6. HuggingFace Meta-Llama-3-8B-Instruct: 9.9s
7. Novita Llama 3.1 8B Instruct: 13.6s
8. OpenRouter DeepSeek R1 0528: 49.2s

## Блок 5: Формат JSON

### Результаты json_short

| Провайдер + Модель | Валидный JSON | Превью |
|--------------------|:------------:|--------|
| Groq Llama 3.3 70B Versatile | **Да** | `{"C": 1972,"Python": 1991,"Java": 1995}` |
| Cerebras Llama 3.1 8B | Да (массив) | `{"languages": [{"name": "Python", "year": 1991}, ...]}` |
| HuggingFace Meta-Llama-3-8B-Instruct | Да (массив) | `{"languages": [{"name": "Java", "year": 1995}, ...]}` |
| Cloudflare Llama 3.3 70B FP8 Fast | **Да** | `{"C": 1972, "Rust": 2010, "Python": 1991}` |
| OpenRouter DeepSeek R1 0528 | Да (массив) | `[{"language": "Python", "year": 1991}, ...]` |
| GitHub Models GPT-4o Mini | **Да** | `{"C": 1972,"Java": 1991,"Python": 1991}` |
| Fireworks GPT-OSS-20B | Да (массив) | `{"languages": [{"name": "C", "year": 1972}, ...]}` |
| Novita Llama 3.1 8B Instruct | **Да** | `{"C": "1972", "Java": "1995", "JavaScript": "1995"}` |

Все провайдеры вернули валидный JSON на коротких промптах. Все модели способны генерировать базовый JSON.

### Результаты json_medium

Все вернули JSON (с некоторой непоследовательностью структуры). HuggingFace Meta-Llama-3-8B-Instruct вернул JSON-схему вместо данных. Fireworks GPT-OSS-20B вернул только 1 фреймворк вместо 5 (178 символов против 900+ у остальных).

### Результаты json_ru

| Провайдер + Модель | Русский в ключах/значениях | Превью |
|--------------------|:------------------------:|--------|
| Groq Llama 3.3 70B Versatile | Только значения | `{"cities": [{"name": "Москва"...}]}` |
| Cerebras Llama 3.1 8B | Только значения | `{"city1": {"name": "Москва"...}}` |
| HuggingFace Meta-Llama-3-8B-Instruct | Только значения | `{"cities": [{"name": "Москва"...}]}` |
| Cloudflare Llama 3.3 70B FP8 Fast | **Ключи + значения** | `{"города": [{"имя": "Москва"...}]}` |
| OpenRouter DeepSeek R1 0528 | **Ключи + значения** | `[{"город": "Москва", "население": 13010112}]` |
| GitHub Models GPT-4o Mini | **Транслитерация** | `{"cities": {"Moskva": 12700000, "Sankt-Peterburg": ...}}` |
| Fireworks GPT-OSS-20B | Только значения | `{"cities": [{"name": "Москва"...}]}` |
| Novita Llama 3.1 8B Instruct | Только значения | `{"cities": [{"name": "Москва"...}]}` |

**Замечание:** GitHub Models GPT-4o Mini транслитерировал русские названия городов в латиницу — неожиданно для модели с "отличным" русским. Cloudflare и OpenRouter использовали русские ключи.

## Блок 6: Качество русского языка

### ru_short ("Что такое Python? 2 предложения.")

| Провайдер + Модель | Язык | Время | Символы | Качество |
|--------------------|:----:|:-----:|:-------:|:--------:|
| Groq Llama 3.3 70B Versatile | **ru** | 1.0s | 312 | **Хорошо** |
| Cerebras Llama 3.1 8B | **ru** | 0.9s | 344 | **Хорошо** |
| HuggingFace Meta-Llama-3-8B-Instruct | **ru** | 3.2s | 340 | **Хорошо** |
| Cloudflare Llama 3.3 70B FP8 Fast | **ru** | 4.5s | 365 | **Хорошо** |
| OpenRouter DeepSeek R1 0528 | **ru** | 9.0s | 292 | **Хорошо** |
| GitHub Models GPT-4o Mini | **ru** | 1.3s | 297 | **Хорошо** |
| Fireworks GPT-OSS-20B | **ru** | 6.9s | 207 | **Хорошо** |
| Novita Llama 3.1 8B Instruct | **ru** | 2.9s | 304 | **Хорошо** |

**Сюрприз:** ВСЕ провайдеры ответили на русском с хорошим качеством, включая 8B-модели. Ожидалось плохое качество русского у 8B — это противоречит результатам исследования.

### ru_medium (детальный промпт об истории ИИ на русском)

| Провайдер + Модель | Язык | Время | Символы | Качество |
|--------------------|:----:|:-----:|:-------:|:--------:|
| Groq Llama 3.3 70B Versatile | **ru** | 2.4s | 3,680 | **Хорошо** |
| Cerebras Llama 3.1 8B | **ru** | 1.5s | 3,340 | **Хорошо** |
| HuggingFace Meta-Llama-3-8B-Instruct | **ru** | 12.4s | 3,367 | **Хорошо** |
| Cloudflare Llama 3.3 70B FP8 Fast | **ru** | 32.2s | 2,716 | **Хорошо** |
| OpenRouter DeepSeek R1 0528 | **ТАЙМАУТ** | 120s | 0 | Н/Д |
| GitHub Models GPT-4o Mini | **ru** | 2.5s | 3,523 | **Хорошо** |
| Fireworks GPT-OSS-20B | **ru** | 32.0s | 3,859 | **Хорошо** |
| Novita Llama 3.1 8B Instruct | **ru** | 17.3s | 3,310 | **Хорошо** |

**Находки:**
- Все провайдеры (кроме таймаута OpenRouter) ответили на русском
- Даже 8B-модели (Cerebras, HuggingFace, Novita) дали приличный русский — противоречит ожиданию "плохого" качества
- OpenRouter DeepSeek R1 0528 таймаут (120с) на среднем русском промпте — слишком большие накладные расходы на reasoning

## Блок 7: Стресс-тест rate limit

**Метод:** Прямые curl-запросы из Docker-контейнера (минуя Business API), быстрые запросы без пауз.

| Провайдер + Модель | Запросов до ошибки | HTTP-код | Тип ошибки | Восстановление (3 мин) |
|--------------------|:------------------:|:--------:|:----------:|:----------------------:|
| Groq Llama 3.3 70B Versatile | **1** | 403 | **Cloudflare WAF (1010)** — не rate limit! | НЕ восстановился |
| Cerebras Llama 3.1 8B | **1** | 403 | **Cloudflare WAF (1010)** — не rate limit! | НЕ восстановился |
| HuggingFace Meta-Llama-3-8B-Instruct | **11** | 402 | **Кредиты исчерпаны** ($0.10/мес) | Восстановился |
| OpenRouter DeepSeek R1 0528 | **50** (лимит не достигнут) | - | Нет rate limit за 50 запросов (165с) | OK |
| Fireworks GPT-OSS-20B | **12** | 429 | **Rate limit** (настоящий 429) | Восстановился |
| Novita Llama 3.1 8B Instruct | **1** | 403 | **Cloudflare WAF (1010)** — не rate limit! | НЕ восстановился |

**Исключены:** GitHub Models GPT-4o Mini (150 RPD — слишком ценны), Cloudflare Llama 3.3 70B FP8 Fast (нативный API — нужен другой тест)

### Критическая находка: блокировка Cloudflare WAF

Groq, Cerebras и Novita вернули **HTTP 403 с кодом ошибки 1010** — это WAF Cloudflare, блокирующий запросы из Docker-контейнеров. Это НЕ rate limit. Business API через httpx работает, а прямой curl из Docker — нет. Вероятно разная TLS-отпечатка или User-Agent.

**Это значит:**
- Данные Блока 7 для Groq, Cerebras, Novita **невалидны** — не удалось протестировать реальные rate limits
- httpx-клиент Business API обходит эту WAF-защиту
- Тестирование rate limits требует прохождения через Business API или правильных TLS/UA заголовков

### Валидные данные по rate limit

- **Fireworks GPT-OSS-20B**: 12 запросов → 429 (настоящий rate limit). ~43 RPM burst, затем троттлинг. Восстановился за <3 мин.
- **OpenRouter DeepSeek R1 0528**: 50 запросов за 166с без лимита — DeepSeek R1 достаточно медленный (~3.3с/запрос), чтобы не достичь RPM-лимита (20)
- **HuggingFace Meta-Llama-3-8B-Instruct**: 11 запросов → 402 (кредиты, не rate limit). $0.10/мес бесплатного кредита исчерпан во время тестирования

## Назначение тегов

На основе эмпирических результатов тестирования:

| Провайдер + Модель | fast | json | code | reasoning | russian | lightweight | Назначенные теги |
|--------------------|:----:|:----:|:----:|:---------:|:-------:|:-----------:|-----------------|
| Groq Llama 3.3 70B Versatile | **Y** | **Y** | **Y** | - | **Y** | - | `fast`, `json`, `code`, `russian` |
| Cerebras Llama 3.1 8B | **Y** | **Y** | - | - | **Y** | **Y** | `fast`, `json`, `russian`, `lightweight` |
| HuggingFace Meta-Llama-3-8B-Instruct | - | ~Y* | - | - | **Y** | **Y** | `russian`, `lightweight` |
| Cloudflare Llama 3.3 70B FP8 Fast | - | **Y** | **Y** | - | **Y** | - | `json`, `code`, `russian` |
| OpenRouter DeepSeek R1 0528 | - | ~Y* | **Y** | **Y** | **Y** | - | `code`, `reasoning`, `russian` |
| GitHub Models GPT-4o Mini | **Y** | **Y** | - | - | **Y** | - | `fast`, `json`, `russian` |
| Fireworks GPT-OSS-20B | - | **Y** | **Y** | ~Y** | **Y** | - | `json`, `code`, `russian` |
| Novita Llama 3.1 8B Instruct | - | **Y** | - | - | **Y** | **Y** | `json`, `russian`, `lightweight` |

### Обоснование тегов

**`fast`** (среднее <3с на user_200 + user_1000):
- Groq Llama 3.3 70B Versatile: 1.1s
- GitHub Models GPT-4o Mini: 1.4s
- Cerebras Llama 3.1 8B: 2.0s

**`json`** (валидный JSON на >=2/3 тестов):
- Все провайдеры вернули валидный JSON на всех 3 тестах
- HuggingFace Meta-Llama-3-8B-Instruct: нет поддержки `response_format` в API, но модель всё равно генерирует JSON — условно
- OpenRouter DeepSeek R1 0528: валидный JSON, но медленно (30с+ на json_medium) — условно

**`code`** (>=70B или специализированная для кода):
- Groq Llama 3.3 70B Versatile (70B), Cloudflare Llama 3.3 70B FP8 Fast (70B), OpenRouter DeepSeek R1 0528 (671B MoE), Fireworks GPT-OSS-20B (специализированная для кода)
- GitHub Models GPT-4o Mini: способна, но не специализированная

**`reasoning`** (возвращает reasoning/reasoning_content с CoT):
- OpenRouter DeepSeek R1 0528: **Да** — поле `reasoning` с массивом `reasoning_details`
- Fireworks GPT-OSS-20B: **Частично** — reasoning встроен в `content` с `<|channel|>` тегами, нестандартный формат

**`russian`** (ответил на русском с хорошим качеством на обоих тестах):
- **ВСЕ провайдеры** ответили на русском с хорошим качеством (кроме таймаута OpenRouter)
- Главный сюрприз — даже 8B-модели выдали хороший русский

**`lightweight`** (<=8B):
- Cerebras Llama 3.1 8B, HuggingFace Meta-Llama-3-8B-Instruct, Novita Llama 3.1 8B Instruct

### Расхождения с ожиданиями (гипотеза до теста)

| Изменение | Ожидалось | Факт | Причина |
|-----------|-----------|------|---------|
| Cerebras `russian` | Нет | **Да** | 8B-модель ответила на хорошем русском — противоречит исследованию |
| HuggingFace `russian` | Нет | **Да** | Аналогично — 8B выдала хороший русский |
| Novita `russian` | Нет | **Да** | Аналогично |
| Cerebras `json` | Нет | **Да** | JSON валиден во всех 3 тестах |
| Novita `json` | Нет | **Да** | JSON валиден во всех 3 тестах |
| GitHub max_tokens | 4,000 | **16,384** | В плане были устаревшие данные |
| Fireworks `reasoning` | Да | **Частично** | Нестандартный формат (`<|channel|>` теги) |
| OpenRouter `reasoning_content` | Да | **Нет** | Использует поле `reasoning` вместо `reasoning_content` |

## Обнаруженные проблемы

### Баг: Business API игнорирует model_id при маршрутизации
При указании `model_id` в `/api/v1/prompts/process` Business API маршрутизирует к провайдеру с наивысшим reliability_score, а не к указанной модели. Наблюдалось при запросе model_id=1 (Groq Llama 3.3 70B Versatile), который постоянно маршрутизировался на Cerebras. Поле `fallback_used` показывает `false` даже при использовании другого провайдера.

### Баг: Несовпадение полей ответа OpenRouter
Текущий код проверяет `reasoning_content` в message, но OpenRouter DeepSeek R1 0528 возвращает `reasoning` (без суффикса `_content`). Массив `reasoning_details` тоже уникален для OpenRouter.

### Баг: Формат ответа Fireworks GPT-OSS-20B
Fireworks возвращает reasoning внутри `content` с проприетарными тегами (`<|channel|>analysis<|message|>...<|end|><|start|>`), а не в отдельном поле. Текущая логика fallback в `_parse_response()` не извлечёт реальный ответ.

### Проблема: Cloudflare WAF блокирует прямые API-вызовы из Docker
HTTP 403/1010 при прямых curl-запросах изнутри Docker-контейнеров. httpx-клиент Business API не затронут — вероятно Cloudflare WAF детектирует curl-специфичные TLS/UA сигнатуры.

### Проблема: Названия моделей в БД не совпадают с API
Cerebras зарегистрирован как "Llama 3.3 70B", но API отправляет `llama3.1-8b`. Fireworks зарегистрирован как "Llama 3.1 70B", но использует `gpt-oss-20b`. Novita зарегистрирован как "Llama 3.1 70B", но использует `llama-3.1-8b-instruct`.

## Рекомендации

1. **Исправить парсинг OpenRouter**: добавить поле `reasoning` в `_parse_response()` наряду с `reasoning_content`
2. **Исправить парсинг Fireworks**: вырезать теги `<|channel|>...<|end|><|start|>` для извлечения реального ответа
3. **Обновить seed.py**: исправить названия моделей для соответствия реальным API model ID
4. **Обновить дефолты max_tokens**: GitHub поддерживает 16,384 (не 4,000), Novita поддерживает 16,384 (не 4,096)
5. **Исследовать маршрутизацию model_id**: проверить что `model_id` в process prompt действительно форсирует конкретного провайдера
6. **Добавить мониторинг кредитов**: HuggingFace исчерпал $0.10 месячного кредита во время тестирования — нужен мониторинг
