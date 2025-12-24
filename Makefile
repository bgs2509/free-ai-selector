.PHONY: help build up down restart logs clean test lint format migrate seed health

# =============================================================================
# Free AI Selector - Development Commands
# =============================================================================
# Level 2 (Development Ready) - Make targets for common operations
# =============================================================================

# Default target
help:
	@echo "Free AI Selector - Available Commands:"
	@echo ""
	@echo "  make build        - Build all Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - Tail logs from all services"
	@echo "  make logs-data    - Tail logs from Data API"
	@echo "  make logs-business - Tail logs from Business API"
	@echo "  make logs-bot     - Tail logs from Telegram Bot"
	@echo "  make logs-worker  - Tail logs from Health Worker"
	@echo "  make clean        - Remove all containers and volumes"
	@echo "  make test         - Run all tests"
	@echo "  make test-data    - Run Data API tests"
	@echo "  make test-business - Run Business API tests"
	@echo "  make lint         - Run linters (ruff, mypy, bandit)"
	@echo "  make format       - Format code with ruff"
	@echo "  make migrate      - Run database migrations"
	@echo "  make seed         - Seed database with initial data"
	@echo "  make health       - Check health of all services"
	@echo "  make shell-data   - Open shell in Data API container"
	@echo "  make shell-business - Open shell in Business API container"
	@echo "  make db-shell     - Open PostgreSQL shell"
	@echo ""

# Build all Docker images
build:
	docker compose build

# Start all services
up:
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@make health

# Stop all services
down:
	docker compose down

# Restart all services
restart:
	docker compose restart

# Tail logs from all services
logs:
	docker compose logs -f

# Tail logs from specific services
logs-data:
	docker compose logs -f free-ai-selector-data-postgres-api

logs-business:
	docker compose logs -f free-ai-selector-business-api

logs-bot:
	docker compose logs -f free-ai-selector-telegram-bot

logs-worker:
	docker compose logs -f free-ai-selector-health-worker

logs-db:
	docker compose logs -f postgres

# Remove all containers and volumes (DANGER: deletes database!)
clean:
	@echo "WARNING: This will delete all data including the database!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose down -v; \
		docker volume rm free-ai-selector-postgres-data 2>/dev/null || true; \
		echo "All containers and volumes removed."; \
	else \
		echo "Clean cancelled."; \
	fi

# Run all tests
test:
	@echo "Running Data API tests..."
	docker compose exec free-ai-selector-data-postgres-api pytest tests/ -v --cov=app --cov-report=term-missing
	@echo ""
	@echo "Running Business API tests..."
	docker compose exec free-ai-selector-business-api pytest tests/ -v --cov=app --cov-report=term-missing

# Run Data API tests only
test-data:
	docker compose exec free-ai-selector-data-postgres-api pytest tests/ -v --cov=app --cov-report=term-missing

# Run Business API tests only
test-business:
	docker compose exec free-ai-selector-business-api pytest tests/ -v --cov=app --cov-report=term-missing

# Run linters
lint:
	@echo "Running ruff..."
	docker compose exec free-ai-selector-data-postgres-api ruff check app/
	docker compose exec free-ai-selector-business-api ruff check app/
	@echo ""
	@echo "Running mypy..."
	docker compose exec free-ai-selector-data-postgres-api mypy app/
	docker compose exec free-ai-selector-business-api mypy app/
	@echo ""
	@echo "Running bandit..."
	docker compose exec free-ai-selector-data-postgres-api bandit -r app/ -ll
	docker compose exec free-ai-selector-business-api bandit -r app/ -ll

# Format code
format:
	docker compose exec free-ai-selector-data-postgres-api ruff format app/
	docker compose exec free-ai-selector-business-api ruff format app/

# Run database migrations
migrate:
	docker compose exec free-ai-selector-data-postgres-api alembic upgrade head

# Seed database with initial data
seed:
	docker compose exec free-ai-selector-data-postgres-api python -m app.infrastructure.database.seed

# Check health of all services
health:
	@echo "Checking service health..."
	@echo ""
	@echo "PostgreSQL:"
	@docker compose exec postgres pg_isready -U free_ai_selector_user || echo "  ❌ Not ready"
	@echo ""
	@echo "Data API (http://localhost:8001/health):"
	@curl -f -s http://localhost:8001/health 2>/dev/null && echo "  ✅ Healthy" || echo "  ❌ Unhealthy"
	@echo ""
	@echo "Business API (http://localhost:8000/health):"
	@curl -f -s http://localhost:8000/health 2>/dev/null && echo "  ✅ Healthy" || echo "  ❌ Unhealthy"

# Open shell in Data API container
shell-data:
	docker compose exec free-ai-selector-data-postgres-api /bin/sh

# Open shell in Business API container
shell-business:
	docker compose exec free-ai-selector-business-api /bin/sh

# Open PostgreSQL shell
db-shell:
	docker compose exec postgres psql -U free_ai_selector_user -d free_ai_selector_db

# Development mode (rebuild and restart)
dev:
	docker compose up --build

# View service status
status:
	docker compose ps
