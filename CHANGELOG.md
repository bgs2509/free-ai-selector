# Changelog

**Примечание:** В этом документе встречаются устаревшие команды `/aidd-idea`, `/aidd-generate`, `/aidd-finalize`, `/aidd-feature-plan`. Актуальные команды: `/aidd-analyze`, `/aidd-code`, `/aidd-validate`, `/aidd-plan-feature`.


All notable changes to Free AI Selector will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned for v4.0 (April 2026)
- **BREAKING**: Remove old command names (`/aidd-idea`, `/aidd-generate`, `/aidd-finalize`)
- **BREAKING**: Remove old role files (`architect.md`, `implementer.md`)
- **BREAKING**: Only v3 naming conventions supported
- Require migration to v3 before upgrade

---

## [3.1.0] - 2026-04-08

### 🐛 Fixed — Empty AI Responses from Reasoning Models (4 fixes)

Комплексное исправление проблемы пустых ответов от AI-провайдеров. Корневая причина: модель `gpt-oss-20b` (Fireworks) — reasoning модель, которая при `max_tokens=512` тратила все токены на `reasoning_content`, оставляя `content` пустым в ~75% запросов. Пустые ответы ошибочно считались "success", не понижая reliability score.

- **F1: max_tokens 512 → 2048** в `base.py` и `cloudflare.py` — reasoning модели получают достаточно токенов для content после chain-of-thought (340b831)
- **F2: Парсинг reasoning_content** в `base.py._parse_response()` — если `content` пуст, используется `reasoning_content` как fallback (340b831)
- **F3: Пустой ответ = ProviderError** в `process_prompt.py` — пустой `response_text` бросает `ProviderError`, что триггерит fallback на следующего провайдера и понижает reliability score. Логика зеркалит `test_all_providers.py` (340b831)
- **F4: Health Worker URL fix** — `/providers/test` → `/api/v1/providers/test` в health-worker. Эндпоинт возвращал 404 из-за отсутствия prefix `/api/v1`, синтетический мониторинг не работал (340b831)

### 📄 Documentation — Ollama Integration Plan

- План интеграции Ollama для локального LLM inference на RTX 4060 (9e10389)
- Provider benchmark: 12 провайдеров × 3 промпта × 2 формата (e186791)

---

## [3.0.0] - 2026-03-20

### ✨ Added — TASK-001: Унификация Docker-сетей — host network + порты 802x

#### Added
- `network_mode: host` для Business API, Telegram Bot, Health Worker в `docker-compose.yml`
- Uvicorn command/healthcheck override для Business API (порт 8020)
- Проброс порта Data API `8021:8001` на хост

#### Changed
- Business API порт: 8000 → 8020 (Dockerfile, docker-compose.yml)
- Data API хост-порт: 8001 → 8021 (внутренний порт 8001 без изменений)
- Makefile: убрана MODE=local/vps логика, единый `COMPOSE := docker compose`
- Locust: `--network host` вместо `--network free-ai-selector-network`
- Вся документация обновлена под новые порты

#### Removed
- `docker-compose.override.yml` — конфигурация перенесена в `docker-compose.yml`
- `docker-compose.vps.yml` — больше не нужен (proxy-network не используется при host mode)
- `make local` / `make vps` — заменены на единый `make up`

### 🔄 Changed — Retry & Circuit Breaker Tuning

- Отключены retry для упрощения fallback loop (04d383a)
- Ускорен lockout circuit breaker (04d383a)
- Health checks делегированы в Business API вместо прямых вызовов провайдеров (0e43f78)

### 🧪 Testing — 80% Coverage Milestone

- 456/456 тестов проходят (a3aa478)
- 80% покрытие для всех 4 микросервисов с реальным PostgreSQL (cca5cc5)

---

## [2.9.1] - 2026-03-04

### 🔄 Changed — Docker Compose Profiles for Telegram Bot

Telegram Bot больше не запускается по умолчанию — требуется явное включение через Docker Compose profile `bot`. Решает проблему конфликта polling при использовании одного токена на нескольких VPS.

- **Docker Compose profiles**: добавлен `profiles: ["bot"]` к сервису `free-ai-selector-telegram-bot` — `docker compose up` больше не запускает бота (c87b264)
- **Makefile WITH_BOT**: переменная `COMPOSE_PROFILES` с поддержкой `WITH_BOT=1` для включения profile bot (c87b264)
- **Новые targets**: `make local-bot` и `make vps-bot` — запуск с ботом; `make local` и `make vps` — без бота (c87b264)
- **Условный тест-раннер**: `run_container_tests.py` динамически определяет наличие контейнера бота через `docker inspect`, пропускает ожидание если бот не запущен (c87b264)

