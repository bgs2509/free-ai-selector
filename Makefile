.PHONY: help local vps build up down restart logs logs-data logs-business logs-bot logs-worker logs-db clean test test-data test-business lint format migrate seed health shell-data shell-business db-shell dev status \
	load-test load-test-ui load-test-baseline load-test-ramp-up load-test-sustained load-test-failover load-test-recovery load-test-oversize load-test-all

# =============================================================================
# Free AI Selector - Команды запуска и сопровождения
# =============================================================================
# Два режима работы:
# 1) local — локальная разработка с прямым доступом к портам 8000/8001.
#    Использует docker-compose.yml + docker-compose.override.yml (авто-загрузка).
# 2) vps   — VPS/production за внешним nginx reverse proxy.
#    Использует docker-compose.yml + docker-compose.vps.yml (явное указание).
#
# По умолчанию MODE=local (безопаснее для разработки).
# =============================================================================

MODE ?= local

ifeq ($(MODE),local)
# docker compose автоматически загружает docker-compose.yml + docker-compose.override.yml
COMPOSE := docker compose
else ifeq ($(MODE),vps)
# Явно указываем файлы, чтобы override НЕ подгружался
COMPOSE := docker compose -f docker-compose.yml -f docker-compose.vps.yml
else
$(error Unsupported MODE='$(MODE)'. Use MODE=local or MODE=vps)
endif

# =============================================================================
# Load testing configuration (Locust in Docker)
# =============================================================================
LOCUST_IMAGE ?= locustio/locust:2.43.3
LOCUST_FILE ?= docs/api-tests/locustfile.py
LOCUST_HOST ?= http://free-ai-selector-business-api:8000
LOAD_TEST_RESULTS_DIR ?= docs/api-tests/results

LOAD_TEST_SCENARIO ?= baseline
LOAD_TEST_USERS ?= 1
LOAD_TEST_SPAWN_RATE ?= 1
LOAD_TEST_RUN_TIME ?= 10m
LOAD_TEST_PREFIX ?= $(LOAD_TEST_SCENARIO)
LOAD_TEST_MONITORING ?= true
LOAD_TEST_OVERSIZE ?= false
LOAD_TEST_WITH_UI ?= true
LOAD_TEST_AUTOSTART ?= true
LOAD_TEST_AUTOQUIT_SECONDS ?= 10
LOAD_TEST_WEB_PORT ?= 8089

help:
	@echo "Free AI Selector - Available Commands:"
	@echo ""
	@echo "  make local                 - Запуск локального режима (порты 8000/8001)"
	@echo "  make vps                   - Запуск VPS режима (за nginx reverse proxy)"
	@echo "  make up                    - Запуск в текущем MODE (по умолчанию local)"
	@echo "  make <target> MODE=local   - Выполнить target в локальном режиме"
	@echo "  make <target> MODE=vps     - Выполнить target в VPS режиме"
	@echo ""
	@echo "  make build                 - Build all Docker images"
	@echo "  make down                  - Stop all services"
	@echo "  make restart               - Restart all services"
	@echo "  make logs                  - Tail logs from all services"
	@echo "  make logs-data             - Tail logs from Data API"
	@echo "  make logs-business         - Tail logs from Business API"
	@echo "  make logs-bot              - Tail logs from Telegram Bot"
	@echo "  make logs-worker           - Tail logs from Health Worker"
	@echo "  make clean                 - Remove all containers and volumes"
	@echo "  make test                  - Run all tests in containers with final report"
	@echo "  make test-data             - Run Data API tests"
	@echo "  make test-business         - Run Business API tests"
	@echo "  make lint                  - Run linters (ruff, mypy, bandit)"
	@echo "  make format                - Format code with ruff"
	@echo "  make migrate               - Run database migrations"
	@echo "  make seed                  - Seed database with initial data"
	@echo "  make health                - Check health of all services"
	@echo "  make shell-data            - Open shell in Data API container"
	@echo "  make shell-business        - Open shell in Business API container"
	@echo "  make db-shell              - Open PostgreSQL shell"
	@echo "  make status                - Show service status"
	@echo ""
	@echo "Load Testing (Locust in Docker):"
	@echo "  make load-test-baseline    - Baseline (1 user, 10m)"
	@echo "  make load-test-ramp-up     - Ramp-up steps: 2/4/6/8/10/12 users"
	@echo "  make load-test-sustained   - Sustained load (8 users, 10m)"
	@echo "  make load-test-failover    - Provider failover scenario (6 users, 10m)"
	@echo "  make load-test-recovery    - Recovery check (1 user, 5m)"
	@echo "  make load-test-oversize    - Oversize payload scenario (422 checks)"
	@echo "  make load-test-ui          - Run Locust web UI in Docker (manual start)"
	@echo "  make load-test-all         - Run all scenarios sequentially (UI + autostart)"
	@echo "                              (UI доступен на http://localhost:8089)"
	@echo ""

# Явные команды запуска для двух режимов
local:
	@$(MAKE) up MODE=local

vps:
	@$(MAKE) up MODE=vps

build:
	@echo "Building images (MODE=$(MODE))"
	$(COMPOSE) build

up:
	@echo "Starting services (MODE=$(MODE))"
	$(COMPOSE) up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@$(MAKE) health MODE=$(MODE)

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f

logs-data:
	$(COMPOSE) logs -f free-ai-selector-data-postgres-api

