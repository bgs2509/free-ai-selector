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

.PHONY: help local vps build up down restart logs logs-data logs-business logs-bot logs-worker logs-db clean test test-data test-business lint format migrate seed health shell-data shell-business db-shell dev status \
	load-test load-test-ui load-test-baseline load-test-ramp-up load-test-sustained load-test-failover load-test-recovery load-test-oversize load-test-all

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
# Можно передать извне: `make load-test-baseline RUN_ID=my-run-001`.
RUN_ID ?= lt-$(shell date -u +%Y%m%dT%H%M%SZ)-$(shell cut -c1-8 /proc/sys/kernel/random/uuid)

# Источник запуска (скрипт/команда), используется в аудит-логах.
# По умолчанию содержит имя текущего make target.
RUN_SOURCE ?= make:$(MAKECMDGOALS)

# Сценарий прогона для трассировки.
# Для load-test обычно совпадает с LOAD_TEST_SCENARIO.
RUN_SCENARIO ?= baseline

# UTC-время старта прогона (ISO-8601).
RUN_STARTED_AT ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ)

# Включение audit-логирования во всех сервисах и Locust.
# true  -> писать audit.jsonl
# false -> не писать аудит
AUDIT_ENABLED ?= true

# Папка для audit-артефактов (host path).
AUDIT_RESULTS_DIR ?= docs/api-tests/results/audit

# Единый JSONL файл аудита (host path).
# Внутри контейнеров будет доступен как /audit/audit.jsonl.
AUDIT_JSONL_PATH ?= $(AUDIT_RESULTS_DIR)/audit.jsonl

# Экспортируем run/audit контекст в sub-make и shell-команды.
export RUN_ID
export RUN_SOURCE
export RUN_SCENARIO
export RUN_STARTED_AT
export AUDIT_ENABLED
export AUDIT_JSONL_PATH

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

# Синхронизация RUN_SCENARIO с нагрузочным сценарием.
RUN_SCENARIO := $(LOAD_TEST_SCENARIO)

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
	@echo "  make restart               - Restart all services"
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
	@echo "  make load-test-ui          - Run Locust web UI in Docker (manual start)"
	@echo "  make load-test-all         - Run all scenarios sequentially"
	@echo ""
	@echo "Run context / audit variables:"
	@echo "  RUN_ID=$(RUN_ID)"
	@echo "  RUN_SOURCE=$(RUN_SOURCE)"
	@echo "  RUN_SCENARIO=$(RUN_SCENARIO)"
	@echo "  RUN_STARTED_AT=$(RUN_STARTED_AT)"
	@echo "  AUDIT_ENABLED=$(AUDIT_ENABLED)"
	@echo "  AUDIT_JSONL_PATH=$(AUDIT_JSONL_PATH)"

# =============================================================================
# Mode Shortcuts
# =============================================================================

# Явный запуск локального режима.
local:
	@$(MAKE) up MODE=local

# Явный запуск VPS режима.
vps:
	@$(MAKE) up MODE=vps

# =============================================================================
# Service Lifecycle Commands
# =============================================================================

# Сборка образов всех сервисов.
build:
	@echo "Building images (MODE=$(MODE))"
	$(COMPOSE) build

# Запуск всех сервисов, затем health-check.
up:
	@echo "Starting services (MODE=$(MODE))"
	$(COMPOSE) up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@$(MAKE) health MODE=$(MODE)

# Остановка всех сервисов в текущем MODE.
down:
	$(COMPOSE) down

# Рестарт всех сервисов в текущем MODE.
restart:
	$(COMPOSE) restart

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
test:
	@COMPOSE_CMD='$(COMPOSE)' python3 scripts/run_container_tests.py

# Запуск unit/integration тестов Data API.
test-data:
	$(COMPOSE) exec free-ai-selector-data-postgres-api pytest tests/ -v --cov=app --cov-report=term-missing

# Запуск unit/integration тестов Business API.
test-business:
	$(COMPOSE) exec free-ai-selector-business-api pytest tests/ -v --cov=app --cov-report=term-missing

# Запуск линтеров для Data API и Business API.
lint:
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
	$(COMPOSE) exec free-ai-selector-data-postgres-api ruff format app/
	$(COMPOSE) exec free-ai-selector-business-api ruff format app/

