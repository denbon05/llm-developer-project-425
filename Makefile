# Phase 3 application stack — Make wraps both Compose projects.
# Two-terminal workflow: each *-up runs foreground `<cli> compose up`.
# Start Dify first (creates helpdesk_private); app stack joins it as external.

# docker if present, else podman. Override: make CONTAINER_CLI=podman …
CONTAINER_CLI ?= $(notdir $(firstword $(shell command -v docker 2>/dev/null) $(shell command -v podman 2>/dev/null)))
ifeq ($(CONTAINER_CLI),)
$(error Neither docker nor podman found in PATH)
endif

# --project-directory loads that dir's .env for YAML ${VAR} interpolation.
# Service env_file (see dify/compose.yml) injects vars into containers — different step.
DIFY_COMPOSE := $(CONTAINER_CLI) compose -f dify/compose.yml --project-directory dify
APP_COMPOSE := $(CONTAINER_CLI) compose -f compose.yml

# Drive Docker base image tag from .python-version (see Dockerfile ARG).
PYTHON_VERSION := $(shell tr -d '[:space:]' < .python-version)
export PYTHON_VERSION

.PHONY: help bootstrap test format migrate-create migrate-up

help:
	@echo "Phase 3 application stack (two-terminal foreground up):"
	@echo "  make bootstrap              Create env files; print start order"
	@echo "  make dify-stack-up          Start Dify platform (creates helpdesk_private)"
	@echo "  make app-stack-up           Start app stack: GreenMail + helpdesk-db + ticketing"
	@echo "  make dify-stack-down        Stop Dify platform"
	@echo "  make app-stack-down         Stop application stack"
	@echo "  make test                   Run unit + contract pytest suite"
	@echo "  make format                 Ruff format (src + tests)"
	@echo "  make migrate-create m=\"…\" Autogenerate Alembic migration (helpdesk-db up)"
	@echo "  make migrate-up             Apply pending migrations (alembic upgrade head)"
	@echo "  make migrate-up ARGS=--sql  Print SQL only (Alembic offline mode)"
	@echo "  Compose CLI: $(CONTAINER_CLI)  (override CONTAINER_CLI=docker|podman)"

bootstrap: dify-env app-env
	@echo "Env files ready."
	@echo "Terminal 1: make dify-stack-up   # creates helpdesk_private; start first"
	@echo "Terminal 2: make app-stack-up    # joins helpdesk_private (external)"
	@echo "Dify UI: http://127.0.0.1:13080  GreenMail API: http://127.0.0.1:8081"
	@echo "Ticketing HTTP: http://127.0.0.1:18080  MCP: /mcp"

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

format:
	uv run ruff format src tests

# Database migrations (Alembic; needs DATABASE_URL / helpdesk-db)
# Usage: make migrate-create m="add foo"
migrate-create:
	@test -n "$(m)" || (echo 'Usage: make migrate-create m="description"' && exit 1)
	uv run alembic revision --autogenerate -m "$(m)"

migrate-up:
	uv run alembic upgrade head $(ARGS)

# helpers
dify-env:
	@test -f dify/.env || (cp dify/.env.example dify/.env && echo "Created dify/.env from example")

app-env:
	@test -f .env || (cp .env.example .env && echo "Created .env from example")
