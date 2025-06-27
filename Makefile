# NADIA HITL Makefile
# Simplified commands for development and production management

.PHONY: help dev prod build test clean logs backup deploy status scale health

# Default environment
ENV ?= production
COMPOSE_FILE ?= docker-compose.yml
BACKUP_TYPE ?= full

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

## ====================================================================
## Help and Documentation
## ====================================================================

help: ## Show this help message
	@echo "$(GREEN)NADIA HITL Management Commands$(NC)"
	@echo "================================="
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(dev|test|clean)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Production:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(prod|build|deploy)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Operations:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '^(logs|backup|status|scale|health)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make dev                    # Start development environment"
	@echo "  make test                   # Run tests"
	@echo "  make prod                   # Start production environment"
	@echo "  make deploy                 # Deploy to production"
	@echo "  make backup BACKUP_TYPE=db  # Backup database only"
	@echo "  make scale SERVICE=api REPLICAS=3  # Scale API to 3 replicas"

## ====================================================================
## Development Commands
## ====================================================================

dev: ## Start development environment with hot reload
	@echo "$(GREEN)Starting NADIA HITL development environment...$(NC)"
	@docker-compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)Development environment started!$(NC)"
	@echo "  Dashboard: http://localhost:3000"
	@echo "  API: http://localhost:8000"
	@echo "  Jupyter: http://localhost:8888"
	@echo "  Redis Commander: http://localhost:8081"
	@echo "  pgAdmin: http://localhost:8082"

dev-build: ## Build development images
	@echo "$(GREEN)Building development images...$(NC)"
	@docker-compose -f docker-compose.dev.yml build

dev-logs: ## Show development logs
	@docker-compose -f docker-compose.dev.yml logs -f

dev-stop: ## Stop development environment
	@echo "$(YELLOW)Stopping development environment...$(NC)"
	@docker-compose -f docker-compose.dev.yml down

dev-clean: ## Clean development environment (remove volumes)
	@echo "$(RED)Cleaning development environment (this will delete data)...$(NC)"
	@docker-compose -f docker-compose.dev.yml down -v
	@docker system prune -f

## ====================================================================
## Testing Commands
## ====================================================================

test: ## Run all tests with coverage
	@echo "$(GREEN)Running NADIA HITL tests...$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ -v --cov=. --cov-report=term-missing

test-unit: ## Run unit tests only (fast, no external dependencies)
	@echo "$(GREEN)Running unit tests...$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ -v -m "unit"

test-integration: ## Run integration tests only (requires DB/Redis)
	@echo "$(GREEN)Running integration tests...$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ -v -m "integration"

test-e2e: ## Run end-to-end tests
	@echo "$(GREEN)Running end-to-end tests...$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ -v -m "e2e"

test-coverage: ## Run tests with detailed coverage report
	@echo "$(GREEN)Running tests with coverage analysis...$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=80
	@echo "$(YELLOW)Coverage report generated at htmlcov/index.html$(NC)"

test-local: ## Run tests locally (requires local setup)
	@echo "$(GREEN)Running tests locally...$(NC)"
	@PYTHONPATH=$(PWD) pytest tests/ -v

test-specific: ## Run specific test file (use TEST=test_filename.py)
	@echo "$(GREEN)Running specific test: $(TEST)$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/$(TEST) -v

test-watch: ## Run tests in watch mode (reruns on file changes)
	@echo "$(GREEN)Running tests in watch mode...$(NC)"
	@docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ -v --looponfail

lint: ## Run code linting
	@echo "$(GREEN)Running linter...$(NC)"
	@docker run --rm -v $(PWD):/app -w /app python:3.12-slim bash -c "pip install ruff && ruff check ."

format: ## Format code
	@echo "$(GREEN)Formatting code...$(NC)"
	@docker run --rm -v $(PWD):/app -w /app python:3.12-slim bash -c "pip install ruff && ruff format ."

## ====================================================================
## Production Commands
## ====================================================================

prod: ## Start production environment
	@echo "$(GREEN)Starting NADIA HITL production environment...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)Production environment started!$(NC)"
	@echo "  Dashboard: http://localhost:3000"
	@echo "  API: http://localhost:8000"
	@echo "  Monitoring: http://localhost:3001"

prod-build: ## Build production images
	@echo "$(GREEN)Building production images...$(NC)"
	@BUILD_DATE=$$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
	 BUILD_VERSION=$${BUILD_VERSION:-latest} \
	 BUILD_COMMIT=$$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown') \
	 docker-compose -f $(COMPOSE_FILE) build \
	   --build-arg BUILD_DATE=$$BUILD_DATE \
	   --build-arg BUILD_VERSION=$$BUILD_VERSION \
	   --build-arg BUILD_COMMIT=$$BUILD_COMMIT

prod-stop: ## Stop production environment
	@echo "$(YELLOW)Stopping production environment...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) down

prod-restart: ## Restart production environment
	@echo "$(YELLOW)Restarting production environment...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) restart

## ====================================================================
## Build and Deployment
## ====================================================================

build: prod-build ## Alias for prod-build

deploy: ## Deploy to production with full automation
	@echo "$(GREEN)Deploying NADIA HITL to production...$(NC)"
	@./scripts/deploy.sh --environment $(ENV)

deploy-staging: ## Deploy to staging environment
	@echo "$(GREEN)Deploying NADIA HITL to staging...$(NC)"
	@./scripts/deploy.sh --environment staging

deploy-quick: ## Quick deploy (skip tests and backup)
	@echo "$(YELLOW)Quick deployment (skipping tests and backup)...$(NC)"
	@./scripts/deploy.sh --environment $(ENV) --skip-tests --skip-backup

