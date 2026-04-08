# Model Tags Benchmark — Test Plan

**Date:** 2026-04-08
**Goal:** Determine optimal tags for 12 AI models based on empirical testing of prompt lengths, JSON support, Russian language quality, rate limits, response fields, and max_tokens limits.

## Context

Previous ad-hoc tests (2026-04-08) revealed that most "failures" on long prompts were caused by **rate limits and circuit breakers**, not prompt length. This plan designs a controlled experiment to isolate variables and produce reliable data for tag assignment.

## Lessons from Previous Tests

| Problem | Root Cause | Fix in v2 |
|---------|-----------|-----------|
| Providers fallback on "working" models | Rate limit from rapid sequential requests | 20s pause between requests to same provider |
| Groq always FB | 429 with retry_after ~30min | Restart services, wait 30min before testing Groq |
| Fireworks always FB | Circuit breaker open from prior failures | `make down && make up` before test |
| OpenRouter R1 returns "None" (4 chars) | Bug: field `reasoning` not parsed (only `reasoning_content`) | Log ALL message fields in raw response |
| Can't distinguish "prompt too long" from "rate limit" | Requests sent back-to-back | 1 request → pause → next |
| max_tokens=2048 limits response | Global default in base.py | Document as test constant; test real max separately |
| Can't see raw response fields | `_parse_response()` hides fields | Direct curl to providers via docker exec |
| Unclear which providers validate max_tokens | Never tested | Dedicated max_tokens validation block |

## Providers Under Test

| ID | Provider | Model | Status (as of test start) |
|----|----------|-------|--------------------------|
| 1 | Groq | llama-3.3-70b-versatile | Check with /providers/test |
| 2 | Cerebras | llama3.1-8b | Usually OK |
| 4 | HuggingFace | Meta-Llama-3-8B-Instruct | Usually OK |
| 5 | Cloudflare | llama-3.3-70b-instruct-fp8-fast | Timeout-prone |
| 6 | DeepSeek | deepseek-chat | 402 (credits exhausted) |
| 7 | OpenRouter | deepseek-r1-0528 | OK but slow |
| 8 | GitHubModels | gpt-4o-mini | OK, 150 RPD limit |
| 9 | Fireworks | gpt-oss-20b | Check after restart |
| 10 | Hyperbolic | Llama-3.3-70B-Instruct | 402 (credits exhausted) |
| 11 | Novita | llama-3.1-8b-instruct | Usually OK |
| 12 | Scaleway | llama-3.1-70b-instruct | 403 (forbidden) |
| 3 | SambaNova | Meta-Llama-3.3-70B-Instruct | 402 (credits exhausted) |

**Active providers (expected):** 1, 2, 4, 5, 7, 8, 9, 11

## Block 0: Preparation (2 min)

1. `make down && make up` — reset all circuit breakers and rate limit cooldowns
2. Wait 2 min for warmup + migrations + health checks
3. `POST /api/v1/providers/test` — confirm which providers are alive
4. Record list of alive providers → only test those
5. Record timestamp of test start

## Block 1: Raw Response Fields Discovery (~2 min)

**Goal:** Document ALL fields returned by each provider in `choices[0].message` and `usage`.

**Method:** Direct HTTP requests from inside business-api container using provider API keys from env vars. Short prompt: `"Say hello in one word."`

**For each alive provider, record:**

```
message fields:
  - field name
  - type (string, list, dict, null)
  - value preview (first 100 chars)

usage fields:
  - prompt_tokens
  - completion_tokens
  - total_tokens
  - reasoning_tokens (if present)
  - any other fields

choices[0] fields:
  - finish_reason
  - index
  - any other fields

top-level response fields:
  - id, object, model, created, system_fingerprint, etc.
```

**Output:** `docs/research/2026-04-08-provider-response-fields.json`

### Expected Results — Block 1

