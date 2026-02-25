# =============================================================================
# Free AI Selector - Makefile
# =============================================================================
# Этот Makefile управляет:
# 1) запуском и обслуживанием docker-кластера проекта;
# 2) запуском тестов/линтинга внутри контейнеров;
# 3) нагрузочным тестированием через Locust в Docker;
# 4) единым контекстом прогона (RUN_ID, source, scenario) для трассировки.
#
# ВАЖНО:
# - По умолчанию используется MODE=local.
# - Для VPS режима передайте MODE=vps.
# - Для нагрузочных прогонов всегда формируется RUN_ID, который прокидывается
#   во все сервисы и в Locust.
# =============================================================================

.PHONY: help local vps build up down restart restart-recreate logs logs-data logs-business logs-bot logs-worker logs-db clean test test-data test-business lint format migrate seed health health-check ensure-up-with-context shell-data shell-business db-shell dev status \
	load-test load-test-ui load-test-ui-up load-test-ui-down load-test-ui-logs load-test-baseline load-test-ramp-up load-test-sustained load-test-failover load-test-recovery load-test-oversize load-test-all cleanup-load-test

# =============================================================================
# Core Mode Configuration
# =============================================================================

# Режим запуска инфраструктуры:
# - local: docker-compose.yml + docker-compose.override.yml
# - vps:   docker-compose.yml + docker-compose.vps.yml
MODE ?= local

ifeq ($(MODE),local)
# Команда Docker Compose для локального режима.
# Override-файл подхватывается автоматически.
COMPOSE := docker compose
else ifeq ($(MODE),vps)
# Команда Docker Compose для VPS режима.
# Override-файл local НЕ подключается.
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.vps.yml
else
$(error Unsupported MODE='$(MODE)'. Use MODE=local or MODE=vps)
endif

# =============================================================================
# Unified Run Context (for traceability/audit)
# =============================================================================

# Уникальный идентификатор прогона.
# Можно передать извне: `make test RUN_ID=my-run-001`.
RUN_ID ?= run-$(shell date -u +%Y%m%dT%H%M%SZ)-$(shell cut -c1-8 /proc/sys/kernel/random/uuid)
RUN_ID := $(RUN_ID)

# Источник запуска (скрипт/команда), используется в аудит-логах.
# По умолчанию содержит первый target в текущем make-вызове.
RUN_SOURCE ?= make:$(or $(firstword $(MAKECMDGOALS)),manual)
RUN_SOURCE := $(RUN_SOURCE)

# Сценарий прогона для трассировки.
# Значение должно отражать тип операции (test/lint/load-test/...).
RUN_SCENARIO ?= general
RUN_SCENARIO := $(RUN_SCENARIO)

# UTC-время старта прогона (ISO-8601).
RUN_STARTED_AT ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
RUN_STARTED_AT := $(RUN_STARTED_AT)

# Включение audit-логирования во всех сервисах и Locust.
# true  -> писать audit.jsonl
# false -> не писать аудит
AUDIT_ENABLED ?= true

# Папка для audit-артефактов (host path).
AUDIT_RESULTS_DIR ?= docs/api-tests/results/audit

# Имя audit-файла для текущего прогона.
# По умолчанию каждый RUN_ID пишет в отдельный файл.
AUDIT_FILE_NAME ?= $(RUN_ID).jsonl
AUDIT_FILE_NAME := $(AUDIT_FILE_NAME)

# JSONL путь на host-машине (артефакт прогона).
AUDIT_JSONL_HOST_PATH ?= $(AUDIT_RESULTS_DIR)/$(AUDIT_FILE_NAME)
AUDIT_JSONL_HOST_PATH := $(AUDIT_JSONL_HOST_PATH)

# JSONL путь внутри контейнеров compose-сервисов.
# Синхронизирован с volume mount `./docs/api-tests/results/audit:/audit`.
AUDIT_JSONL_PATH ?= /audit/$(AUDIT_FILE_NAME)
AUDIT_JSONL_PATH := $(AUDIT_JSONL_PATH)

# Экспортируем run/audit контекст в sub-make и shell-команды.
export RUN_ID
export RUN_SOURCE
export RUN_SCENARIO
export RUN_STARTED_AT
export AUDIT_ENABLED
export AUDIT_JSONL_PATH
export AUDIT_JSONL_HOST_PATH

