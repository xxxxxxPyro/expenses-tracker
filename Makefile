# ============================================================
# Expenses Tracker — Makefile
# Usage: make <command>
# Run from project root: ~/repos/expenses-tracker/
# ============================================================

COMPOSE  = docker-compose -f deployments/docker-compose.yml
BOT      = expenses_bot
DB       = expenses_db
DB_USER  = expenses
DB_NAME  = expenses_tracker

.DEFAULT_GOAL := help

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Expenses Tracker — Available commands"
	@echo ""
	@echo "  DOCKER"
	@echo "    make up          Start all containers"
	@echo "    make down        Stop all containers"
	@echo "    make build       Rebuild and start all containers"
	@echo "    make restart     Restart all containers"
	@echo "    make restart-bot Restart only the Telegram bot"
	@echo "    make ps          Show running containers"
	@echo ""
	@echo "  LOGS"
	@echo "    make logs        Tail logs from all containers"
	@echo "    make logs-bot    Tail bot logs"
	@echo "    make logs-db     Tail database logs"
	@echo ""
	@echo "  DATABASE"
	@echo "    make schema      Apply database schema"
	@echo "    make psql        Open psql shell"
	@echo "    make db-reset    ⚠️  Wipe all data and reset IDs"
	@echo "    make db-tables   List all tables"
	@echo "    make db-users    Show registered users"
	@echo "    make db-purchases Show latest purchases"
	@echo ""
	@echo "  OTHER"
	@echo "    make shell-bot   Open shell in bot container"
	@echo ""

# ── Docker ────────────────────────────────────────────────────────────────────

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) down
	$(COMPOSE) up -d --build

restart:
	$(COMPOSE) restart

restart-bot:
	$(COMPOSE) restart bot
	@sleep 2 && $(COMPOSE) logs --tail 15 bot

ps:
	$(COMPOSE) ps

# ── Logs ──────────────────────────────────────────────────────────────────────

logs:
	$(COMPOSE) logs -f --tail 50

logs-bot:
	$(COMPOSE) logs -f --tail 50 bot

logs-db:
	$(COMPOSE) logs -f --tail 50 db

# ── Database ──────────────────────────────────────────────────────────────────

schema:
	@echo "Applying database schema..."
	docker exec -i $(DB) psql -U $(DB_USER) -d $(DB_NAME) < deployments/schema.sql
	@echo "Done."

psql:
	docker exec -it $(DB) psql -U $(DB_USER) -d $(DB_NAME)

db-reset:
	@echo "⚠️  This will DELETE all data. Press Ctrl+C to cancel, Enter to continue."
	@read confirm
	docker exec $(DB) psql -U $(DB_USER) -d $(DB_NAME) -c \
		"TRUNCATE items, purchases, users RESTART IDENTITY CASCADE;"
	@echo "Database wiped and IDs reset."

db-tables:
	docker exec $(DB) psql -U $(DB_USER) -d $(DB_NAME) -c "\dt"

db-users:
	docker exec $(DB) psql -U $(DB_USER) -d $(DB_NAME) -c \
		"SELECT id, telegram_user_id, email, first_name, created_at FROM users;"

db-purchases:
	docker exec $(DB) psql -U $(DB_USER) -d $(DB_NAME) -c \
		"SELECT id, store_name, purchase_date, total_net, payment_method \
		FROM purchases ORDER BY created_at DESC LIMIT 20;"

# ── Other ─────────────────────────────────────────────────────────────────────

shell-bot:
	docker exec -it $(BOT) /bin/bash

.PHONY: help up down build restart restart-bot ps \
        logs logs-bot logs-db \
        schema psql db-reset db-tables db-users db-purchases \
        shell-bot