### 🐛 Fixed — Docker Warnings

- Добавлен дефолт `${TELEGRAM_BOT_TOKEN:-}` в `docker-compose.yml` — устранён WARN о неустановленной переменной при запуске без бота (e6666cc)
- Исправлен `FROM ... as base` → `FROM ... AS base` в Dockerfile data-api и business-api — устранён `FromAsCasing` warning (e6666cc)

---

## [2.9.0] - 2026-03-04

### ✨ Added — JSON response_format Support

Маршрутизация, валидация и retry для JSON-ответов от AI-провайдеров.

- Включён `SUPPORTS_RESPONSE_FORMAT=True` для 7 провайдеров: Groq, Cerebras, DeepSeek, OpenRouter, Fireworks, Novita, Scaleway (cb6d5d8)
- `ProviderRegistry.supports_response_format()` — проверка capability без инстанцирования провайдера (cb6d5d8)
- Pydantic `field_validator` ограничивает `response_format` значением `{"type": "json_object"}` (cb6d5d8)
- `_filter_json_capable_models()` в `ProcessPromptUseCase` — маршрутизация JSON-запросов только на capable провайдеров с fallback на system_prompt (cb6d5d8)
- `json_validator.py` — утилита для извлечения валидного JSON из ответов провайдеров (обработка markdown-обёрток, embedded JSON) (cb6d5d8)
- Интеграция JSON-валидации в fallback loop с retry при невалидном JSON (cb6d5d8)

### ✨ Added — Decay-Weighted Scoring Algorithm (Fix C+D2)

Замена бинарного переключения recent/long-term на плавный decay-weighted алгоритм. Long-term score больше не используется для выбора модели — только актуальные данные из `prompt_history`.

- **Fix C+D2**: `get_recent_weighted_stats_for_all_models()` с SQL decay-формулой: `weight = POW(0.98, hours_ago)` — свежие данные доминируют (1ч=98%, 1д=61%, 3д=23%, 7д=3%) (7ad97eb)
- Удалён long-term fallback и бинарный `MIN_REQUESTS_FOR_RECENT` переключатель: модели без данных получают `score=1.0` (explore new models first) (7ad97eb)
- Упрощён `_calculate_recent_metrics`: единый `decision_reason="decay_weighted_score"` вместо `"recent_score"`/`"fallback"` (7ad97eb)
- Обновлены тесты F015 под новый формат данных: `weighted_success_rate`/`weighted_avg_response_time` вместо `success_count`/`avg_response_time` (a31f200)
- Без миграций БД

### ✨ Added — F026: Unified JSON Logging

Единый формат JSON-логов во всех 4 сервисах.

- Stdlib logging interception через `ProcessorFormatter` во всех `logger.py` (828a772)
- Замена `logging.getLogger` на structlog `get_logger` в business-api (5 файлов) и data-api (2 файла) (828a772)
- Конвертация f-string сообщений в structured events (snake_case + kwargs) (828a772)
- `--no-access-log` в uvicorn CMD для business-api и data-api Dockerfiles (828a772)
- Маппинг `LOG_LEVEL` env var в `docker-compose.yml` (828a772)
- Подавление noisy stdlib логгеров (httpx, httpcore, asyncio, urllib3) (828a772)
- PRD, research, plan, completion report (68b3fa9, 330bef0, a60ccee, ef5c8b1)

### 🐛 Fixed — Scoring & Reliability (5 исправлений)

Комплексное исправление системы скоринга и надёжности.

- **Fix A1**: `or` → `is not None` для `effective_reliability_score` — предотвращение маскировки легитимных `0.0` значений (4376f79)
- **Fix A2**: Multi-key sort (effective_score DESC, avg_response_time ASC) — при равных scores побеждает более быстрая модель (4376f79)
- **Fix A3**: Реальные метрики из Data API в stats endpoint вместо сломанной инверсной формулы `reliability_score / 0.6`, показывавшей >100% (4376f79)
- **Fix B**: Health Worker записывает результаты в `prompt_history` — recent_score отражает synthetic monitoring. Лимит cleanup увеличен 1000→5000 (4376f79)
- **Fix E**: Quality gate `MINIMUM_RELIABILITY_THRESHOLD=0.3` — отклонение моделей ниже 30% reliability, HTTP 503 когда все ниже порога (4376f79)