# =============================================================================
# Load Testing Configuration (Locust in Docker)
# =============================================================================

# Docker image с Locust.
LOCUST_IMAGE ?= locustio/locust:2.43.3

# Путь к locustfile внутри репозитория.
LOCUST_FILE ?= docs/api-tests/locustfile.py

# URL Business API из Docker-сети (внутренний DNS сервиса).
LOCUST_HOST ?= http://free-ai-selector-business-api:8000

# Папка для результатов load-теста (CSV/HTML/JSONL).
LOAD_TEST_RESULTS_DIR ?= docs/api-tests/results

# Логический сценарий нагрузочного теста:
# baseline | ramp_up | sustained | failover
LOAD_TEST_SCENARIO ?= baseline

# Количество виртуальных пользователей (users).
LOAD_TEST_USERS ?= 1

# Скорость запуска пользователей (users/sec).
LOAD_TEST_SPAWN_RATE ?= 1

# Длительность прогона (например: 5m, 10m, 1h).
LOAD_TEST_RUN_TIME ?= 10m

# Префикс файлов результатов (CSV/HTML/JSONL).
LOAD_TEST_PREFIX ?= $(LOAD_TEST_SCENARIO)

# Включить/выключить мониторинговые запросы /health и /models/stats из Locust.
LOAD_TEST_MONITORING ?= true

# Включить oversize payload сценарий (ожидаемые 422).
LOAD_TEST_OVERSIZE ?= false

# Режим с Web UI Locust.
LOAD_TEST_WITH_UI ?= true

# Для UI-режима: автостарт генерации нагрузки (true/false).
LOAD_TEST_AUTOSTART ?= true

# Для UI-режима: авто-выход через N секунд после завершения теста.
LOAD_TEST_AUTOQUIT_SECONDS ?= 10

# Порт Web UI Locust на host.
LOAD_TEST_WEB_PORT ?= 8089

# Имя контейнера для headless-прогонов Locust.
LOCUST_RUN_CONTAINER_NAME ?= free-ai-selector-locust-run-$(RUN_ID)

# Имя контейнера для постоянного UI режима Locust.
LOCUST_UI_CONTAINER_NAME ?= free-ai-selector-locust-ui

# Сценарий трассировки для нагрузочного прогона.
# Можно переопределить извне: RUN_SCENARIO=load-test:custom
LOAD_TEST_RUN_SCENARIO ?= load-test:$(LOAD_TEST_SCENARIO)

# =============================================================================
# Help
# =============================================================================