| Provider | message fields | usage extras | finish_reason | id format | Notable differences |
|----------|---------------|-------------|---------------|-----------|-------------------|
| Groq | `role`, `content` | `queue_time`, `prompt_time`, `completion_time`, `total_time` (float seconds) | `stop`, `length` | `chatcmpl-xxx` | `x_groq` top-level object with internal request ID; `system_fingerprint` present |
| Cerebras | `role`, `content` | `time_info` object (`queue_time`, `inference_time`, `total_time`) | `stop`, `length` | `chatcmpl-xxx` | `system_fingerprint` present |
| HuggingFace | `role`, `content` | Standard only (`prompt_tokens`, `completion_tokens`, `total_tokens`) | `stop`, `length`, **`eos_token`** | Empty string `""` or UUID | **No `system_fingerprint`**; `id` may be empty; `eos_token` is non-standard finish_reason |
| Cloudflare | `role`, `content` | Standard but **values may be 0** (unreliable) | `stop`, `length` | UUID (no `chatcmpl-` prefix) | **No `system_fingerprint`**; usage unreliable; native API format completely different |
| OpenRouter | `role`, `content`, **`reasoning_content`** | `prompt_tokens_details` (`cached_tokens`), `completion_tokens_details` (**`reasoning_tokens`**) | `stop`, `length` | `gen-xxx` | **`reasoning_content`** in message (key field for R1); `provider` top-level field; `model` = full path `deepseek/deepseek-r1-0528` |
| GitHub Models | `role`, `content`, `refusal` | `prompt_tokens_details` (`cached_tokens`, `audio_tokens`), `completion_tokens_details` (`reasoning_tokens`=0) | `stop`, `length`, `content_filter` | `chatcmpl-xxx` | `refusal` field in message; `service_tier` top-level; closest to OpenAI standard (Azure backend) |
| Fireworks | `role`, `content`, **`reasoning_content`** | Standard; may include `reasoning_tokens` | `stop`, `length` | `chatcmpl-xxx` or UUID | **`reasoning_content`** for gpt-oss-20b; `content` may be empty string `""` (not null) when reasoning-only; **no `system_fingerprint`** |
| Novita | `role`, `content` | Standard only | `stop`, `length` | Standard | **No `system_fingerprint`**; minimal, closest to bare OpenAI format |

**Key things to verify empirically:**
- Does OpenRouter R1 put reasoning in `reasoning_content` or inside `<think>` tags in `content`?
- Does Fireworks return `content: ""` or `content: null` for reasoning-only responses?
- Are Cloudflare usage values actually 0?

## Block 2: max_tokens Validation (~3 min)

**Goal:** Determine real max_tokens limit for each provider.

**Method per provider:**

1. Send request with `max_tokens=99999` + short prompt "Say hello"
2. If 400/422 → parse error message for actual max limit
3. If 200 → provider accepts or silently caps
4. Send request with documented max_tokens → verify success
5. Send request with `max_tokens=1` → verify minimal response

### Expected Results — Block 2

| Provider | Expected Max Output | Context Window | max_tokens=99999 | max_tokens=1 | Default if omitted | Source |
|----------|-------------------|----------------|-------------------|--------------|-------------------|--------|
| Groq | **32,768** | 131,072 | 400 error: `"max_tokens must be <= 32768"` (reveals limit) | OK, 1 token | Not documented | console.groq.com/docs/model/llama-3.3-70b-versatile |
| Cerebras | **8,192** | 8K (free) / 32K (paid) | Silently capped or error (undocumented) | OK | Not documented | inference-docs.cerebras.ai |
| HuggingFace | **~8,192** (shared with input) | 8,192 total | Validation error: input + max_new_tokens > 8192 | OK | **20 tokens (!)** — very low default | huggingface.co/docs |
| Cloudflare | **~24,000** | 24,000 (much less than native 128K) | Silently capped | OK | **256 tokens** — needs explicit override | developers.cloudflare.com/workers-ai |
| OpenRouter | **65,536** | 163,840 | Capped or error | OK | Not documented | openrouter.ai/deepseek/deepseek-r1-0528 |
| GitHub Models | **4,000** | 8K input + 4K output (free tier) | Error: exceeds per-request limit | OK | Not documented | docs.github.com/github-models |
| Fireworks | **~131,072** (undocumented, = context) | 131,072 | Probably OK (within context) | OK | Not documented | fireworks.ai/models/fireworks/gpt-oss-20b |
| Novita | **16,384** | 16,384 (less than native 128K) | Capped or error | OK | Not documented | novita.ai/docs |

**Key things to verify empirically:**
- Does Groq error message reveal exact max_tokens? (expected: yes)
- Does HuggingFace use `max_new_tokens` instead of `max_tokens`? (expected: yes)
- Does Cloudflare silently cap or return error?
- What is Fireworks' actual max for gpt-oss-20b? (Use `max_completion_tokens` for reasoning models)

**Output:** Table confirming or correcting each value.

## Block 3: System Prompt Length (~12 min)

**Goal:** How does system prompt length affect response quality and success rate?