### 🐛 Fixed

- Root redirect за nginx reverse proxy: относительный путь `static/index.html` вместо абсолютного `/static/index.html` (5bb31e7)
- Stale default `model_id` для провайдеров с 404 (Cerebras, Fireworks, Novita, OpenRouter) (67c5c19)
- Фильтрация provider tests по зарегистрированным активным провайдерам (2cdb062)
- Тест `test_fallback_preserves_system_prompt_and_response_format` для JSON-валидации (0a34c24)

### 🔥 Removed — Provider Cleanup

- **Kluster** — провайдер удалён из runtime, seed, тестов, конфигурации (0a4aa71)
- **Nebius** — провайдер удалён из runtime, seed, тестов, конфигурации, всех AIDD-артефактов (7e6f843)
- Количество провайдеров: 12 → 10

### 🔄 Changed

- Business API переведён на `network_mode: host` для VPN routing в локальной разработке (1716000)
- Merge backup patterns (`.merge_backups/`) добавлены в `.gitignore` (cd1ac89)

### 📄 Documentation

- Диагностика nginx 404 при относительном redirect за reverse proxy (5b21bb2)
- Audit-логи load test runs от 2026-02-26 и 2026-03-04 (6159dbf, cc59035)

---

## [2.8.0] - 2026-02-25

### ✨ Added — Error Resilience Pipeline (F022–F025)

Масштабное улучшение отказоустойчивости при работе с AI-провайдерами.
Реализованы 4 связанные фичи в рамках единого плана из 8 стадий.

#### F022: Error Classifier Fix
- Исправлена потеря HTTP-кода при оборачивании `HTTPStatusError` в `ProviderError` (c50b662)
- Добавлена классификация кодов 402, 404 в error classifier (c50b662)
- Защита от слишком больших payload (> 6000 символов) (c50b662)
- 36/36 тестов (b92366e)

#### F023: Error Resilience, Exponential Backoff & Telemetry
- Cooldown для провайдеров с постоянными ошибками (e55b8ed)
- Exponential backoff вместо фиксированных retry-интервалов (e55b8ed)
- Per-request telemetry: поля `attempts` и `fallback_used` в `ProcessPromptResponse` (e55b8ed)

#### F024: Circuit Breaker
- Паттерн Circuit Breaker (CLOSED → OPEN → HALF-OPEN) для AI-провайдеров (03a17e2)
- Автоматическое отключение нестабильных провайдеров с постепенным восстановлением (03a17e2)

#### F025: Server-Side Backpressure
- HTTP 429 с `ErrorResponse` и заголовком `Retry-After` при rate limit всех провайдеров (399801f)
- HTTP 503 с `ErrorResponse` и заголовком `Retry-After` при недоступности сервиса (399801f)
- Structured `ErrorResponse` schema: `error`, `message`, `retry_after`, `attempts`, `providers_tried`, `providers_available` (591b293)
- Кастомный обработчик slowapi rate limit в формате `ErrorResponse` (399801f)
- Domain exceptions: `AllProvidersRateLimited`, `ServiceUnavailable` (399801f)

### 📄 Documentation
- Комплексный отчёт об анализе ошибок LLM API (45c45bb)
- 8-стадийный план исправления ошибок (179e879)
- PRD, research, plan и completion reports для F022–F025
- Полностью обновлена API документация: `docs/api/data-api.md`, `business-api.md`, `errors.md`, `examples.md`
- Обновлён CHANGELOG с отсутствующими изменениями

### 🧪 Testing Infrastructure
- Locust template для нагрузочного тестирования (8ee64d1)
- Структура для load test reports (8ee64d1)
- План нагрузочного тестирования (`docs/api-tests/load-testing-plan.md`)

---

## [2.7.0] - 2026-02-16

### 🔄 Changed - Docker Compose Restructure

- **Docker Compose base + override pattern** — разделение на `docker-compose.yml` (base) + `docker-compose.override.yml` (local dev) для чистого управления окружениями (011f114)

---

## [2.6.0] - 2026-02-13

### ✨ Added - Features F020, F021 + Incident Documentation

#### F020: Web Model Selector
- Веб-интерфейс для выбора AI-модели (5f91821)
- PRD, research, план реализации (8118132)