# Печатает список доступных команд с краткими описаниями.
help:
	@echo "Free AI Selector - Available Commands:"
	@echo ""
	@echo "Runtime mode:"
	@echo "  make local                 - Запуск локального режима (порты 8000/8001)"
	@echo "  make vps                   - Запуск VPS режима (за nginx reverse proxy)"
	@echo "  make up                    - Запуск в текущем MODE (по умолчанию local)"
	@echo "  make <target> MODE=local   - Выполнить target в локальном режиме"
	@echo "  make <target> MODE=vps     - Выполнить target в VPS режиме"
	@echo ""
	@echo "Service management:"
	@echo "  make build                 - Build all Docker images"
	@echo "  make down                  - Stop all services"
	@echo "  make restart               - Fast restart (без пересоздания и без смены RUN контекста)"
	@echo "  make restart-recreate      - Recreate containers (обновляет RUN контекст)"
	@echo "  make logs                  - Tail logs from all services"
	@echo "  make logs-data             - Tail logs from Data API"
	@echo "  make logs-business         - Tail logs from Business API"
	@echo "  make logs-bot              - Tail logs from Telegram Bot"
	@echo "  make logs-worker           - Tail logs from Health Worker"
	@echo "  make logs-db               - Tail logs from PostgreSQL"
	@echo "  make status                - Show service status"
	@echo ""
	@echo "Quality and database:"
	@echo "  make test                  - Run all tests in containers with final report"
	@echo "  make test-data             - Run Data API tests"
	@echo "  make test-business         - Run Business API tests"
	@echo "  make lint                  - Run ruff, mypy, bandit"
	@echo "  make format                - Format code with ruff"
	@echo "  make migrate               - Run database migrations"
	@echo "  make seed                  - Seed database with initial data"
	@echo "  make health                - Check health of all services"
	@echo ""
	@echo "Interactive shells:"
	@echo "  make shell-data            - Open shell in Data API container"
	@echo "  make shell-business        - Open shell in Business API container"
	@echo "  make db-shell              - Open PostgreSQL shell"
	@echo ""
	@echo "Load testing (Locust in Docker):"
	@echo "  make load-test-baseline    - Baseline (1 user, 10m)"
	@echo "  make load-test-ramp-up     - Ramp-up steps: 2/4/6/8/10/12 users"
	@echo "  make load-test-sustained   - Sustained load (8 users, 10m)"
	@echo "  make load-test-failover    - Provider failover scenario (6 users, 10m)"
	@echo "  make load-test-recovery    - Recovery check (1 user, 5m)"
	@echo "  make load-test-oversize    - Oversize payload scenario (422 checks)"
	@echo "  make load-test-ui          - Alias for load-test-ui-up"
	@echo "  make load-test-ui-up       - Start persistent Locust Web UI"
	@echo "  make load-test-ui-logs     - Tail persistent Locust UI logs"
	@echo "  make load-test-ui-down     - Stop Locust UI and docker stack"
	@echo "  make load-test-all         - Run all scenarios sequentially"
	@echo "  make cleanup-load-test     - Remove stale Locust containers"
	@echo ""
	@echo "Run context / audit variables:"
	@echo "  RUN_ID=$(RUN_ID)"
	@echo "  RUN_SOURCE=$(RUN_SOURCE)"
	@echo "  RUN_SCENARIO=$(RUN_SCENARIO)"
	@echo "  RUN_STARTED_AT=$(RUN_STARTED_AT)"
	@echo "  AUDIT_ENABLED=$(AUDIT_ENABLED)"
	@echo "  AUDIT_JSONL_PATH=$(AUDIT_JSONL_PATH)            (container path)"
	@echo "  AUDIT_JSONL_HOST_PATH=$(AUDIT_JSONL_HOST_PATH)  (host path)"

# =============================================================================
# Mode Shortcuts
# =============================================================================

# Явный запуск локального режима.
local:
	@$(MAKE) up MODE=local RUN_SOURCE=make:local RUN_SCENARIO=infra:local

# Явный запуск VPS режима.
vps:
	@$(MAKE) up MODE=vps RUN_SOURCE=make:vps RUN_SCENARIO=infra:vps

# =============================================================================
# Service Lifecycle Commands
# =============================================================================

# Сборка образов всех сервисов.
# RUN_ID намеренно не используется в build-args, чтобы не ломать Docker cache.
build:
	@echo "Building images (MODE=$(MODE))"
	$(COMPOSE) build

# Гарантирует, что сервисы запущены с текущим run/audit контекстом.
# Используется как preflight перед test/lint/migrate/... командами.
ensure-up-with-context:
	@mkdir -p "$(AUDIT_RESULTS_DIR)"
	@echo "Ensuring services are running with current run context (MODE=$(MODE))"
	@echo "Run context: RUN_ID=$(RUN_ID), RUN_SOURCE=$(RUN_SOURCE), RUN_SCENARIO=$(RUN_SCENARIO), RUN_STARTED_AT=$(RUN_STARTED_AT)"
	@echo "Audit paths: container=$(AUDIT_JSONL_PATH), host=$(AUDIT_JSONL_HOST_PATH)"
	@RUN_ID="$(RUN_ID)" \
	RUN_SOURCE="$(RUN_SOURCE)" \
	RUN_SCENARIO="$(RUN_SCENARIO)" \
	RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	AUDIT_JSONL_PATH="$(AUDIT_JSONL_PATH)" \
	$(COMPOSE) up -d
	@$(MAKE) health-check MODE=$(MODE)

# Запуск всех сервисов с пересборкой, затем health-check.
up:
	@mkdir -p "$(AUDIT_RESULTS_DIR)"
	@echo "Starting services (MODE=$(MODE))"
	@echo "Run context: RUN_ID=$(RUN_ID), RUN_SOURCE=$(RUN_SOURCE), RUN_SCENARIO=$(RUN_SCENARIO), RUN_STARTED_AT=$(RUN_STARTED_AT)"
	@echo "Audit paths: container=$(AUDIT_JSONL_PATH), host=$(AUDIT_JSONL_HOST_PATH)"
	@RUN_ID="$(RUN_ID)" \
	RUN_SOURCE="$(RUN_SOURCE)" \
	RUN_SCENARIO="$(RUN_SCENARIO)" \
	RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	AUDIT_JSONL_PATH="$(AUDIT_JSONL_PATH)" \
	$(COMPOSE) up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@$(MAKE) health-check MODE=$(MODE)

