# Исследование: Бенчмарк AI-провайдеров и Smart Prompt Routing

**Дата:** 2026-03-20
**Статус:** Исследование завершено, план реализации готов
**Автор:** Claude Code + bgs

---

## 1. Проблема

Текущая маршрутизация в `ProcessPromptUseCase` выбирает AI-провайдера по единому `effective_reliability_score` — агрегированной метрике, не учитывающей характеристики конкретного запроса. На практике провайдеры ведут себя радикально по-разному в зависимости от:

- **Размера промпта** — Cerebras отвечает за 2с на 7500 токенов, Cloudflare таймаутит
- **Формата ответа** — Groq выдаёт 100% валидный JSON, остальные 33–67%
- **Комбинации** — MEDIUM+JSON проблемен для всех кроме Groq

Без учёта этих факторов система может отправить длинный промпт на Cloudflare (таймаут) или JSON-запрос на HuggingFace (не поддерживает), хотя есть более подходящие провайдеры.

---

## 2. Исследование: методология бенчмарка

### 2.1 Параметры тестирования

| Параметр | Значение |
|----------|----------|
| Провайдеров | 12 (все зарегистрированные) |
| Промптов | 3: SHORT (~15 tok), MEDIUM (~1000 tok), LONG (~7500 tok) |
| Форматов | 2: PLAIN, JSON (`response_format: json_object`) |
| Тестов всего | 72 (12 × 3 × 2) |
| Среда | Docker Compose, localhost |
| Скрипт | `scripts/provider_benchmark.py` (внутри контейнера business-api) |
| Таймаут | 30с (провайдер default), 90с (benchmark script) |
| Пауза между тестами | 2с (rate limit protection) |

### 2.2 Промпты

**SHORT (~15 токенов):**
```
What is 2+2? Answer in one word.
```

**MEDIUM (~1000 токенов):**
Код-ревью сценарий: анализ 10 архитектурных проблем REST API на FastAPI, запрос severity rating, root cause analysis, refactoring steps, effort estimation, roadmap для команды из 4 разработчиков.

**LONG (~7500 токенов):**
Архитектурная трансформация SaaS-компании: монолит Ruby on Rails 450K строк, 2800 таблиц, 180K DAU, 65 разработчиков. Запрос 6-частного плана миграции (DDD, strangler fig, K8s, observability, team topology, risk mitigation).

### 2.3 Метрики

- `response_time_sec` — время от отправки до получения ответа
- `response_length` — длина ответа в символах
- `json_valid` — для JSON формата: парсится ли ответ как валидный JSON
- `status` — success / error / skipped
- `error_message` — детали ошибки (HTTP код, таймаут)

---

## 3. Результаты бенчмарка

### 3.1 Доступность провайдеров

| Провайдер | API Key | Health Check | Генерация |
|-----------|:-------:|:------------:|:---------:|
| Groq | OK | HEALTHY | 6/6 OK |
| Cerebras | OK | HEALTHY | 6/6 OK |
| SambaNova | OK | HEALTHY | 5/6 OK |
| HuggingFace | OK | HEALTHY | 3/3 OK (JSON skip) |
| Cloudflare | OK | HEALTHY | 3/6 OK |
| DeepSeek | OK | HEALTHY | **0/6 — 402 Payment Required** |
| OpenRouter | OK | HEALTHY | 6/6 OK (но проблемы) |
| GitHubModels | OK | HEALTHY | 6/6 OK |
| Fireworks | OK | HEALTHY | 6/6 OK |
| Hyperbolic | OK | HEALTHY | **0/3 — 402 Payment Required** |
| Novita | OK | HEALTHY | 6/6 OK |
| Scaleway | OK | HEALTHY | 6/6 OK |

**DeepSeek и Hyperbolic** — кончились бесплатные кредиты.

### 3.2 Контекстные окна моделей