# Применение миграций alembic.
migrate:
	$(COMPOSE) exec free-ai-selector-data-postgres-api alembic upgrade head

# Наполнение БД стартовыми данными.
seed:
	$(COMPOSE) exec free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed

# =============================================================================
# Health and Interactive Commands
# =============================================================================

# Проверка health сервисов.
# В MODE=local дополнительно проверяются host-порты 8000/8001.
health:
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
	$(COMPOSE) exec free-ai-selector-data-postgres-api /bin/sh

# Shell внутри контейнера Business API.
shell-business:
	$(COMPOSE) exec free-ai-selector-business-api /bin/sh

# PSQL shell внутри контейнера PostgreSQL.
db-shell:
	$(COMPOSE) exec postgres psql -U free_ai_selector_user -d free_ai_selector_db

# Фореграунд запуск compose (удобно для локальной отладки).
dev:
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
	@echo "Starting load test: scenario=$(LOAD_TEST_SCENARIO), users=$(LOAD_TEST_USERS), run_time=$(LOAD_TEST_RUN_TIME), mode=$(MODE), ui=$(LOAD_TEST_WITH_UI)"
	@echo "Run context: RUN_ID=$(RUN_ID), RUN_SOURCE=$(RUN_SOURCE), RUN_SCENARIO=$(RUN_SCENARIO), RUN_STARTED_AT=$(RUN_STARTED_AT)"
	@echo "Audit: AUDIT_ENABLED=$(AUDIT_ENABLED), AUDIT_JSONL_PATH=$(AUDIT_JSONL_PATH)"
	@set -e; \
	cleanup() { \
	    echo "Stopping Docker services after load test..."; \
	    $(COMPOSE) down; \
	}; \
	trap cleanup EXIT INT TERM; \
	echo "Starting Docker services for load test..."; \
	RUN_ID="$(RUN_ID)" \
	RUN_SOURCE="$(RUN_SOURCE)" \
	RUN_SCENARIO="$(RUN_SCENARIO)" \
	RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	AUDIT_ENABLED="$(AUDIT_ENABLED)" \
	AUDIT_JSONL_PATH="/audit/audit.jsonl" \
	$(COMPOSE) up -d --build; \
	$(MAKE) health MODE=$(MODE); \
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
	docker run --rm $$DOCKER_PORT_ARG \
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
	    -e AUDIT_JSONL_PATH="$(AUDIT_JSONL_PATH)" \
	    -e PROMPT_PATH="/api/v1/prompts/process" \
	    -e MODEL_STATS_PATH="/api/v1/models/stats" \
	    -e HEALTH_PATH="/health" \
	    -e RUN_ID="$(RUN_ID)" \
	    -e RUN_SOURCE="$(RUN_SOURCE)" \
	    -e RUN_SCENARIO="$(RUN_SCENARIO)" \
	    -e RUN_STARTED_AT="$(RUN_STARTED_AT)" \
	    $(LOCUST_IMAGE) -c "$$LOCUST_CMD"; \
	echo "Load test finished. Reports are in $(LOAD_TEST_RESULTS_DIR)"

# UI-режим Locust без автозапуска нагрузки.
# Удобен для ручного старта сценариев из браузера.
load-test-ui:
	@echo "Locust UI will be available at http://localhost:$(LOAD_TEST_WEB_PORT)"
	@$(MAKE) load-test \
	    LOAD_TEST_WITH_UI=true \
	    LOAD_TEST_AUTOSTART=false \
	    LOAD_TEST_SCENARIO=baseline \
	    LOAD_TEST_PREFIX=ui-baseline \
	    RUN_SOURCE=make:load-test-ui

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
	    RUN_SOURCE=make:load-test-baseline

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
	    RUN_SOURCE=make:load-test-sustained

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
	    RUN_SOURCE=make:load-test-failover

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
	    RUN_SOURCE=make:load-test-recovery

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
	    RUN_SOURCE=make:load-test-oversize

# Полный последовательный прогон всех нагрузочных сценариев.
load-test-all:
	@$(MAKE) load-test-baseline RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-ramp-up RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-sustained RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-failover RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-recovery RUN_SOURCE=make:load-test-all
	@$(MAKE) load-test-oversize RUN_SOURCE=make:load-test-all