# Остановка всех сервисов в текущем MODE.
# Перед остановкой очищает зависшие Locust-контейнеры.
down:
	@$(MAKE) cleanup-load-test >/dev/null
	$(COMPOSE) down

# Быстрый рестарт контейнеров без пересоздания.
# ВАЖНО: RUN контекст при этом не меняется.
restart:
	@echo "Restarting containers without recreation (run context is unchanged)"
	$(COMPOSE) restart

# Рестарт с полным пересозданием контейнеров.
# Используйте эту команду, когда нужно применить новый RUN контекст.
restart-recreate:
	@echo "Recreating containers with current run context"
	@$(MAKE) down MODE=$(MODE)
	@$(MAKE) up MODE=$(MODE) RUN_SOURCE=make:restart-recreate RUN_SCENARIO=infra:restart-recreate

# Логи всех сервисов (follow).
logs:
	$(COMPOSE) logs -f

# Логи Data API.
logs-data:
	$(COMPOSE) logs -f free-ai-selector-data-postgres-api

# Логи Business API.
logs-business:
	$(COMPOSE) logs -f free-ai-selector-business-api

# Логи Telegram Bot.
logs-bot:
	$(COMPOSE) logs -f free-ai-selector-telegram-bot

# Логи Health Worker.
logs-worker:
	$(COMPOSE) logs -f free-ai-selector-health-worker

# Логи PostgreSQL.
logs-db:
	$(COMPOSE) logs -f postgres

# Удаление контейнеров и томов (опасная операция).
clean:
	@echo "WARNING: This will delete all data including the database!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
	    $(MAKE) cleanup-load-test >/dev/null; \
	    $(COMPOSE) down -v; \
	    docker volume rm free-ai-selector-postgres-data 2>/dev/null || true; \
	    echo "All containers and volumes removed."; \
	else \
	    echo "Clean cancelled."; \
	fi

# =============================================================================
# Quality Commands
# =============================================================================

# Запуск полного контейнерного тест-раннера.
# Скрипт поднимет/остановит docker-стек и выведет агрегированный отчет.
test:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:test RUN_SCENARIO=qa:test >/dev/null
	@COMPOSE_CMD='$(COMPOSE)' python3 scripts/run_container_tests.py

# Запуск unit/integration тестов Data API.
test-data:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:test-data RUN_SCENARIO=qa:test-data >/dev/null
	$(COMPOSE) exec free-ai-selector-data-postgres-api pytest tests/ -v --cov=app --cov-report=term-missing

# Запуск unit/integration тестов Business API.
test-business:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:test-business RUN_SCENARIO=qa:test-business >/dev/null
	$(COMPOSE) exec free-ai-selector-business-api pytest tests/ -v --cov=app --cov-report=term-missing

# Запуск линтеров для Data API и Business API.
lint:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:lint RUN_SCENARIO=qa:lint >/dev/null
	@echo "Running ruff..."
	$(COMPOSE) exec free-ai-selector-data-postgres-api ruff check app/
	$(COMPOSE) exec free-ai-selector-business-api ruff check app/
	@echo ""
	@echo "Running mypy..."
	$(COMPOSE) exec free-ai-selector-data-postgres-api mypy app/
	$(COMPOSE) exec free-ai-selector-business-api mypy app/
	@echo ""
	@echo "Running bandit..."
	$(COMPOSE) exec free-ai-selector-data-postgres-api bandit -r app/ -ll
	$(COMPOSE) exec free-ai-selector-business-api bandit -r app/ -ll

# Форматирование кода ruff format.
format:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:format RUN_SCENARIO=qa:format >/dev/null
	$(COMPOSE) exec free-ai-selector-data-postgres-api ruff format app/
	$(COMPOSE) exec free-ai-selector-business-api ruff format app/