| Провайдер | Модель | Контекст | 1K tok | 7.5K tok |
|-----------|--------|----------|:------:|:--------:|
| Groq | llama-3.3-70b-versatile | 128K | OK | OK |
| Cerebras | llama3.1-8b | **8K (free)** | OK | Риск |
| SambaNova | Llama-3.3-70B-Instruct | 128K | OK | OK |
| HuggingFace | Meta-Llama-3-8B-Instruct | **8K** | OK | Риск |
| Cloudflare | llama-3.3-70b-instruct-fp8 | 128K | OK | OK |
| DeepSeek | deepseek-chat | 128K | OK | OK |
| OpenRouter | deepseek-r1-0528 | 164K | OK | OK |
| GitHubModels | gpt-4o-mini | **8K лимит GitHub** | OK | Риск |
| Fireworks | gpt-oss-20b | 131K | OK | OK |
| Hyperbolic | Llama-3.3-70B-Instruct | 131K | OK | OK |
| Novita | llama-3.1-8b-instruct | 16K | OK | OK |
| Scaleway | llama-3.1-70b-instruct | 128K | OK | OK |

### 3.3 Полные результаты: PLAIN формат

| Провайдер | SHORT (time/chars) | MEDIUM (time/chars) | LONG (time/chars) |
|-----------|:------------------:|:-------------------:|:-----------------:|
| **Groq** | 0.83s / 5 | 3.58s / 4,643 | 5.42s / 9,891 |
| **Cerebras** | 0.76s / 5 | 1.59s / 5,034 | 2.07s / 10,784 |
| **SambaNova** | 1.37s / 5 | 6.39s / 4,521 | 7.17s / 9,708 |
| HuggingFace | 1.18s / 5 | 11.37s / 5,013 | 21.64s / 9,347 |
| Cloudflare | 1.06s / 5 | 29.00s / 4,505 | **TIMEOUT 30s** |
| DeepSeek | **402** | **402** | **402** |
| OpenRouter | 2.37s / 4 | 10.03s / **4** | 92.99s / **4** |
| GitHubModels | 3.78s / 5 | 14.40s / 4,750 | 23.63s / 9,472 |
| Fireworks | 1.50s / 4 | 9.78s / 3,134 | 21.55s / 5,741 |
| Hyperbolic | **402** | **402** | **402** |
| Novita | 1.15s / 5 | 12.36s / 5,172 | 18.68s / 8,301 |
| Scaleway | 0.62s / 5 | 12.86s / 4,591 | 14.34s / 5,472 |

### 3.4 Полные результаты: JSON формат

| Провайдер | SHORT (time/valid) | MEDIUM (time/valid) | LONG (time/valid) |
|-----------|:------------------:|:-------------------:|:-----------------:|
| **Groq** | 0.68s / **YES** | 3.36s / **YES** | 4.45s / **YES** |
| **Cerebras** | 0.87s / YES | 1.29s / **NO** | 2.01s / YES |
| **SambaNova** | 1.50s / YES | **400 ERR** | 4.59s / YES |
| HuggingFace | — skip — | — skip — | — skip — |
| Cloudflare | 0.91s / YES | **TIMEOUT** | **TIMEOUT** |
| DeepSeek | **402** | **402** | **402** |
| OpenRouter | 9.93s / YES | 140.50s / **NO** | 74.64s / **NO** |
| GitHubModels | 2.32s / YES | 15.25s / **NO** | 17.95s / YES |
| Fireworks | 2.02s / **NO** | 9.89s / **NO** | 8.85s / YES |
| Hyperbolic | — skip — | — skip — | — skip — |
| Novita | 1.31s / YES | 13.67s / **NO** | 22.90s / YES |
| Scaleway | 0.67s / YES | 13.11s / **NO** | 16.15s / YES |

### 3.5 Бесплатные лимиты провайдеров

