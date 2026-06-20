# Диагностика провайдеров — Результаты (2026-06-20)

**Когда:** 2026-06-20
**Где:** gpu-1 (`/home/ssserver/works/free-ai-selector`), внутри работающего контейнера
`free-ai-selector-business-api` — прямой прогон по задеплоенному прод-коду.
**Чем:** модернизированный `provider_benchmark.py` (Rung 2: health-gate, таксономия
ошибок через `classify_error()`, warmup, registry-driven).
**Промпты:** `plain_short`, `json_short` (response_format=json_object), `russian_short`.
**Сырые данные:** [`2026-06-20-provider-diagnostic-raw.json`](2026-06-20-provider-diagnostic-raw.json).

## Health-gate (GET /models)

Допущено к замерам **14/15**. Единственный отвал на gate — **Scaleway** (`unhealthy`,
`/models` не отвечает).

## Сводная таблица (14 admitted)

| Провайдер | ok/3 | avg_s | Класс сбоя | Итог |
|-----------|:----:|:-----:|------------|------|
| Groq | 3 | 1.84 | — | ✅ работает |
| HuggingFace | 3 | 2.58 | — | ✅ работает |
| OpenRouter | 3 | 8.93 | — | ✅ работает (медленный) |
| Novita | 3 | 2.59 | — | ✅ работает |
| Cloudflare | 2 | 2.89 | transient:1 (json timeout) | ⚠️ JSON флапает |
| CloudflareQwen3 | 2 | 2.86 | capability:1 (invalid JSON) | ⚠️ JSON ломается |
| Fireworks | 2 | 3.75 | capability:1 (invalid JSON) | ⚠️ JSON ломается |
| Ollama-Gemma4-E2B | 1 | 1.53 | capability:2 (JSON + russian 0.26) | ⚠️ слабый JSON/RU |
| **Cerebras** | 0 | — | **transport:3 (404)** | ❌ **наш баг** |
| SambaNova | 0 | — | quota:3 (402) | 💳 нет кредитов |
| DeepSeek | 0 | — | quota:3 (402) | 💳 нет кредитов |
| Hyperbolic | 0 | — | quota:3 (402) | 💳 нет кредитов |
| GitHubModels | 0 | — | quota:3 (429) | 💳 rate limit |
| CloudflareGemma3 | 0 | — | transient:3 (410) | 🪦 модель удалена |

## Ключевые выводы

### 1. Премиса xqi устарела: из 4 транспортных багов остался 1

| Провайдер | bd-снимок 2026-06-19 | 2026-06-20 |
|-----------|----------------------|------------|
| Groq 413 | сломан | ✅ работает (фикс `MAX_OUTPUT_TOKENS=8192` в проде) |
| HuggingFace 422 | сломан | ✅ работает |
| Novita 400 | сломан | ✅ работает |
| **Cerebras 404** | сломан | ❌ **всё ещё сломан** |

Cerebras: health-gate (`GET /models`) проходит → ключ и base_url валидны; 404 на
`generate` → **неверный slug** `llama3.1-8b`. Чинить = сверить с Cerebras `/models`
и поправить `DEFAULT_MODEL`. Это единственная оставшаяся работа xqi.

### 2. Русский — отличный почти везде (эмпирика для bd-ttn)

`cyrillic_ratio` на `russian_short`: Groq 0.96, HuggingFace 0.98, Cloudflare 0.98,
CloudflareQwen3 0.96, Fireworks 0.97, OpenRouter 0.98. Тег `russian` можно осознанно
возвращать всем перечисленным. Исключения: Ollama-Gemma4-E2B (0.26 — «thinking»-модель
отвечает не по-русски) и Cerebras (нельзя проверить, пока 404).

### 3. JSON ненадёжен у части провайдеров (новое)

`json_short` (response_format=json_object) ломается у CloudflareQwen3, Fireworks,
Ollama (invalid JSON — кладут reasoning/мусор), и флапает у Cloudflare (timeout).
Тег `json` у этих провайдеров под вопросом.

### 4. Мёртвые модели/провайдеры

- **CloudflareGemma3** → `410 Gone` (Cloudflare убрал `@cf/google/gemma-3-12b-it`) —
  выкинуть из seed/registry.
- **Scaleway** → unhealthy на gate (выкинуть или чинить отдельно).
- quota-мертвы (402/429): SambaNova, DeepSeek, Hyperbolic, GitHubModels — внешнее,
  кодом не чинится.

### 5. Баг классификатора (новое)

`410 Gone` попадает в `transient` (ретраебельное), хотя это **постоянная** ошибка —
`classify_error()` не обрабатывает 410. Стоит добавить 410 → невозобновляемый класс.

## Скорректированный Rung 3

1. **Cerebras 404** — единственный реальный транспортный фикс (сверка с `/models`).
2. **Чистка мёртвого**: CloudflareGemma3 (410), Scaleway (unhealthy).
3. (опц.) `classify_error`: 410 → permanent, не transient.
4. (опц.) bd-ttn: вернуть тег `russian` по подтверждённым провайдерам.