# Применение миграций alembic.
migrate:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:migrate RUN_SCENARIO=db:migrate >/dev/null
	$(COMPOSE) exec free-ai-selector-data-postgres-api alembic upgrade head

# Наполнение БД стартовыми данными.
seed:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:seed RUN_SCENARIO=db:seed >/dev/null
	$(COMPOSE) exec free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed

# =============================================================================
# Health and Interactive Commands
# =============================================================================

# Проверка health сервисов.
# Гарантирует запуск сервисов с актуальным RUN контекстом перед проверкой.
health:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:health RUN_SCENARIO=ops:health >/dev/null

# Низкоуровневый health-check без preflight.
# Используется внутри up/ensure-up-with-context, чтобы не создавать рекурсию.
health-check:
	@echo "Checking service health (MODE=$(MODE))..."
	@echo ""
	@echo "PostgreSQL:"
	@$(COMPOSE) exec postgres pg_isready -U free_ai_selector_user >/dev/null && echo "  ✅ Ready" || echo "  ❌ Not ready"
	@echo ""
	@echo "Data API (container localhost:8001/health):"
	@$(COMPOSE) exec free-ai-selector-data-postgres-api curl -f -s http://localhost:8001/health >/dev/null && echo "  ✅ Healthy" || echo "  ❌ Unhealthy"
	@echo ""
	@echo "Business API (container localhost:8000/health):"
	@$(COMPOSE) exec free-ai-selector-business-api curl -f -s http://localhost:8000/health >/dev/null && echo "  ✅ Healthy" || echo "  ❌ Unhealthy"
	@if [ "$(MODE)" = "local" ]; then \
	    echo ""; \
	    echo "Host ports (local mode only):"; \
	    curl -f -s http://localhost:8001/health >/dev/null && echo "  ✅ Data API host port healthy" || echo "  ❌ Data API host port unavailable"; \
	    curl -f -s http://localhost:8000/health >/dev/null && echo "  ✅ Business API host port healthy" || echo "  ❌ Business API host port unavailable"; \
	fi

# Shell внутри контейнера Data API.
shell-data:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:shell-data RUN_SCENARIO=ops:shell-data >/dev/null
	$(COMPOSE) exec free-ai-selector-data-postgres-api /bin/sh

# Shell внутри контейнера Business API.
shell-business:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:shell-business RUN_SCENARIO=ops:shell-business >/dev/null
	$(COMPOSE) exec free-ai-selector-business-api /bin/sh

# PSQL shell внутри контейнера PostgreSQL.
db-shell:
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:db-shell RUN_SCENARIO=ops:db-shell >/dev/null
	$(COMPOSE) exec postgres psql -U free_ai_selector_user -d free_ai_selector_db

# Фореграунд запуск compose (удобно для локальной отладки).
dev:
	@mkdir -p "$(AUDIT_RESULTS_DIR)"
	@echo "Starting dev mode with run context: RUN_ID=$(RUN_ID), RUN_SOURCE=$(RUN_SOURCE), RUN_SCENARIO=$(RUN_SCENARIO)"
	@RUN_ID="$(RUN_ID)" \
	RUN_SOURCE="$(RUN_SOURCE)" \
	RUN_SCENARIO="$(RUN_SCENARIO)" \
	RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	AUDIT_JSONL_PATH="$(AUDIT_JSONL_PATH)" \
	$(COMPOSE) up --build

# Краткий статус контейнеров.
status:
	$(COMPOSE) ps

# =============================================================================
# Load Testing (Locust in Docker, full lifecycle)
# =============================================================================