| Провайдер | Контекст | Rate Limits | Бесплатный объём |
|-----------|----------|-------------|-----------------|
| Groq | 128K | 30 RPM, ~6K TPM | 14,400 req/день |
| Cerebras | 8K (free) | — | 1M токенов/день |
| SambaNova | 128K | 20 RPM | 20M токенов/день |
| HuggingFace | 8K | ~100 req/час | Без явного лимита |
| Cloudflare | 128K | — | 10,000 Neurons/день |
| DeepSeek | 128K | ~10-30 RPM | 5M токенов при регистрации |
| OpenRouter | 164K | 20 RPM | 50 req/день (без кредитов) |
| GitHubModels | 8K (лимит) | — | 150 req/день |
| Fireworks | 131K | 10 RPM | $1 стартовый кредит |
| Hyperbolic | 131K | 60 RPM | $1 стартовый кредит |
| Novita | 16K | — | $0.50 стартовый кредит |
| Scaleway | 128K | 100 RPM, 200K TPM | 1M токенов (бета) |

---

## 4. Шесть рейтингов провайдеров

### 4.1 Рейтинг скорости (avg PLAIN, все размеры)

| Место | Провайдер | Среднее время |
|:-----:|-----------|:------------:|
| 1 | **Cerebras** | **1.47s** |
| 2 | **Groq** | **3.28s** |
| 3 | **SambaNova** | **4.98s** |
| 4 | Scaleway | 9.27s |
| 5 | Novita | 10.73s |
| 6 | Fireworks | 10.94s |
| 7 | HuggingFace | 11.40s |
| 8 | GitHubModels | 13.94s |
| 9 | Cloudflare | ~15s (таймауты) |
| 10 | OpenRouter | 35.13s |

### 4.2 Рейтинг надёжности (% успешных)

| Место | Провайдер | Успех |
|:-----:|-----------|:-----:|
| 1 | Groq, Cerebras, Scaleway, Novita, Fireworks, GitHubModels, OpenRouter | 100% |
| 8 | HuggingFace | 100% (JSON N/A) |
| 9 | SambaNova | 83% |
| 10 | Cloudflare | 50% |
| 11 | DeepSeek | 0% |
| 12 | Hyperbolic | 0% |

### 4.3 Рейтинг JSON-валидности

| Место | Провайдер | Валидность |
|:-----:|-----------|:----------:|
| 1 | **Groq** | **100% (3/3)** |
| 2 | Cerebras, SambaNova, GitHubModels, Novita, Scaleway | 67% |
| 7 | Cloudflare, OpenRouter, Fireworks | 33% |
| 10 | HuggingFace, Hyperbolic | Не поддерживают |

### 4.4 Рейтинг объёма ответа (avg chars PLAIN)

| Место | Провайдер | Avg chars |
|:-----:|-----------|:---------:|
| 1 | **Cerebras** | 5,274 |
| 2 | **Groq** | 4,846 |
| 3 | HuggingFace | 4,788 |
| 4 | SambaNova | 4,745 |
| 5 | GitHubModels | 4,742 |
| 6 | Novita | 4,493 |
| 7 | Scaleway | 3,356 |
| 8 | Fireworks | 2,960 |
| 9 | Cloudflare | 2,255 |
| 10 | OpenRouter | **4** (пустые!) |

### 4.5 Рейтинг длинных промптов (LONG PLAIN)

| Место | Провайдер | Время | Chars |
|:-----:|-----------|:-----:|:-----:|
| 1 | **Cerebras** | 2.07s | 10,784 |
| 2 | **Groq** | 5.42s | 9,891 |
| 3 | SambaNova | 7.17s | 9,708 |
| 4 | Scaleway | 14.34s | 5,472 |
| 5 | Novita | 18.68s | 8,301 |
| 6 | Fireworks | 21.55s | 5,741 |
| 7 | HuggingFace | 21.64s | 9,347 |
| 8 | GitHubModels | 23.63s | 9,472 |
| 9 | OpenRouter | 92.99s | 4 |
| 10 | Cloudflare | TIMEOUT | 0 |

### 4.6 Общий композитный рейтинг

Формула: Скорость×30% + Надёжность×25% + JSON×20% + Контент×15% + Длинные×10%

