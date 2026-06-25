# ADR-0003: Reliability Rating Formula v2 (capability-gated, smoothed, multiplicative)

- **Status:** Proposed
- **Date:** 2026-06-25
- **Deciders:** bgs2509
- **Related issues:** `free-ai-selector-ex9` (Fireworks → all_models_failed without fallback), `free-ai-selector-bmm` (implementation)
- **Supersedes:** ADR-0001 (`reliability_score = success_rate·0.6 + speed_score·0.4`); also replaces the `effective_reliability_score` explore-first scheme built on top of it

---

## Context

Free AI Selector routes each prompt to the "best" free model. Selection happens in
`services/free-ai-selector-business-api/app/application/use_cases/process_prompt.py`
(`execute`, step 3, sort by `effective_reliability_score`). The score is computed in the
Data API and exposed per model via `/api/v1/models?include_recent=true`.

### Observed failure (live VPS data, 2026-06-23 → 2026-06-25)

1. **17.3% of requests failed over 2 days** (686 / 3974); the rate spiked to **~48% on
   2026-06-25** because the previously-reliable `GPT-4o Mini (GitHub)` hit a permanent error
   and went on a 24h cooldown (`AUTH_ERROR_COOLDOWN = 86400`), dumping traffic onto Fireworks.
2. **~89% of all errors are Fireworks** (`412 Precondition Failed` + empty `Fireworks error:`),
   yet Fireworks keeps being selected.

### Root causes in the current scoring

1. **"No data" is treated as "perfect".** Models with no recent-window data get
   `effective_reliability_score = 1.0` (`decision_reason = "no_data_explore"`). Live example:
   - `SambaNova` — lifetime success rate **0.7%** (17 ok / 2405 fail) → `effective = 1.0`
   - `DeepSeek Chat` — **0%** → `effective = 1.0`
   - `OpenRouter R1` — healthy **98.1%** → `effective = 1.0` (same as the broken ones!)
   The explore bonus is an unbounded, permanent `1.0`, so broken-but-idle providers float to
   the top and are tried first, wasting attempts; circuit-breaker-skipped providers never
   accumulate recent data, so they stay pinned at `1.0` forever.
2. **Lifetime reliability is ignored for ranking.** Selection uses the recent-window
   `effective_reliability_score`, not the lifetime `success_rate`. Genuinely excellent models
   (`Ollama Gemma4` 99.8%, `OpenRouter R1` 98.1%) do not reliably win.
3. **Additive speed can rescue a broken model.** `key = (effective_score, -average_response_time)`
   means a fast-but-failing provider (e.g. `Groq` 0.5s, `SambaNova` 0.39s) sorts high on the
   speed tiebreaker despite near-zero quality.
4. **Capabilities are entangled with availability, not modelled as gates.** Tag filtering
   (`_filter_by_tags`) and JSON filtering (`_filter_json_capable_models`) exist but fall back
   to "all models" and are not a first-class, ordered gating layer.

---

## Decision

Replace the single blended score with an explicit **3-layer pipeline**: two hard gates
(capability, health) followed by one continuous score. Capabilities and health are **gates
(×{0,1})**, never additive terms. Quality and speed are **scores**.

```
final_score(model, request) =
    capability_gate(model, request)         # {0,1} — can it do the task at all?
  · health_gate(model)                      # {0,1} — cooldown / circuit breaker
  · ( base_score(model) + explore_bonus(model) )

base_score   = quality · (0.5 + 0.5 · speed)      # multiplicative: quality is necessary
quality      = laplace_smoothed, time-decayed success rate over a window
speed        = clamp(1 − (latency − FAST_FLOOR)/(SLOW_CEIL − FAST_FLOOR), 0, 1)
explore_bonus= C · sqrt( ln(total_requests) / (recent_n + 1) )   # bounded, decaying (UCB)
```

### 1. Quality with Laplace smoothing — kills "1.0 from no data"

```
quality = (succ_hard + 1) / (succ_hard + fail_hard + 2)
```

- A model with **0 data → 0.5** ("unknown / neutral"), NOT 1.0.
- `fail_hard` counts **hard** failures only (500, 412, empty response). **429 rate-limits are
  excluded** from `fail_hard` (they already do not reduce reliability — keep that).
- Computed over a **rolling window with exponential time-decay** (recent calls weigh more):
  weight of a sample = `0.5 ^ (age_hours / HALF_LIFE_HOURS)`.

### 2. Speed normalized to 0..1

```
speed = clamp(1 − (latency_median − FAST_FLOOR) / (SLOW_CEIL − FAST_FLOOR), 0, 1)
```
Use the **median** latency over the window (mean is skewed by outliers). Suggested defaults:
`FAST_FLOOR = 0.5s`, `SLOW_CEIL = 20s`.