# Базовая команда нагрузочного теста:
# 1) Поднимает весь docker-стек;
# 2) Передает RUN_ID/AUDIT контекст в сервисы и Locust;
# 3) Запускает Locust (headless или UI);
# 4) Сохраняет CSV/HTML/JSONL результаты;
# 5) После завершения останавливает docker-стек.
load-test:
	@mkdir -p "$(LOAD_TEST_RESULTS_DIR)"
	@mkdir -p "$(AUDIT_RESULTS_DIR)"
	@if [ ! -f "$(LOCUST_FILE)" ]; then \
	    echo "ERROR: Locust file not found: $(LOCUST_FILE)"; \
	    exit 2; \
	fi
	@echo "Starting load test: scenario=$(LOAD_TEST_SCENARIO), users=$(LOAD_TEST_USERS), run_time=$(LOAD_TEST_RUN_TIME), mode=$(MODE), ui=$(LOAD_TEST_WITH_UI)"
	@echo "Run context: RUN_ID=$(RUN_ID), RUN_SOURCE=$(RUN_SOURCE), RUN_SCENARIO=$(LOAD_TEST_RUN_SCENARIO), RUN_STARTED_AT=$(RUN_STARTED_AT)"
	@echo "Audit: AUDIT_ENABLED=$(AUDIT_ENABLED), container=$(AUDIT_JSONL_PATH), host=$(AUDIT_JSONL_HOST_PATH)"
	@set -e; \
	cleanup() { \
	    echo "Stopping Docker services after load test..."; \
	    $(MAKE) cleanup-load-test >/dev/null; \
	    $(COMPOSE) down; \
	}; \
	trap cleanup EXIT INT TERM; \
	$(MAKE) ensure-up-with-context MODE=$(MODE) \
	    RUN_ID="$(RUN_ID)" \
	    RUN_SOURCE="$(RUN_SOURCE)" \
	    RUN_SCENARIO="$(LOAD_TEST_RUN_SCENARIO)" \
	    RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	    AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	    AUDIT_JSONL_PATH="$(AUDIT_JSONL_PATH)" \
	    AUDIT_JSONL_HOST_PATH="$(AUDIT_JSONL_HOST_PATH)" \
	    >/dev/null; \
	DOCKER_PORT_ARG=""; \
	LOCUST_CMD="locust -f $(LOCUST_FILE) --host $(LOCUST_HOST)"; \
	if [ "$(LOAD_TEST_WITH_UI)" = "true" ]; then \
	    DOCKER_PORT_ARG="-p $(LOAD_TEST_WEB_PORT):$(LOAD_TEST_WEB_PORT)"; \
	    LOCUST_CMD="$$LOCUST_CMD --web-host 0.0.0.0 --web-port $(LOAD_TEST_WEB_PORT)"; \
	    if [ "$(LOAD_TEST_AUTOSTART)" = "true" ]; then \
	        LOCUST_CMD="$$LOCUST_CMD --autostart --autoquit $(LOAD_TEST_AUTOQUIT_SECONDS) --users $(LOAD_TEST_USERS) --spawn-rate $(LOAD_TEST_SPAWN_RATE) --run-time $(LOAD_TEST_RUN_TIME) --csv $(LOAD_TEST_RESULTS_DIR)/$(LOAD_TEST_PREFIX) --html $(LOAD_TEST_RESULTS_DIR)/$(LOAD_TEST_PREFIX).html"; \
	    fi; \
	    echo "Locust UI: http://localhost:$(LOAD_TEST_WEB_PORT)"; \
	else \
	    LOCUST_CMD="$$LOCUST_CMD --headless --users $(LOAD_TEST_USERS) --spawn-rate $(LOAD_TEST_SPAWN_RATE) --run-time $(LOAD_TEST_RUN_TIME) --csv $(LOAD_TEST_RESULTS_DIR)/$(LOAD_TEST_PREFIX) --html $(LOAD_TEST_RESULTS_DIR)/$(LOAD_TEST_PREFIX).html"; \
	fi; \
	docker rm -f "$(LOCUST_RUN_CONTAINER_NAME)" >/dev/null 2>&1 || true; \
	docker run --name "$(LOCUST_RUN_CONTAINER_NAME)" --rm $$DOCKER_PORT_ARG \
	    --entrypoint /bin/sh \
	    --network free-ai-selector-network \
	    -v "$(PWD):/work" \
	    -w /work \
	    -e LOCUST_SCENARIO="$(LOAD_TEST_SCENARIO)" \
	    -e ENABLE_MONITORING="$(LOAD_TEST_MONITORING)" \
	    -e WRITE_RESULTS_JSONL=true \
	    -e INCLUDE_OVERSIZE_PROMPT="$(LOAD_TEST_OVERSIZE)" \
	    -e RESULTS_JSONL_PATH="$(LOAD_TEST_RESULTS_DIR)/$(LOAD_TEST_PREFIX).jsonl" \
	    -e AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	    -e AUDIT_JSONL_PATH="$(AUDIT_JSONL_HOST_PATH)" \
	    -e PROMPT_PATH="/api/v1/prompts/process" \
	    -e MODEL_STATS_PATH="/api/v1/models/stats" \
	    -e HEALTH_PATH="/health" \
	    -e RUN_ID="$(RUN_ID)" \
	    -e RUN_SOURCE="$(RUN_SOURCE)" \
	    -e RUN_SCENARIO="$(LOAD_TEST_RUN_SCENARIO)" \
	    -e RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	    $(LOCUST_IMAGE) -c "$$LOCUST_CMD"; \
	echo "Load test finished. Reports are in $(LOAD_TEST_RESULTS_DIR)"

