# Phase 2 private platform — Make wraps both Compose projects.
# Two-terminal workflow: each *-up runs foreground `docker compose up`.
# Start Dify first (creates helpdesk_private); app stack joins it as external.

# --project-directory loads that dir's .env for YAML ${VAR} interpolation.
# Service env_file (see dify/compose.yml) injects vars into containers — different step.
DIFY_COMPOSE := docker compose -f dify/compose.yml --project-directory dify
APP_COMPOSE := docker compose -f compose.yml

.PHONY: help bootstrap

help:
	@echo "Phase 2 private platform (two-terminal foreground up):"
	@echo "  make bootstrap              Create env files; print start order"
	@echo "  make dify-stack-up          Start Dify platform (creates helpdesk_private)"
	@echo "  make app-stack-up           Start application stack (needs network from Dify)"
	@echo "  make dify-stack-down        Stop Dify platform"
	@echo "  make app-stack-down         Stop application stack"

bootstrap: dify-env app-env
	@echo "Env files ready."
	@echo "Terminal 1: make dify-stack-up   # creates helpdesk_private; start first"
	@echo "Terminal 2: make app-stack-up    # joins helpdesk_private (external)"
	@echo "Dify UI: http://127.0.0.1:13080  GreenMail API: http://127.0.0.1:8081"

dify-stack-up: dify-env
	$(DIFY_COMPOSE) up

dify-stack-down:
	$(DIFY_COMPOSE) down

app-stack-up: app-env
	$(APP_COMPOSE) up

app-stack-down:
	$(APP_COMPOSE) down

# helpers
dify-env:
	@test -f dify/.env || (cp dify/.env.example dify/.env && echo "Created dify/.env from example")

app-env:
	@test -f .env || (cp .env.example .env && echo "Created .env from example")