**Fixed user prompt:** `"What is Python? Answer in exactly 2 sentences."`

| Test ID | System Prompt | Chars |
|---------|--------------|-------|
| sys_0 | (none) | 0 |
| sys_500 | Expert Python developer role description | ~500 |
| sys_1500 | Detailed coding standards + style guide | ~1500 |
| sys_3000 | Full project context + rules + examples | ~3000 |

**Pause:** 20s between requests to same provider.

**Metrics per request:**

```
provider, model, self_or_fb, time_s, resp_chars,
resp_preview (100ch), attempts, http_status,
prompt_tokens, completion_tokens, finish_reason
```

### Expected Results — Block 3

| Provider | sys_0 | sys_500 | sys_1500 | sys_3000 | Notes |
|----------|-------|---------|----------|----------|-------|
| Groq (70B) | OK, <2s | OK, <2s | OK, <3s | OK, <3s | Fastest provider. All sizes well within 131K context. No issues expected. |
| Cerebras (8B) | OK, <1s | OK, <1s | OK, <2s | OK, <2s | Very fast inference. 8K context limit — sys_3000 ≈ 800 tokens, still fits. |
| HuggingFace (8B) | OK, 2-5s | OK, 2-5s | OK, 3-6s | OK, 3-6s | Slower (shared infra). May have cold start on first request. 8K context OK. |
| Cloudflare (70B) | OK, 3-8s | OK, 3-10s | OK, 5-15s | **Timeout risk** | Timeout-prone. 24K context limit — sys_3000 fits but response time may spike. **10K neuron/day limit may exhaust after 2-3 requests to 70B.** |
| OpenRouter R1 | OK, 5-15s | OK, 5-20s | OK, 8-25s | OK, 10-30s | Slow (reasoning model). `reasoning_content` will contain CoT. Response time dominated by reasoning, not prompt size. |
| GitHub (4o-mini) | OK, 1-3s | OK, 1-3s | OK, 2-4s | OK, 2-4s | Stable. 8K input limit — sys_3000 ≈ 800 tokens, fits. 15 RPM limit — pace requests. |
| Fireworks (20B) | OK, 2-5s | OK, 2-5s | OK, 3-6s | OK, 3-8s | Reasoning model — `reasoning_content` may appear. `content` may be empty. |
| Novita (8B) | OK, 1-3s | OK, 1-3s | OK, 2-4s | OK, 2-4s | 16K context — all sizes fit comfortably. |

**Risk:** Cloudflare neuron limit may cause failures mid-block. If Cloudflare fails after 2-3 requests, it's neuron exhaustion, not prompt length.

## Block 4: User Prompt Length (~15 min)

**Goal:** How does user prompt length affect response quality and success rate?

**No system prompt.**

| Test ID | User Prompt | Chars | Description |
|---------|------------|-------|-------------|
| user_200 | Simple question | ~200 | "Explain machine learning in 2 sentences" |
| user_1000 | Detailed question | ~1000 | Multi-topic analysis request |
| user_2000 | Complex task | ~2000 | Detailed essay prompt with structure |
| user_3000 | Very complex | ~3000 | Multi-section analysis with constraints |
| user_5000 | Maximum | ~5000 | Full analysis + sub-questions + examples |

**Pause:** 20s between requests to same provider.

**Same metrics as Block 3.**

### Expected Results — Block 4

| Provider | user_200 | user_1000 | user_2000 | user_3000 | user_5000 | Notes |
|----------|----------|-----------|-----------|-----------|-----------|-------|
| Groq (70B) | OK | OK | OK | OK | OK | 131K context. All sizes trivial. Speed: <3s for all. |
| Cerebras (8B) | OK | OK | OK | OK | **Context risk** | 8K context (free). user_5000 ≈ 1300 tokens input, but with max_tokens=2048 output → ~3300 total. Fits, but less headroom. |
| HuggingFace (8B) | OK | OK | OK | OK | **Context risk** | Same 8K limit. user_5000 + max_tokens may approach limit. Response may be truncated. |
| Cloudflare (70B) | OK | OK | Timeout risk | Timeout risk | **Timeout + neuron risk** | 24K context fits, but response time scales poorly. Neuron quota likely exhausted by this block. |
| OpenRouter R1 | OK, slow | OK, slow | OK, slow | OK, slow | OK, slow | 163K context. No size issues. Speed: 10-30s regardless of input length (dominated by reasoning). |
| GitHub (4o-mini) | OK | OK | OK | OK | OK | 8K input limit. user_5000 ≈ 1300 tokens — fits. 150 RPD — budget 5 requests here. |
| Fireworks (20B) | OK | OK | OK | OK | OK | 131K context. No issues expected. |
| Novita (8B) | OK | OK | OK | OK | OK | 16K context. user_5000 ≈ 1300 tokens — fits easily. |