| Место | Провайдер | Балл | Tier |
|:-----:|-----------|:----:|:----:|
| 1 | **Groq** | **9.45** | S |
| 2 | **Cerebras** | **9.40** | S |
| 3 | **SambaNova** | **7.65** | A |
| 4 | Scaleway | 7.30 | A |
| 5 | Novita | 7.05 | A |
| 6 | GitHubModels | 6.00 | B |
| 7 | Fireworks | 5.55 | B |
| 8 | HuggingFace | 5.30 | B |
| 9 | OpenRouter | 3.75 | C |
| 10 | Cloudflare | 2.85 | C |
| 11 | DeepSeek | 0.00 | D |
| 12 | Hyperbolic | 0.00 | D |

---

## 5. Ключевые находки

### 5.1 MEDIUM + JSON — самая проблемная комбинация

Только **Groq** выдаёт валидный JSON на промптах ~1000 токенов. У 6 из 9 провайдеров JSON невалиден именно на MEDIUM. Парадокс: на LONG промпте JSON валиден у 7/8 провайдеров.

### 5.2 OpenRouter (DeepSeek R1) — почти пустые PLAIN ответы

На MEDIUM и LONG PLAIN запросах OpenRouter возвращает ответ длиной **4 символа** ("Four"). Модель DeepSeek R1 через OpenRouter ведёт себя корректно только с JSON format.

### 5.3 Cloudflare — таймауты на длинных промптах

Cloudflare Workers AI таймаутит (30с) на MEDIUM JSON, LONG PLAIN и LONG JSON. Работает только на SHORT и MEDIUM PLAIN (еле: 29с из 30с лимита).

### 5.4 Скорость Cerebras vs Groq

Cerebras стабильно быстрее Groq (1.47s vs 3.28s avg), но Groq лидирует по JSON-валидности (100% vs 67%). Для PLAIN запросов Cerebras оптимален, для JSON — Groq.

---

## 6. Анализ: нужны ли все 6 пар счётчиков?

При проектировании per-category tracking рассмотрели 6 пар счётчиков (SHORT/MEDIUM/LONG × PLAIN/JSON). Анализ показал, что 4 из 6 — избыточны:

| Комбинация | Нужен свой счётчик? | Причина |
|-----------|:-------------------:|---------|
| SHORT PLAIN | **Нет** | Все провайдеры справляются ≈ одинаково |
| SHORT JSON | **Нет** | ≈ SHORT PLAIN, JSON валиден у 9/10 |
| MEDIUM PLAIN | **Нет** | Рейтинг ≈ идентичен LONG PLAIN |
| MEDIUM JSON | **→ `json_*`** | Groq единственный с 100% валидным JSON |
| LONG PLAIN | **→ `long_*`** | Cloudflare timeout, OpenRouter пустой |
| LONG JSON | **→ `long_*` + `json_*`** | ≈ LONG PLAIN по рейтингу |

**Итого: 2 оси вместо 6 = 6 полей вместо 18+**

---

## 7. Решение: Smart Prompt Routing

### 7.1 Архитектура

```
execute(request)
  ├─ get_all_models() + filter + quality_gate     ← без изменений
  ├─ ★ classify_prompt(prompt_text, response_format)
  │     → PromptClassification(size=SHORT|MEDIUM|LONG, needs_json=bool)
  ├─ ★ _get_routing_score(model, classification)
  │     → выбирает json/long/base score
  ├─ ★ smart_sort(models, classification)
  │     → пересортировка по routing_score
  ├─ _build_candidate_models()                     ← без изменений
  └─ fallback loop                                 ← без изменений
```

### 7.2 Новые поля в БД (6 штук)

```sql
ALTER TABLE ai_models ADD COLUMN json_success_count INTEGER DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN json_failure_count INTEGER DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN json_total_response_time DECIMAL DEFAULT 0.0;
ALTER TABLE ai_models ADD COLUMN long_success_count INTEGER DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN long_failure_count INTEGER DEFAULT 0;
ALTER TABLE ai_models ADD COLUMN long_total_response_time DECIMAL DEFAULT 0.0;
```

### 7.3 Логика маршрутизации