# Алиас для совместимости: запускает постоянный Locust UI.
load-test-ui:
	@$(MAKE) load-test-ui-up RUN_SOURCE=make:load-test-ui RUN_SCENARIO=load-test:ui

# Поднимает постоянный контейнер Locust UI и оставляет его работать.
# Используется для ручного запуска/остановки нагрузки через браузер.
load-test-ui-up:
	@mkdir -p "$(LOAD_TEST_RESULTS_DIR)"
	@mkdir -p "$(AUDIT_RESULTS_DIR)"
	@if [ ! -f "$(LOCUST_FILE)" ]; then \
	    echo "ERROR: Locust file not found: $(LOCUST_FILE)"; \
	    exit 2; \
	fi
	@$(MAKE) ensure-up-with-context MODE=$(MODE) RUN_SOURCE=make:load-test-ui-up RUN_SCENARIO=load-test:ui >/dev/null
	@docker rm -f "$(LOCUST_UI_CONTAINER_NAME)" >/dev/null 2>&1 || true
	@docker run -d --name "$(LOCUST_UI_CONTAINER_NAME)" \
	    -p "$(LOAD_TEST_WEB_PORT):$(LOAD_TEST_WEB_PORT)" \
	    --entrypoint /bin/sh \
	    --network free-ai-selector-network \
	    -v "$(PWD):/work" \
	    -w /work \
	    -e LOCUST_SCENARIO="$(LOAD_TEST_SCENARIO)" \
	    -e ENABLE_MONITORING="$(LOAD_TEST_MONITORING)" \
	    -e WRITE_RESULTS_JSONL=true \
	    -e INCLUDE_OVERSIZE_PROMPT="$(LOAD_TEST_OVERSIZE)" \
	    -e RESULTS_JSONL_PATH="$(LOAD_TEST_RESULTS_DIR)/ui-$(RUN_ID).jsonl" \
	    -e AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	    -e AUDIT_JSONL_PATH="$(AUDIT_JSONL_HOST_PATH)" \
	    -e PROMPT_PATH="/api/v1/prompts/process" \
	    -e MODEL_STATS_PATH="/api/v1/models/stats" \
	    -e HEALTH_PATH="/health" \
	    -e RUN_ID="$(RUN_ID)" \
	    -e RUN_SOURCE="make:load-test-ui-up" \
	    -e RUN_SCENARIO="load-test:ui" \
	    -e RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	    "$(LOCUST_IMAGE)" -c "locust -f $(LOCUST_FILE) --host $(LOCUST_HOST) --web-host 0.0.0.0 --web-port $(LOAD_TEST_WEB_PORT)"
	@echo "Locust UI is running: http://localhost:$(LOAD_TEST_WEB_PORT)"
	@echo "Use 'make load-test-ui-logs' to watch logs and 'make load-test-ui-down' to stop."

# Показывает логи постоянного контейнера Locust UI.
load-test-ui-logs:
	@docker logs -f "$(LOCUST_UI_CONTAINER_NAME)"

# Останавливает постоянный Locust UI и docker-стек проекта.
load-test-ui-down:
	@$(MAKE) cleanup-load-test >/dev/null
	@$(COMPOSE) down

# Базовый smoke/baseline прогон.
load-test-baseline:
	@$(MAKE) load-test \
	    LOAD_TEST_SCENARIO=baseline \
	    LOAD_TEST_USERS=1 \
	    LOAD_TEST_SPAWN_RATE=1 \
	    LOAD_TEST_RUN_TIME=10m \
	    LOAD_TEST_PREFIX=baseline \
	    LOAD_TEST_MONITORING=true \
	    LOAD_TEST_OVERSIZE=false \
	    RUN_SOURCE=make:load-test-baseline \
	    LOAD_TEST_RUN_SCENARIO=load-test:baseline