**Key hypothesis:** No provider should fail on prompt length alone (max test = 5000 chars ≈ 1300 tokens). Failures indicate rate limits or infra issues, not prompt-length limits.

## Block 5: JSON Format (~8 min)

**Goal:** Validate JSON response support per provider.

| Test ID | Prompt | response_format | Chars |
|---------|--------|----------------|-------|
| json_short | "List 3 programming languages with year" | `{"type":"json_object"}` | ~50 |
| json_medium | Multi-field structured data request | `{"type":"json_object"}` | ~1000 |
| json_ru | "Перечисли 3 города России с населением" | `{"type":"json_object"}` | ~60 |

**Additional metrics:**

```
json_valid: bool (is response valid JSON?)
json_structure: brief description of returned structure
provider_supports_json: bool (SUPPORTS_RESPONSE_FORMAT flag)
```

### Expected Results — Block 5

| Provider | API supports json_object | json_short | json_medium | json_ru | JSON quality | Notes |
|----------|------------------------|------------|-------------|---------|-------------|-------|
| Groq (70B) | **Yes** (+ json_schema) | Valid JSON | Valid JSON | Valid JSON | **Reliable** | 70B follows format instructions well. Also supports structured output with schema. |
| Cerebras (8B) | **Yes** (basic) | Likely valid | **May break** | **May break** | **Unreliable** | 8B models often produce malformed JSON: unclosed brackets, trailing commas, free text mixed in. |
| HuggingFace (8B) | **No** (parameter ignored) | **Unreliable** | **Likely invalid** | **Likely invalid** | **Unreliable** | response_format not supported — model gets no JSON enforcement. 8B Llama produces poor JSON without guidance. |
| Cloudflare (70B) | **Yes** (+ json_schema) | Valid JSON | Valid JSON | Valid JSON | **Reliable** | Same 70B model as Groq — reliable JSON. But neuron limit may cause failure before reaching this block. |
| OpenRouter R1 | **Yes** (proxied) | **Problematic** | **Problematic** | **Problematic** | **Problematic** | DeepSeek R1 generates `<think>` blocks before answer. Even with json_object mode, reasoning-content may interfere. Need to extract JSON from final content, ignoring reasoning_content. |
| GitHub (4o-mini) | **Yes** (+ structured output) | Valid JSON | Valid JSON | Valid JSON | **Excellent** | Best JSON producer. Native OpenAI structured output support. |
| Fireworks (20B) | **Yes** (+ grammar-based) | Valid JSON | Valid JSON | Likely valid | **Medium** | Grammar-based enforcement helps. Reasoning model — may be slower. 20B quality between 8B and 70B. |
| Novita (8B) | **Yes** (basic) | Likely valid | **May break** | **May break** | **Unreliable** | 8B model with json_object enforcement — helps but not guaranteed. vLLM backend may support guided generation. |

**Expected tag assignment after this block:**
- `json` tag: Groq, Cloudflare, GitHub Models, Fireworks (≥2/3 valid)
- Not `json`: Cerebras, HuggingFace, Novita (8B models unreliable), OpenRouter R1 (reasoning interference)

## Block 6: Russian Language Quality (~6 min)

**Goal:** Assess Russian language output quality per provider.

| Test ID | Prompt | Chars |
|---------|--------|-------|
| ru_short | "Что такое Python? 2 предложения." | ~40 |
| ru_medium | Detailed Russian prompt about AI history | ~1000 |

**Additional metrics:**

```
language_of_response: ru | en | mixed
grammar_quality: good | fair | poor (subjective)
answered_in_russian: bool
```

### Expected Results — Block 6