```
SHORT  + PLAIN  →  effective_reliability_score   (уже есть, без изменений)
SHORT  + JSON   →  json_reliability_score        (новый)
MEDIUM + PLAIN  →  effective_reliability_score   (уже есть, без изменений)
MEDIUM + JSON   →  json_reliability_score        (новый, ключевой!)
LONG   + PLAIN  →  long_reliability_score        (новый)
LONG   + JSON   →  avg(long_reliability, json_reliability)
```

**4 из 6 комбинаций** покрываются существующим `effective_reliability_score` без новых данных.

### 7.4 Переиспользование (DRY)

| Существующий компонент | Как переиспользуем |
|-----------------------|-------------------|
| `ReliabilityService.calculate()` | Та же формула для json/long scores |
| `increment_success/failure` | Добавляем параметры `is_json`, `is_long_prompt` |
| `effective_reliability_score` | Базовый score для SHORT/MEDIUM PLAIN |
| `PromptHistory` | Уже хранит все данные для анализа |

### 7.5 Что даёт smart routing (ожидаемый эффект)

| Запрос | Сейчас (по reliability) | После (по smart score) |
|--------|------------------------|----------------------|
| SHORT + PLAIN | Кто выше по общему скору | Без изменений (все ≈ равны) |
| MEDIUM + JSON | Может выбрать Cerebras (fast, но JSON fail) | **Groq** (100% JSON valid) |
| LONG + PLAIN | Может выбрать Cloudflare (таймаут) | **Cerebras** (2.07s, 10K chars) |
| LONG + JSON | Случайный порядок | **Cerebras/Groq** (быстрые + JSON OK) |

---

## 8. План реализации

### Файлы для изменения

| # | Файл | Действие | LOC |
|---|------|----------|-----|
| 1 | Alembic миграция | Создать — 6 новых полей | ~15 |
| 2 | `data-api/.../database/models.py` | Изменить — 6 полей в ORM | ~6 |
| 3 | `data-api/.../domain/models.py` | Изменить — 6 полей + 2 computed properties | ~20 |
| 4 | `data-api/.../repositories/ai_model_repository.py` | Изменить — increment_json/long | ~20 |
| 5 | `data-api/app/api/v1/models.py` | Изменить — params is_json, is_long | ~10 |
| 6 | `data-api/app/api/v1/schemas.py` | Изменить — json/long scores в response | ~6 |
| 7 | `business-api/app/domain/prompt_classifier.py` | Создать — classify_prompt() | ~25 |
| 8 | `business-api/.../process_prompt.py` | Изменить — classify + smart_sort | ~30 |
| 9 | `scripts/seed_benchmark_scores.py` | Создать — предзаполнение из бенчмарка | ~40 |

**Итого:** ~170 LOC новых + ~60 LOC изменений

### Принципы реализации

- **SSOT:** ReliabilityService — единственная формула расчёта скора
- **DRY:** Не дублируем формулу, переиспользуем для json/long
- **KISS:** Классификация по `len(prompt)`, пороги: 400 / 12000 chars
- **YAGNI:** Не добавляем авто-обновление, ML-классификацию, per-size decay
- **SRP:** Классификатор, скоры, сортировка — отдельные компоненты
- **Обратная совместимость:** `is_json=False, is_long=False` по умолчанию

### Верификация

1. `make migrate` — применить миграцию
2. `python scripts/seed_benchmark_scores.py` — предзаполнить из бенчмарка
3. `make test` — существующие тесты не сломаны
4. `make logs-business | grep smart_routing` — классификация в логах
5. Ручной тест: SHORT, MEDIUM+JSON, LONG → проверить правильный выбор модели

---

## 9. Приложение: скрипты бенчмарка

- `scripts/provider_benchmark.py` — основной скрипт бенчмарка (все 12 провайдеров)
- `scripts/provider_benchmark_part2.py` — дополнительный прогон (GitHubModels LONG, Fireworks, Hyperbolic, Novita, Scaleway)
- Результаты сохраняются в `benchmark_results.json` / `benchmark_results_part2.json` внутри контейнера business-api