logs-business:
	$(COMPOSE) logs -f free-ai-selector-business-api

logs-bot:
	$(COMPOSE) logs -f free-ai-selector-telegram-bot

logs-worker:
	$(COMPOSE) logs -f free-ai-selector-health-worker

logs-db:
	$(COMPOSE) logs -f postgres

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

test:
	@COMPOSE_CMD='$(COMPOSE)' python3 scripts/run_container_tests.py

test-data:
	$(COMPOSE) exec free-ai-selector-data-postgres-api pytest tests/ -v --cov=app --cov-report=term-missing

test-business:
	$(COMPOSE) exec free-ai-selector-business-api pytest tests/ -v --cov=app --cov-report=term-missing

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

format:
	$(COMPOSE) exec free-ai-selector-data-postgres-api ruff format app/
	$(COMPOSE) exec free-ai-selector-business-api ruff format app/

migrate:
	$(COMPOSE) exec free-ai-selector-data-postgres-api alembic upgrade head

seed:
	$(COMPOSE) exec free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed

# В VPS режиме host-порты API закрыты, проверка идёт через контейнеры.
# Для local дополнительно проверяем host-порты.
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

shell-data:
	$(COMPOSE) exec free-ai-selector-data-postgres-api /bin/sh

shell-business:
	$(COMPOSE) exec free-ai-selector-business-api /bin/sh

db-shell:
	$(COMPOSE) exec postgres psql -U free_ai_selector_user -d free_ai_selector_db

dev:
	$(COMPOSE) up --build

status:
	$(COMPOSE) ps

# =============================================================================
# Load testing (Locust in Docker, full lifecycle)
# =============================================================================

load-test:
	@mkdir -p "$(LOAD_TEST_RESULTS_DIR)"
	@echo "Starting load test: scenario=$(LOAD_TEST_SCENARIO), users=$(LOAD_TEST_USERS), run_time=$(LOAD_TEST_RUN_TIME), mode=$(MODE), ui=$(LOAD_TEST_WITH_UI)"
	@set -e; \
	cleanup() { \
		echo "Stopping Docker services after load test..."; \
		$(COMPOSE) down; \
	}; \
	trap cleanup EXIT INT TERM; \
	echo "Starting Docker services for load test..."; \
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
		-e PROMPT_PATH="/api/v1/prompts/process" \
		-e MODEL_STATS_PATH="/api/v1/models/stats" \
		-e HEALTH_PATH="/health" \
		$(LOCUST_IMAGE) -c "$$LOCUST_CMD"; \
	echo "Load test finished. Reports are in $(LOAD_TEST_RESULTS_DIR)"

load-test-ui:
	@echo "Locust UI will be available at http://localhost:$(LOAD_TEST_WEB_PORT)"
	@$(MAKE) load-test \
		LOAD_TEST_WITH_UI=true \
		LOAD_TEST_AUTOSTART=false \
		LOAD_TEST_SCENARIO=baseline \
		LOAD_TEST_PREFIX=ui-baseline

load-test-baseline:
	@$(MAKE) load-test \
		LOAD_TEST_SCENARIO=baseline \
		LOAD_TEST_USERS=1 \
		LOAD_TEST_SPAWN_RATE=1 \
		LOAD_TEST_RUN_TIME=10m \
		LOAD_TEST_PREFIX=baseline \
		LOAD_TEST_MONITORING=true \
		LOAD_TEST_OVERSIZE=false

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
			|| exit $$?; \
	done

load-test-sustained:
	@$(MAKE) load-test \
		LOAD_TEST_SCENARIO=sustained \
		LOAD_TEST_USERS=8 \
		LOAD_TEST_SPAWN_RATE=2 \
		LOAD_TEST_RUN_TIME=10m \
		LOAD_TEST_PREFIX=sustained \
		LOAD_TEST_MONITORING=true \
		LOAD_TEST_OVERSIZE=false

load-test-failover:
	@$(MAKE) load-test \
		LOAD_TEST_SCENARIO=failover \
		LOAD_TEST_USERS=6 \
		LOAD_TEST_SPAWN_RATE=2 \
		LOAD_TEST_RUN_TIME=10m \
		LOAD_TEST_PREFIX=failover \
		LOAD_TEST_MONITORING=true \
		LOAD_TEST_OVERSIZE=false

load-test-recovery:
	@$(MAKE) load-test \
		LOAD_TEST_SCENARIO=baseline \
		LOAD_TEST_USERS=1 \
		LOAD_TEST_SPAWN_RATE=1 \
		LOAD_TEST_RUN_TIME=5m \
		LOAD_TEST_PREFIX=recovery \
		LOAD_TEST_MONITORING=true \
		LOAD_TEST_OVERSIZE=false

load-test-oversize:
	@$(MAKE) load-test \
		LOAD_TEST_SCENARIO=ramp_up \
		LOAD_TEST_USERS=4 \
		LOAD_TEST_SPAWN_RATE=2 \
		LOAD_TEST_RUN_TIME=5m \
		LOAD_TEST_PREFIX=ramp_up_oversize \
		LOAD_TEST_MONITORING=true \
		LOAD_TEST_OVERSIZE=true

load-test-all:
	@$(MAKE) load-test-baseline
	@$(MAKE) load-test-ramp-up
	@$(MAKE) load-test-sustained
	@$(MAKE) load-test-failover
	@$(MAKE) load-test-recovery
	@$(MAKE) load-test-oversize