# Лестница ramp-up по users: 2 -> 12.
load-test-ramp-up:
	@for users in 2 4 6 8 10 12; do \
	    echo "Ramp-up step: users=$$users"; \
	    $(MAKE) load-test \
	        LOAD_TEST_SCENARIO=ramp_up \
	        LOAD_TEST_USERS=$$users \
	        LOAD_TEST_SPAWN_RATE=2 \
	        LOAD_TEST_RUN_TIME=3m \
	        LOAD_TEST_PREFIX=ramp_up_u$$users \
	        LOAD_TEST_MONITORING=true \
	        LOAD_TEST_OVERSIZE=false \
	        RUN_SOURCE=make:load-test-ramp-up \
	        LOAD_TEST_RUN_SCENARIO=load-test:ramp_up \
	        || exit $$?; \
	done

# Длительная равномерная нагрузка.
load-test-sustained:
	@$(MAKE) load-test \
	    LOAD_TEST_SCENARIO=sustained \
	    LOAD_TEST_USERS=8 \
	    LOAD_TEST_SPAWN_RATE=2 \
	    LOAD_TEST_RUN_TIME=10m \
	    LOAD_TEST_PREFIX=sustained \
	    LOAD_TEST_MONITORING=true \
	    LOAD_TEST_OVERSIZE=false \
	    RUN_SOURCE=make:load-test-sustained \
	    LOAD_TEST_RUN_SCENARIO=load-test:sustained

# Сценарий проверки fallback/failover.
load-test-failover:
	@$(MAKE) load-test \
	    LOAD_TEST_SCENARIO=failover \
	    LOAD_TEST_USERS=6 \
	    LOAD_TEST_SPAWN_RATE=2 \
	    LOAD_TEST_RUN_TIME=10m \
	    LOAD_TEST_PREFIX=failover \
	    LOAD_TEST_MONITORING=true \
	    LOAD_TEST_OVERSIZE=false \
	    RUN_SOURCE=make:load-test-failover \
	    LOAD_TEST_RUN_SCENARIO=load-test:failover

# Короткий recovery прогон после нагрузочных сценариев.
load-test-recovery:
	@$(MAKE) load-test \
	    LOAD_TEST_SCENARIO=baseline \
	    LOAD_TEST_USERS=1 \
	    LOAD_TEST_SPAWN_RATE=1 \
	    LOAD_TEST_RUN_TIME=5m \
	    LOAD_TEST_PREFIX=recovery \
	    LOAD_TEST_MONITORING=true \
	    LOAD_TEST_OVERSIZE=false \
	    RUN_SOURCE=make:load-test-recovery \
	    LOAD_TEST_RUN_SCENARIO=load-test:recovery

# Сценарий с oversize payload (проверка ограничений размера).
load-test-oversize:
	@$(MAKE) load-test \
	    LOAD_TEST_SCENARIO=ramp_up \
	    LOAD_TEST_USERS=4 \
	    LOAD_TEST_SPAWN_RATE=2 \
	    LOAD_TEST_RUN_TIME=5m \
	    LOAD_TEST_PREFIX=ramp_up_oversize \
	    LOAD_TEST_MONITORING=true \
	    LOAD_TEST_OVERSIZE=true \
	    RUN_SOURCE=make:load-test-oversize \
	    LOAD_TEST_RUN_SCENARIO=load-test:oversize

# Полный последовательный прогон всех нагрузочных сценариев.
load-test-all:
	@$(MAKE) load-test-baseline RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-ramp-up RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-sustained RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-failover RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-recovery RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-oversize RUN_SOURCE=make:load-test-all

# Очищает зависшие locust-контейнеры, которые могут удерживать docker-сеть.
cleanup-load-test:
	@docker rm -f "$(LOCUST_UI_CONTAINER_NAME)" >/dev/null 2>&1 || true
	@docker ps -a --format '{{.Names}}' | rg '^free-ai-selector-locust-run-' | xargs -r docker rm -f >/dev/null 2>&1 || true
	@docker ps -a --filter "network=free-ai-selector-network" --filter "ancestor=$(LOCUST_IMAGE)" --format '{{.ID}}' | xargs -r docker rm -f >/dev/null 2>&1 || true