## ====================================================================
## Operations and Monitoring
## ====================================================================

logs: ## Show logs for all services
	@docker-compose -f $(COMPOSE_FILE) logs -f

logs-api: ## Show API logs only
	@docker-compose -f $(COMPOSE_FILE) logs -f nadia-api

logs-bot: ## Show bot logs only
	@docker-compose -f $(COMPOSE_FILE) logs -f nadia-bot

logs-db: ## Show database logs only
	@docker-compose -f $(COMPOSE_FILE) logs -f postgres

status: ## Show service status
	@echo "$(GREEN)NADIA HITL Service Status:$(NC)"
	@docker-compose -f $(COMPOSE_FILE) ps
	@echo ""
	@echo "$(GREEN)Resource Usage:$(NC)"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

health: ## Run health checks
	@echo "$(GREEN)Running health checks...$(NC)"
	@python monitoring/health_check.py || echo "$(RED)Health check script not available$(NC)"
	@echo ""
	@echo "$(GREEN)Service Health:$(NC)"
	@curl -f -s http://localhost:8000/health > /dev/null && echo "✓ API: Healthy" || echo "✗ API: Unhealthy"
	@curl -f -s http://localhost:3000 > /dev/null && echo "✓ Dashboard: Healthy" || echo "✗ Dashboard: Unhealthy"

scale: ## Scale a service (usage: make scale SERVICE=api REPLICAS=3)
	@echo "$(GREEN)Scaling $(SERVICE) to $(REPLICAS) replicas...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) up -d --scale nadia-$(SERVICE)=$(REPLICAS)

## ====================================================================
## Backup and Restore
## ====================================================================

backup: ## Create backup (BACKUP_TYPE: full|database|config|logs)
	@echo "$(GREEN)Creating $(BACKUP_TYPE) backup...$(NC)"
	@./scripts/backup.sh --type $(BACKUP_TYPE)

backup-db: ## Backup database only
	@$(MAKE) backup BACKUP_TYPE=database

backup-config: ## Backup configuration only
	@$(MAKE) backup BACKUP_TYPE=config

backup-full: ## Full system backup
	@$(MAKE) backup BACKUP_TYPE=full

restore-db: ## Restore database from latest backup
	@echo "$(YELLOW)Restoring database from latest backup...$(NC)"
	@latest_backup=$$(ls -t backups/nadia_db_*.sql.gz 2>/dev/null | head -n1); \
	if [ -n "$$latest_backup" ]; then \
		echo "Restoring from $$latest_backup"; \
		gunzip -c "$$latest_backup" | docker-compose -f $(COMPOSE_FILE) exec -T postgres psql -U postgres -d nadia_hitl; \
		echo "$(GREEN)Database restored successfully$(NC)"; \
	else \
		echo "$(RED)No database backup found$(NC)"; \
		exit 1; \
	fi

## ====================================================================
## Maintenance and Cleanup
## ====================================================================

clean: ## Clean up Docker resources
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	@docker system prune -f
	@docker volume prune -f

clean-all: ## Clean everything (DANGEROUS - removes all data)
	@echo "$(RED)WARNING: This will remove ALL data including volumes!$(NC)"
	@echo "Press Ctrl+C to cancel, or wait 10 seconds to continue..."
	@sleep 10
	@docker-compose -f $(COMPOSE_FILE) down -v
	@docker-compose -f docker-compose.dev.yml down -v
	@docker system prune -af
	@docker volume prune -f

update: ## Update Docker images
	@echo "$(GREEN)Updating Docker images...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) pull
	@docker-compose -f docker-compose.dev.yml pull

## ====================================================================
## Database Operations
## ====================================================================

db-shell: ## Connect to database shell
	@docker-compose -f $(COMPOSE_FILE) exec postgres psql -U postgres -d nadia_hitl

db-migrate: ## Run database migrations
	@echo "$(GREEN)Running database migrations...$(NC)"
	@docker-compose -f $(COMPOSE_FILE) exec nadia-api python -m alembic upgrade head

db-reset: ## Reset database (DANGEROUS)
	@echo "$(RED)WARNING: This will reset the database!$(NC)"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@docker-compose -f $(COMPOSE_FILE) exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS nadia_hitl; CREATE DATABASE nadia_hitl;"

## ====================================================================
## Development Utilities
## ====================================================================

shell: ## Access application shell
	@docker-compose -f $(COMPOSE_FILE) exec nadia-api bash

jupyter: ## Start Jupyter notebook
	@echo "$(GREEN)Starting Jupyter notebook...$(NC)"
	@docker-compose -f docker-compose.dev.yml up -d jupyter
	@echo "Jupyter available at: http://localhost:8888"

redis-cli: ## Access Redis CLI
	@docker-compose -f $(COMPOSE_FILE) exec redis redis-cli

## ====================================================================
## Security and Monitoring
## ====================================================================

security-scan: ## Run security scan
	@echo "$(GREEN)Running security scan...$(NC)"
	@docker run --rm -v $(PWD):/app -w /app securecodewarrior/docker-security-scanner

monitor: ## Open monitoring dashboard
	@echo "$(GREEN)Opening monitoring dashboard...$(NC)"
	@echo "Grafana: http://localhost:3001"
	@echo "Prometheus: http://localhost:9090"

## ====================================================================
## Conditional targets for CI/CD
## ====================================================================

ci-test: lint test ## Run CI tests (lint + unit tests)

ci-build: prod-build ## Build for CI

ci-deploy: ## Deploy in CI environment
	@echo "$(GREEN)CI Deployment...$(NC)"
	@./scripts/deploy.sh --environment production --skip-backup