#### F021: Independent Compose Modes
- Разделение Docker Compose на nginx (VPS) и local (dev) режимы (e3adfdb)
- Research, план, полный AIDD pipeline (c38509c, 192ee06)
- Удалён устаревший deploy-скрипт (dd55188)

#### Docker/VPN Incident
- Подробный postmortem конфликта Docker DNS и VPN strict-route (f3876e0)
- Документация workaround для Hiddify strict-route (318ff55)
- Внешние ссылки на известные проблемы VPN + Docker (45f4164)
- Обновление инцидента с runtime collision и финальным фиксом (6edd3c9)

### 🐛 Fixed
- Улучшена обработка сетевых ошибок в polling бота и логах worker (0fd5521)

---

## [2.5.0] - 2026-02-11

### ✨ Added - Features F018, F019

#### F018: Remove env_var from DB (SSOT via ProviderRegistry)
- Удалён `env_var` из БД, `ProviderRegistry` стал единственным источником правды для API key env vars (570d109)
- Полный AIDD pipeline: PRD → research → plan → implementation → completion report (ceaca89, 44e1a7d, 0d64cc9, 018622e)

#### F019: model_id Priority with Fallback
- Реализован приоритетный выбор модели по `model_id` с fallback на reliability score (b78443e)
- PRD, pipeline metadata, completion report (d34926b, 78a40dd, 6041353)

---

## [2.4.2] - 2026-02-04

### 🔄 Changed
- Обновлён AIDD framework submodule до последней версии (cfacdb0)
- Добавлены research и план реализации для F017 SQL optimization (a37f001)

---

## [2.4.1] - 2026-01-28 — 2026-01-30

### ✨ Added - Features F012–F017

#### F012: Rate Limit Handling
- Обработка rate limit ответов от AI-провайдеров с retry логикой (c8ac9e4)

#### F013: OpenAI-Compatible Provider Base Class
- Консолидация AI-провайдеров через `OpenAICompatibleProvider` — единый базовый класс (6238653)

#### F014: Error Handling Consolidation
- Консолидация обработки ошибок в `ProcessPromptUseCase` (ef29541)

#### F015: Data API DRY Refactoring
- DRY-рефакторинг Data API — устранение дублирования кода (5c3daf9)

#### F016: ReliabilityService as SSOT
- `ReliabilityService` стал единственным источником правды для расчёта reliability score (dc16457)

#### F017: SQL Aggregation Optimization
- Оптимизация `get_statistics_for_period` — замена Python-агрегации на SQL (53b3571)

#### Auto-cleanup
- Автоматическая очистка `prompt_history` — хранение только 1000 последних записей (bccd06e)

### 🔄 Changed - AIDD v4.0 Migration
- Миграция на AIDD v4.0 naming v3: `prd/` → `_analysis/`, `architecture/` → `_plans/mvp/`, `reports/` → `_validation/` (14914c6)
- Синхронизация AIDD framework до v2.4 с Migration Mode (84bee05)
- Выравнивание путей артефактов в `.pipeline-state.json` (615d225)

### 📄 Documentation
- Расширены примеры REST API в README: `system_prompt`, `response_format` (c401056)
- Completion reports для F012–F017 (990b5d6, 75af7fe, c47502d, 71664b1, 3117ec0, 308fbbf)

---

## [2.4.0] - 2026-01-19

### ✨ Added - Migration Mode

**Phase 2 Complete**: Full migration mode support for naming conventions

#### New Commands (aliases, fully functional)
- `/aidd-analyze` - alias for `/aidd-idea` (PRD creation)
- `/aidd-code` - alias for `/aidd-generate` (code generation)
- `/aidd-validate` - alias for `/aidd-finalize` (quality & deploy)
- `/aidd-plan-feature` - alias for `/aidd-feature-plan` (feature planning)

#### New Agent Roles (aliases, fully functional)
- `planner.md` - alias for `architect.md`
- `coder.md` - alias for `implementer.md`

#### Artifact Structure Versioning
- `naming_version` field in `.pipeline-state.json` controls artifact paths
- **v2 (default)**: Old structure - `prd/`, `architecture/`, `plans/`, `reports/`
- **v3 (opt-in)**: New structure - `_analysis/`, `_plans/`, `_validation/`

#### Migration Tools
- `scripts/migrate-naming-v3.py` - automated migration from v2 to v3
  - Renames artifact folders
  - Removes duplication in filenames (`{name}-prd.md` → `{name}.md`)
  - Updates `.pipeline-state.json`
  - Updates references in documents

