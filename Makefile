# ============================================================
# Expenses Tracker — Makefile
# Usage: make <command>
# Run from project root: ~/repos/expenses-tracker/
# ============================================================

COMPOSE     = docker-compose -f deployments/docker-compose.yml
BOT         = expenses_bot
APP         = expenses_app
DB          = expenses_db
DB_USER     = expenses
DB_NAME     = expenses_tracker

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
	@echo "    make restart-app Restart only the FastAPI app"
	@echo "    make ps          Show running containers"
	@echo ""
	@echo "  LOGS"
	@echo "    make logs        Tail logs from all containers"
	@echo "    make logs-bot    Tail bot logs"
	@echo "    make logs-app    Tail app logs"
	@echo "    make logs-db     Tail database logs"
	@echo ""
	@echo "  DATABASE"
	@echo "    make psql        Open psql shell"
	@echo "    make db-reset    ⚠️  Wipe all data and reset IDs"
	@echo "    make db-tables   List all tables"
	@echo "    make db-users    Show registered users"
	@echo "    make db-purchases Show all purchases"
	@echo ""
	@echo "  OPENCLAW"
	@echo "    make gw-start    Start OpenClaw gateway"
	@echo "    make gw-stop     Stop OpenClaw gateway"
	@echo "    make gw-status   Check gateway process status"
	@echo "    make gw-config   Configure OpenClaw (channels, model, etc.)"
	@echo ""
	@echo "  OTHER"
	@echo "    make health      Check API health"
	@echo "    make shell-bot   Open shell in bot container"
	@echo "    make shell-app   Open shell in app container"
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
	@sleep 2 && $(COMPOSE) logs --tail 10 bot

restart-app:
	$(COMPOSE) restart app

ps:
	$(COMPOSE) ps

cleanup:
	$(COMPOSE) down --volumes --remove-orphans
	docker system prune -f

# ── Logs ──────────────────────────────────────────────────────────────────────

logs:
	$(COMPOSE) logs -f --tail 50

logs-bot:
	$(COMPOSE) logs -f --tail 50 bot

logs-app:
	$(COMPOSE) logs -f --tail 50 app

logs-db:
	$(COMPOSE) logs -f --tail 50 db

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	@echo "Running latest migration..."
	docker exec -i $(DB) psql -U $(DB_USER) -d $(DB_NAME) < migrate_multiuser.sql
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
		"SELECT id, internal_id, telegram_user_id, email, first_name, created_at FROM users;"

db-purchases:
	docker exec $(DB) psql -U $(DB_USER) -d $(DB_NAME) -c \
		"SELECT id, store_name, purchase_date, total_net, payment_method FROM purchases ORDER BY created_at DESC LIMIT 20;"

# ── OpenClaw ──────────────────────────────────────────────────────────────────

gw-start:
	openclaw gateway start &
	@echo "OpenClaw gateway started in background."

gw-stop:
	openclaw gateway stop || pkill -f openclaw-gateway || true
	@echo "OpenClaw gateway stopped."

gw-status:
	@ps aux | grep -i "openclaw-gateway" | grep -v grep || echo "Gateway is NOT running."

gw-config:
	openclaw configure --section channels

# ── Other ─────────────────────────────────────────────────────────────────────

health:
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "App not reachable"

shell-bot:
	docker exec -it $(BOT) /bin/bash

shell-app:
	docker exec -it $(APP) /bin/bash

.PHONY: help up down build restart restart-bot restart-app ps \
        logs logs-bot logs-app logs-db \
        migrate psql db-reset db-tables db-users db-purchases \
        gw-start gw-stop gw-status gw-config \
        health shell-bot shell-app