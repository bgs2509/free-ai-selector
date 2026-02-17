# Changelog

**Примечание:** В этом документе встречаются устаревшие команды `/aidd-idea`, `/aidd-generate`, `/aidd-finalize`, `/aidd-feature-plan`. Актуальные команды: `/aidd-analyze`, `/aidd-code`, `/aidd-validate`, `/aidd-plan-feature`.


All notable changes to AIDD-MVP Generator will be documented in this file.

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
