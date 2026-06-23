# Глубокая диагностика провайдеров — Результаты (2026-06-23)

**Метод:** тиерный `deep_benchmark.py` на gpu-1 (прод-контейнер `free-ai-selector-business-api`),
бюджет запросов под реальные free-tier лимиты (web-verified 2026-06-23).
**Объём:** 13 провайдеров, **116 замеров**. Сырьё: [`2026-06-23-deep-provider-diagnostic-raw.json`](2026-06-23-deep-provider-diagnostic-raw.json).
**Измерения:** speed×N, prompt-length (short/med/long), system-prompt, JSON (simple/complex),
russian (short/med), max_tokens (min/high), tools, raw-fields (reasoning/finish/usage).

## Статус провайдеров

**✅ Функционально работают (8):** Groq, Cerebras, HuggingFace, Cloudflare, CloudflareQwen3,
OpenRouter, Novita, Ollama.

**❌ Не работают на момент прогона (5):**
- SambaNova — 402 (free-tier по докам не требует оплаты, но аккаунт отдаёт 402 — состояние аккаунта)
- DeepSeek — 402 (grant истёк, pay-only)
- Hyperbolic — 402 ($1 trial потрачен)
- GitHubModels — **429** (исчерпан дневной лимит «150 per 86400s» — восстановится через сутки)
- Fireworks — **unhealthy** на этом прогоне (GET /models не ответил; 2026-06-20 работал → вероятно transient)

## Скорость (тёплая, avg)

1. Ollama 1.55s · Groq 1.72s · Cerebras 1.92s · Cloudflare 1.94s
2. Novita 2.29s · CloudflareQwen3 2.52s · HuggingFace 2.75s
3. **OpenRouter 22.95s** (deepseek-r1, reasoning — на порядок медленнее)

## Русский (cyrillic_ratio, порог 0.5)

- ✅ Хорошо (≥0.9): OpenRouter 0.97 · Novita 0.97 · CloudflareQwen3 0.97 · Groq 0.96 · Cloudflare 0.96 · HuggingFace 0.92
- ❌ Плохо: **Cerebras 0.49 / 0.40** · Ollama 0.27 *(см. критическую находку ниже)*

## JSON (response_format=json_object)

- ✅ Валидный: Groq (simple+complex) · HuggingFace · Novita · OpenRouter
- ❌ Невалидный: **Cerebras** (оба) · **CloudflareQwen3** (оба) · Ollama (simple)
- ⏱️ Cloudflare native (70B) — **таймаут** на обоих JSON (медленный/нестабильный на structured)

## Tools (function calling)

- ✅ Groq → `tool_call get_weather` (finish=tool_calls)
- ✅ OpenRouter → `tool_call get_weather` (finish=tool_calls)

## max_tokens (реальные лимиты)

- **Groq:** 400 раскрывает `max_tokens ≤ 32768`
- **Cerebras / Ollama:** тихо принимают `200000` (silent cap)
- **Cloudflare / Qwen3:** native API — проба пропущена (не OpenAI-формат)

## Raw-поля ответа (reasoning)

- **Groq:** `content, role` · finish=stop · reasoning нет → **чистый** не-reasoning
- **Cerebras (zai-glm-4.7):** `reasoning, role` (**content пуст!**) · finish=**length** · reasoning=True
- **OpenRouter (deepseek-r1):** `content, reasoning, reasoning_details, refusal, role` · finish=length
- **Ollama (gemma thinking):** `content, reasoning, role` · finish=length · reasoning=True

## 🔴 Критическая находка: reasoning-модели «протекают» при малом max_tokens

Cerebras `zai-glm-4.7`, CloudflareQwen3, Ollama, OpenRouter — **reasoning-модели**: ответ
сначала идёт в поле `reasoning` (размышление), и только потом — финальный `content`.

При **малом `max_tokens`** (в бенчмарке 64–512) размышление съедает весь бюджет → `content`
пустой → `finish_reason=length` → `base._parse_response()` отдаёт fallback на поле `reasoning`
(сырое размышление, часто на английском/смешанное и не-JSON). Отсюда:
- Cerebras russian 0.49/0.40 и невалидный JSON — **артефакт малого бюджета**, а не «не умеет».
  При `max_tokens=4096` (ручная проба 2026-06-20) Cerebras GLM давал **чистый русский и валидный JSON**.
- Реальный дефолт провайдера `MAX_OUTPUT_TOKENS=8192` → в обычной работе хватает.

**Но это реальный риск:** если вызывающий код запрашивает у reasoning-провайдера малый
`max_tokens` (например, 256 под JSON), он получит мусор-размышление вместо ответа.

### Два следствия

1. **Теги под вопросом** (подтверждает bead `48u`):
   - Cerebras `json` и `russian` — верны только при большом `max_tokens`; при малом — ломаются.
   - CloudflareQwen3 `json` — невалидный JSON даже на нормальном бюджете.
2. **Код-смелл в `_parse_response()`:** при `finish_reason=length` и пустом `content` fallback
   на `reasoning` отдаёт «мысли» как ответ. Для reasoning-моделей это вводит в заблуждение —
   стоит либо не подставлять reasoning при `length`, либо форсировать минимальный `max_tokens`
   для reasoning-провайдеров.

## Чистые vs reasoning (итоговая классификация по качеству)

- **Чистые, надёжные** (clean output, JSON+RU ок при любом бюджете): **Groq, HuggingFace, Novita**.
  Cloudflare native (70B) — чистый и хороший русский, но JSON нестабилен (таймауты).
- **Reasoning (нужен большой max_tokens, JSON рискован):** Cerebras (zai-glm-4.7),
  CloudflareQwen3, OpenRouter (deepseek-r1, к тому же медленный ~23s), Ollama (gemma, к тому же слабый RU).

## Рекомендации / follow-ups

1. **Cerebras теги** — пересмотреть: `json`/`russian` достоверны только при большом бюджете.
   Вариант: оставить, но в `MAX_OUTPUT_TOKENS`/роутере гарантировать reasoning-моделям ≥4096.
2. **`_parse_response()`** — не отдавать `reasoning` как ответ при `finish_reason=length`
   (новый bead-кандидат).
3. **bead `48u`** (json у reasoning) — подтверждён эмпирически: снять/уточнить `json` у
   CloudflareQwen3, Cerebras, Ollama; либо добавить strip-reasoning + повторную JSON-валидацию.
4. **Fireworks** — перепроверить (unhealthy на этом прогоне, ранее работал).
5. **GitHubModels** — 429 (дневной лимит); тестировать в начале суток или реже.
6. **SambaNova 402** — проверить состояние аккаунта (free-tier по докам без оплаты).
