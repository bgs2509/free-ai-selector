.PHONY: help nginx loc build up down restart logs logs-data logs-business logs-bot logs-worker logs-db clean test test-data test-business lint format migrate seed health shell-data shell-business db-shell dev status

# =============================================================================
# Free AI Selector - Команды запуска и сопровождения
# =============================================================================
# Почему тут два режима:
# 1) `nginx` — VPS/production режим за внешним reverse proxy. Порты API на host
#    не публикуются, чтобы не раскрывать сервисы напрямую.
# 2) `loc` — локальная разработка без nginx, с прямым доступом к 8000/8001.
#
# Почему не используем compose override:
# - два независимых compose-файла проще читать и сопровождать;
# - нет неочевидного merge-поведения docker compose.
#
# Почему `make up` оставляем:
# - для обратной совместимости со старыми сценариями;
# - по умолчанию `make up` эквивалентен `make nginx`.
# =============================================================================

MODE ?= nginx
COMPOSE_FILE_NGINX := docker-compose.nginx.yml
COMPOSE_FILE_LOC := docker-compose.loc.yml

ifeq ($(MODE),nginx)
COMPOSE_FILE := $(COMPOSE_FILE_NGINX)
else ifeq ($(MODE),loc)
COMPOSE_FILE := $(COMPOSE_FILE_LOC)
else
$(error Unsupported MODE='$(MODE)'. Use MODE=nginx or MODE=loc)
endif

COMPOSE := docker compose -f $(COMPOSE_FILE)

help:
	@echo "Free AI Selector - Available Commands:"
	@echo ""
	@echo "  make nginx                 - Запуск VPS режима (docker-compose.nginx.yml)"
	@echo "  make loc                   - Запуск локального режима (docker-compose.loc.yml)"
	@echo "  make up                    - Алиас на nginx (обратная совместимость)"
	@echo "  make <target> MODE=loc     - Выполнить target в локальном режиме"
	@echo "  make <target> MODE=nginx   - Выполнить target в VPS режиме"
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
	@echo "  make test                  - Run all tests"
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

# Явные команды запуска для двух режимов
nginx:
	@$(MAKE) up MODE=nginx

loc:
	@$(MAKE) up MODE=loc

build:
	@echo "Using $(COMPOSE_FILE) (MODE=$(MODE))"
	$(COMPOSE) build

# По умолчанию `up` работает как nginx (см. MODE ?= nginx).
up:
	@echo "Starting services with $(COMPOSE_FILE) (MODE=$(MODE))"
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
	@echo "Running Data API tests..."
	$(COMPOSE) exec free-ai-selector-data-postgres-api pytest tests/ -v --cov=app --cov-report=term-missing
	@echo ""
	@echo "Running Business API tests..."
	$(COMPOSE) exec free-ai-selector-business-api pytest tests/ -v --cov=app --cov-report=term-missing

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

# В nginx режиме host-порты API могут быть закрыты, поэтому базовая проверка
# идёт через контейнеры. Для loc дополнительно проверяем host-порты.
health:
	@echo "Checking service health (MODE=$(MODE), compose=$(COMPOSE_FILE))..."
	@echo ""
	@echo "PostgreSQL:"
	@$(COMPOSE) exec postgres pg_isready -U free_ai_selector_user >/dev/null && echo "  ✅ Ready" || echo "  ❌ Not ready"
	@echo ""
	@echo "Data API (container localhost:8001/health):"
	@$(COMPOSE) exec free-ai-selector-data-postgres-api curl -f -s http://localhost:8001/health >/dev/null && echo "  ✅ Healthy" || echo "  ❌ Unhealthy"
	@echo ""
	@echo "Business API (container localhost:8000/health):"
	@$(COMPOSE) exec free-ai-selector-business-api curl -f -s http://localhost:8000/health >/dev/null && echo "  ✅ Healthy" || echo "  ❌ Unhealthy"
	@if [ "$(MODE)" = "loc" ]; then \
		echo ""; \
		echo "Host ports (loc mode only):"; \
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
