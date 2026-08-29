# Application stack (GreenMail, helpdesk-db, ticketing, email-gateway).
# Two-terminal workflow: each *-up runs foreground `docker compose up`.
# Start Dify first (creates helpdesk_private); app stack joins it as external.
# Docker Compose v2 only (Docker Desktop). Podman is not supported.

ifeq ($(shell command -v docker 2>/dev/null),)
$(error docker not found in PATH; install Docker Desktop)
endif

# --env-file loads that file for YAML ${VAR} interpolation.
# Service env_file (see dify/compose.yml) injects vars into containers — different step.
DIFY_COMPOSE := docker compose -f dify/compose.yml --env-file dify/.env
APP_COMPOSE := docker compose -f compose.yml

# Drive Docker base image tag from .python-version (see Dockerfile ARG).
PYTHON_VERSION := $(shell tr -d '[:space:]' < .python-version)
export PYTHON_VERSION

.PHONY: help bootstrap test eval format migrate-create migrate-up migrate-down

help:
	@echo "Application stack (two-terminal foreground up; includes email-gateway):"
	@echo "  make bootstrap              Env files + uv sync --all-extras; print start order"
	@echo "  make dify-stack-up          Start Dify (creates helpdesk_private; ollama-pull uses OLLAMA_EMBEDDING_MODEL)"
	@echo "  make app-stack-up           Start app stack: GreenMail + helpdesk-db + ticketing + email-gateway"
	@echo "  make dify-stack-down        Stop Dify platform"
	@echo "  make app-stack-down         Stop application stack"
	@echo "  make test                   Run pytest (fake Dify; GreenMail via Testcontainers)"
	@echo "  make eval                   Golden retrieval against live Dify knowledge API (opt-in)"
	@echo "  make format                 Ruff format (src + tests)"
	@echo "  make migrate-create m=\"…\" Autogenerate Alembic migration (helpdesk-db up)"
	@echo "  make migrate-up             Apply pending migrations (alembic upgrade head)"
	@echo "  make migrate-up ARGS=--sql  Print SQL only (Alembic offline mode)"
	@echo "  make migrate-down           Rollback one migration (alembic downgrade -1)"
	@echo "  make migrate-down ARGS=--sql  Print SQL only (Alembic offline mode)"
	@echo "  Compose: docker compose (v2; Docker Desktop)"

bootstrap: dify-env app-env
	uv sync --all-extras
	@echo "Env files and local .venv ready."
	@echo "Terminal 1: make dify-stack-up   # creates helpdesk_private; start first"
	@echo "Terminal 2: make app-stack-up    # joins helpdesk_private (external)"
	@echo "Dify UI: http://127.0.0.1:13080  (first visit prompts you to create the admin account)"
	@echo "GreenMail API: http://127.0.0.1:8081"
	@echo "Ticketing HTTP: http://127.0.0.1:18080  MCP: /mcp"
	@echo "Email gateway: Compose service email-gateway (polls GreenMail; Dify via nginx)"

dify-stack-up: dify-env
	$(DIFY_COMPOSE) up

dify-stack-down:
	$(DIFY_COMPOSE) down

app-stack-up: app-env
	$(APP_COMPOSE) up

app-stack-down:
	$(APP_COMPOSE) down

test:
	uv run pytest

eval: app-env
	uv run python -m tests.eval.evaluate

format:
	uv run ruff format src tests

# Database migrations (Alembic; needs DATABASE_URL / helpdesk-db)
# Usage: make migrate-create m="add foo"
migrate-create:
	@test -n "$(m)" || (echo 'Usage: make migrate-create m="description"' && exit 1)
	uv run alembic revision --autogenerate -m "$(m)"

migrate-up:
	uv run alembic upgrade head $(ARGS)

migrate-down:
	uv run alembic downgrade -1 $(ARGS)

# helpers
dify-env:
	@test -f dify/.env || (cp dify/.env.example dify/.env && echo "Created dify/.env from example")

app-env:
	@test -f .env || (cp .env.example .env && echo "Created .env from example")