#### Documentation
- Updated all command files to support `naming_version`
- Added migration guide: `docs/naming-v3-implementation.md`
- Added completion summary: `contributors/2026-01-19-phase2-completion-summary.md`
- Updated roles map: `contributors/2026-01-19-aidd-roles-commands-artifacts-map.md`
- Updated `CLAUDE.md` with migration mode section

### 🔄 Changed

#### Commands
All commands now check `naming_version` and create artifacts accordingly:
- `/aidd-analyze` (ea568ca) - `prd/` → `_analysis/`
- `/aidd-research` (c0ec969) - `research/` → `_research/`
- `/aidd-plan` (f9c810e) - `architecture/` → `_plans/mvp/`
- `/aidd-plan-feature` (6e84bbc) - `plans/` → `_plans/features/`
- `/aidd-validate` (e56630d) - `reports/` → `_validation/`

#### File Naming Convention
- **v2**: Duplication in names - `{date}_{FID}_{slug}-prd.md`, `{slug}-plan.md`
- **v3**: No duplication - `{date}_{FID}_{slug}.md`

### ✅ Backward Compatibility

- **100% backward compatible** - no breaking changes
- All old commands continue to work
- All old role files continue to work
- Existing v2 projects work without modification
- Can use old and new command names interchangeably

### 📊 Metrics

- **5/5 commands** support dual-mode (100%)
- **2/2 roles** have aliases (planner, coder)
- **6 commits** in Phase 2.3
- **~300+ lines** of documentation updated
- **8 files** modified (5 commands + 2 docs + 1 script)

### 🔗 References

- Full plan: `/home/bgs/.claude/plans/idempotent-drifting-wirth.md`
- Implementation guide: `docs/naming-v3-implementation.md`
- Phase 2 summary: `contributors/2026-01-19-phase2-completion-summary.md`

---

## [2.3.0] - 2026-01-14

### Added
- Completion Report (single document instead of 4 separate files)
- Two modes for `/aidd-finalize`: Full (production-ready) and Quick (draft)
- Plan verification procedure in implementer role
- Documentation on validator Quick and Full modes

### Changed
- Consolidated review-report, qa-report, rtm, and documentation into single Completion Report
- Updated workflow to support starting new features without waiting for DEPLOYED gate

### Documentation
- Updated CLAUDE.md and workflow.md for two-mode `/aidd-finalize`
- Added Quick and Full modes description to validator documentation
- Updated pipeline documentation

---

## [2.2.0] - 2025-12-25

### Added
- Pipeline State v2: Support for parallel pipelines
- Git integration: Feature-based branching (feature/{FID}-{slug})
- Features registry: Deployed features tracking
- Gate isolation: `active_pipelines[FID].gates` instead of global `gates`
- Context auto-detection by current git branch

### Changed
- `.pipeline-state.json` structure: Added `active_pipelines` and `features_registry`
- All commands now work with parallel features
- Feature context determined automatically from git branch

### Documentation
- Added `knowledge/pipeline/git-integration.md`
- Added `knowledge/pipeline/state-v2.md`
- Updated workflow documentation for parallel development

---

## [2.1.0] - 2025-12-23

### Added
- HTTP-only architecture enforcement in Data APIs
- Log-driven design documentation
- Security checklist
- Secrets management guidelines

### Changed
- Business APIs must use Data API via HTTP (no direct DB access)
- Enhanced validator role with security checks

---

## [2.0.0] - 2025-12-15

### Added
- 6-stage pipeline with quality gates
- 7 AI agent roles (Analyst, Researcher, Architect, Implementer, Validator, Reviewer, QA)
- Quality Cascade (16 checks across roles)
- DDD/Hexagonal architecture
- HTTP-only data access pattern
- Template system for services
- Knowledge base system

### Changed
- Complete rewrite of generation system
- Maturity level fixed at Level 2 (MVP)
- Unified conventions and documentation

---

## [1.0.0] - 2025-11-01

Initial release with basic MVP generation capabilities.

---

## Legend

- ✨ Added - New features
- 🔄 Changed - Changes in existing functionality
- 🐛 Fixed - Bug fixes
- ⚠️ Deprecated - Soon-to-be removed features
- 🔥 Removed - Removed features
- 🔒 Security - Security fixes
- 📊 Metrics - Performance or quality metrics
- 🔗 References - Links to related documents
- ✅ Backward Compatibility - Compatibility notes