| Provider | Model | ru_short | ru_medium | Language | Grammar | Notes |
|----------|-------|----------|-----------|----------|---------|-------|
| Groq | llama-3.3-70b | Russian, 2 sentences | Russian, detailed | **ru** | **Good** | 70B handles Russian well. Occasional calques from English, but grammatically correct. May insert English technical terms. |
| Cerebras | llama-3.1-8b | **May respond in English** | **Likely English or mixed** | **en/mixed** | **Poor** | 8B models have very weak Russian. Often switch to English mid-response. Wrong cases, gender, number. |
| HuggingFace | Llama-3-8B | **May respond in English** | **Likely English** | **en/mixed** | **Poor** | Same 8B-class issues. Worst Russian in the list — Llama 3.0 8B even weaker than 3.1. |
| Cloudflare | llama-3.3-70b | Russian, 2 sentences | Russian, detailed | **ru** | **Good** | Same model as Groq. Good Russian. (If Cloudflare still has neuron quota left.) |
| OpenRouter | deepseek-r1 | Russian, 2 sentences | Russian, detailed | **ru** (think may be en/zh) | **Excellent** | Best Russian among open-source. Trained on multilingual data including Chinese — strong non-English support. `reasoning_content` may be in English/Chinese. |
| GitHub | gpt-4o-mini | Russian, 2 sentences | Russian, detailed | **ru** | **Excellent** | Best overall Russian. Never switches to English unprompted. Understands cultural context. |
| Fireworks | gpt-oss-20b | Russian, brief | Russian, with errors | **ru/mixed** | **Fair** | 20B reasoning model. Better than 8B but worse than 70B. Reasoning part likely in English. |
| Novita | llama-3.1-8b | **May respond in English** | **Likely English or mixed** | **en/mixed** | **Poor** | Same 8B limitations as Cerebras. |

**Expected tag assignment after this block:**
- `russian` tag: GitHub Models (gpt-4o-mini), OpenRouter (deepseek-r1), Groq (llama-3.3-70b), Cloudflare (llama-3.3-70b)
- Not `russian`: Cerebras, HuggingFace, Novita (all 8B — poor Russian), Fireworks (fair but not good)

## Block 7: Rate Limit Stress Test (~5 min)

**Goal:** Determine how many rapid requests each provider handles before 429, and the retry_after duration.

**DESTRUCTIVE BLOCK — runs last intentionally.** This block exhausts rate limits and may disable providers for 30+ minutes. All quality/functional tests (Blocks 1–6) must be completed before running this.

**Exclude GitHub Models (150 RPD limit)** — stress test would burn the entire daily quota. GitHub Models rate limits are documented; empirical stress test not worth the cost.

**Method per provider (except GitHub Models):**

1. Send rapid requests (no pause) with short prompt "Hi"
2. Count until first non-200 response
3. Record: error code, retry_after header/body, error message
4. Record timestamp of 429 for recovery tracking
5. After all providers hit 429: wait 5 min, then re-test each to measure actual recovery time

**Record for each:**

```
requests_until_429: int
error_code: 429 | 400 | 500 | timeout
retry_after_seconds: int
rate_limit_type: RPM | TPM | RPD | unknown
recovery_time_observed: seconds (measured in step 5)
```

### Expected Results — Block 7

| Provider | RPM limit | Expected requests until 429 | HTTP code | retry_after header | Expected cooldown | Rate limit type | Notes |
|----------|----------|---------------------------|-----------|-------------------|------------------|----------------|-------|
| Groq | 30 RPM | **~30** | 429 | **Yes** | ~60s (minute window), but can be **30 min** if TPD hit | RPM + TPM + TPD | 1,000 RPD / 100K TPD total. retry_after documented. Most predictable. |
| Cerebras | 30 RPM | **~30** | 429 | Not documented | ~60s (minute window) | RPM + TPM + TPD | 14,400 RPD — most generous daily quota. 1M TPD. |
| HuggingFace | ~30 RPM | **~30** | 429 | **Yes** (RateLimit IETF headers) | 5-minute fixed windows | RPM (compute-based) | SDK auto-handles retry. Monthly credit cap ($0.10 free). |
| Cloudflare | 300 RPM | **~3-5** (neuron limit, NOT RPM) | 429 or 500 | Not documented | Until 00:00 UTC next day | **Neuron/day** | 10K neurons/day. 70B model costs ~200K neurons/M output tokens. Will hit neuron limit in 1-3 requests, NOT RPM limit. |
| OpenRouter | 20 RPM | **~20** | 429 (RPM) or 402 (credits) | Not documented | Minute window for RPM; daily for RPD | RPM + **RPD (50 total!)** | 50 RPD across ALL free models — extremely tight. May hit daily limit mid-test. |
| Fireworks | 10 RPM | **~10** | 429 (probable) | Not documented | Dynamic ("spike arrest") | RPM (dynamic ceiling) | $1 starter credits (pay-as-you-go). Lowest RPM. Dynamic rate limiting — may allow burst then throttle. |
| Novita | Unknown RPM | **Unknown** | 429 | Not documented | Unknown | Unknown | $0.50 starter credits. Rates not publicly documented — this test will discover them. |
| ~~GitHub~~ | ~~15 RPM~~ | ~~**Excluded**~~ | ~~429~~ | — | — | ~~RPM + RPD (150)~~ | **Excluded from stress test.** 150 RPD too precious. Known limits: 15 RPM, 150 RPD, 5 concurrent. |