### 3. Multiplicative combine — speed cannot rescue a broken model

```
base_score = quality · (0.5 + 0.5 · speed)
```
If `quality ≈ 0`, `base_score ≈ 0` regardless of speed.

### 4. Bounded, decaying exploration (UCB) — replaces fixed 1.0

```
explore_bonus = C · sqrt( ln(total_requests_all_models) / (recent_n_this_model + 1) )
```
New models get a *bounded* benefit of the doubt that **shrinks** as they accumulate data, so
they are tried a few times then judged on merit. Suggested `C ≈ 0.2`.

### 5. Capability gate (first layer) — tags as hard filters

`capability_gate = 1` iff the model's `TAGS` ⊇ the request's required tags AND
`SUPPORTS_RESPONSE_FORMAT` is true when `response_format` is requested; else `0`.
Unlike today, **no silent fallback-to-all**: if zero models match a hard requirement, the
request fails fast with a clear "no capable model" error rather than routing to an incapable one.
(Soft preferences MAY still degrade gracefully; hard requirements MUST NOT.)

Capability is binary "can / cannot", not a quality measure. Known tags in the codebase:
`json, russian, code, reasoning, tools, fast, lightweight, local`. Gap to fix alongside:
`SambaNova / DeepSeek / Hyperbolic` currently declare **no** `TAGS` (inherit empty set).

### 6. Health gate (second layer)

`health_gate = 0` if `available_at > now()` (cooldown) OR circuit breaker is OPEN; else `1`.
Unchanged in spirit from today — just formally separated from the score.

---

## Worked example (live numbers, quality·speed only, weights as above)

```
quality (Laplace)          speed (FAST_FLOOR .5s, SLOW_CEIL 20s)     base = q·(0.5+0.5·s)
Ollama Gemma4 : 0.998       7.6s → 0.64                              0.998·0.82 = 0.818
OpenRouter R1 : 0.981       12.1s → 0.41                             0.981·0.71 = 0.696
Fireworks     : 0.745*      9.9s → 0.52                              0.745·0.76 = 0.566
Groq          : 0.185       0.5s → 1.00                              0.185·1.00 = 0.185
SambaNova     : 0.007       0.39s → 1.00                             0.007·1.00 = 0.007
(* Fireworks uses recent-window SR 74.6%)
```

Resulting order: **Ollama > OpenRouter > Fireworks > Groq > SambaNova** — the healthy models
surface, Fireworks lands mid-pack, the broken `SambaNova` sinks to the bottom. Compare to today:
`SambaNova` and `OpenRouter` both score `1.0`, and the failing Fireworks becomes the de-facto
workhorse.

---

## Alternatives considered

1. **Keep additive `0.6·SR + 0.4·speed`, just fix the explore bonus.** Rejected: additive speed
   still rescues broken-but-fast providers (Groq/SambaNova); the multiplicative form is the real
   fix.
2. **Pure greedy (always pick highest lifetime SR), no exploration.** Rejected: new/recovered
   models never get traffic; can't detect a provider coming back online.
3. **ε-greedy (random exploration X% of the time).** Rejected: wastes a fixed fraction of real
   user traffic on known-bad models; UCB targets exploration where uncertainty is highest.
4. **Thompson sampling (Beta posterior per model).** Strong option and a natural extension of the
   Laplace prior, but higher implementation/observability cost. Deferred as a possible v3; v2's
   smoothed-mean + UCB is simpler to reason about and to log.

---

## Consequences

**Positive**
- Broken-but-idle providers can no longer rank #1; "no data" = 0.5, not 1.0.
- Lifetime/recent quality, not speed, drives selection; speed only breaks near-ties.
- Hard capability requirements (e.g. `json`, `russian`) are honoured or fail fast.
- Exploration is bounded and decays — recovered providers get retried without flooding.

**Negative / cost**
- Requires changing the score computation in the Data API (`effective_reliability_score`,
  `decision_reason`) and the sort key in `process_prompt.py`.
- New tunables (`HALF_LIFE_HOURS`, `FAST_FLOOR`, `SLOW_CEIL`, `C`, smoothing α/β) need sane
  defaults + env overrides + tests.
- Must split failures into hard vs soft (429) at the point stats are recorded.
- Data backfill/migration: `decision_reason` values change; dashboards referencing
  `no_data_explore` must be updated.

**Follow-ups (separate issues)**
- Fill missing `TAGS` for `SambaNova / DeepSeek / Hyperbolic`.
- Measure capabilities instead of declaring them (e.g. track JSON-validity success rate so
  "supports json" becomes a measured fact) — links capability (layer 1) back to quality (score).
- Resolve `free-ai-selector-ex9`: surface the real Fireworks error and ensure fallback actually
  has healthy candidates to fall to.