**Key predictions:**
- Cloudflare will fail fastest (neuron limit, not RPM) — expect 1-3 requests before exhaustion
- OpenRouter's 50 RPD may already be partially consumed by Blocks 1-6 (~12-15 requests)
- Fireworks has lowest RPM (10) — will hit limit quickly
- Groq is the only provider confirmed to return `retry_after` header
- Recovery after 5 min: Groq/Cerebras/HuggingFace likely recovered (minute-window RPM). Cloudflare NOT recovered (daily reset). OpenRouter NOT recovered if RPD hit.

## Output Artifacts

### 1. Raw Data

- `/tmp/benchmark_raw/block{N}_{provider}_{test_id}.json` — full API response per request
- `docs/research/2026-04-08-model-tags-benchmark-raw.csv` — all requests in CSV

### 2. Analysis

- `docs/research/2026-04-08-model-tags-benchmark-results.md` — summary tables + conclusions

### 3. Tag Assignment

Final tag assignment table based on test results:

| Tag | Criteria to assign |
|-----|-------------------|
| `fast` | avg response_time < 3s on user_200 + user_1000 (SELF only) |
| `json` | SUPPORTS_RESPONSE_FORMAT=True AND json_valid=True on >=2/3 json tests |
| `code` | model >=70B OR specialized for code (DeepSeek, gpt-oss) |
| `reasoning` | returns reasoning/reasoning_content field with CoT |
| `russian` | answered_in_russian=True AND grammar_quality >= good on both ru tests |
| `vision` | model supports image input (documented) |
| `tools` | provider API supports `tools` parameter (documented) |
| `lightweight` | model <= 8B parameters |
| `gdpr` | provider hosted in EU with GDPR guarantees |

### Expected Tag Assignment (pre-test hypothesis)

| Provider | Model | fast | json | code | reasoning | russian | lightweight | Expected tags |
|----------|-------|:----:|:----:|:----:|:---------:|:-------:|:-----------:|---------------|
| Groq | llama-3.3-70b | **Y** | **Y** | **Y** | - | **Y** | - | fast, json, code, russian |
| Cerebras | llama-3.1-8b | **Y** | - | - | - | - | **Y** | fast, lightweight |
| HuggingFace | Llama-3-8B | - | - | - | - | - | **Y** | lightweight |
| Cloudflare | llama-3.3-70b | - | **Y** | **Y** | - | **Y** | - | json, code, russian |
| OpenRouter | deepseek-r1 | - | - | **Y** | **Y** | **Y** | - | code, reasoning, russian |
| GitHub | gpt-4o-mini | - | **Y** | - | - | **Y** | - | json, russian |
| Fireworks | gpt-oss-20b | - | **Y** | **Y** | **Y** | - | - | json, code, reasoning |
| Novita | llama-3.1-8b | - | - | - | - | - | **Y** | lightweight |

## Execution Timeline

```
T+0:00  Block 0 — make down && make up, warmup
T+0:02  Block 1 — Raw response fields (12 requests)
T+0:04  Block 2 — max_tokens validation (24 requests)
T+0:07  Block 3 — System prompt length (32 requests)
T+0:19  Block 4 — User prompt length (40 requests)
T+0:34  Block 5 — JSON format (24 requests)
T+0:42  Block 6 — Russian language (16 requests)
T+0:48  Block 7 — Rate limit stress test (DESTRUCTIVE, ~50 requests)
T+0:53  PAUSE — 5 min rate limit recovery
T+0:58  Block 7 step 5 — Recovery measurement
T+1:00  Analysis + tag assignment

Total: ~1 hour, ~200 requests
```

## Success Criteria

1. Each alive provider tested at least once per block (no untested gaps)
2. SELF vs FB clearly distinguished for every request
3. max_tokens confirmed or corrected for each provider
4. Rate limit thresholds documented
5. Response field differences documented
6. Final tag assignment backed by empirical data
