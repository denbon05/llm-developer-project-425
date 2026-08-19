# Platform setup

Operational entry points for the private Dify + application stacks. Product
behavior: [requirements.md](requirements.md), [architecture.md](architecture.md).

Host tools (local run and tests): `uv`, plus Docker or Podman on `PATH`.

## Run (two terminals)

```bash
make bootstrap           # env files, uv sync --all-extras, start-order hint
make dify-stack-up       # terminal 1 — creates helpdesk_private
make app-stack-up        # terminal 2 — GreenMail + helpdesk-db + ticketing + email-gateway
```

Stop with `make app-stack-down` then `make dify-stack-down`. Make uses
`docker compose` when `docker` is on `PATH`, otherwise `podman compose`
(override with `CONTAINER_CLI=podman` or `docker`). Use
`<cli> compose … logs|ps` as needed. Volume wipe is manual `down -v`
(irreversible).

| Project | File | Role |
| --- | --- | --- |
| `helpdesk-dify` | `dify/compose.yml` | Dify, its Postgres, Weaviate, Ollama, Redis, sandbox; **creates** `helpdesk_private` |
| `helpdesk-app` | `compose.yml` | GreenMail, helpdesk Postgres, ticketing, **email-gateway**; joins `helpdesk_private` as **external** |

Status: Phase 4 **email-gateway** is implemented (IMAP poll, mask, blocking
Dify, SMTP, `\Seen`). Merge-gate uses fake Dify; live echo is opt-in.
`email-gateway` depends on healthy GreenMail only (Dify down still starts;
static acknowledgement path).

Escalate: a Dify daily Schedule Trigger app (not authored yet; Phase 8) will
HTTP-call existing ticketing `POST /v1/tickets/escalate-stale` (inactivity on
`tickets.updated_at`). Escalate rules stay in that endpoint.

Unit/contract/gateway tests: `make test` / `uv run pytest` after
`make bootstrap` (Testcontainers Postgres + GreenMail; fake Dify; Compose
not required). Compose is the real topology and optional local curl against
`localhost:18080`. Live Dify echo is opt-in, not merge-gate.

## Dify Service API (email workflow)

Get the app key in the **Workflow** app: left sidebar **API Access** (or
Publish → Access API) → Create API Key. Put it in gitignored `.env` as
`DIFY_EMAIL_HELPDESK_API_KEY` (placeholder already in `.env.example`).

Call **blocking** Service API:

`POST http://localhost:13080/v1/workflows/run`  
Header: `Authorization` from `DIFY_EMAIL_HELPDESK_API_KEY`.

In-network Compose `email-gateway`: `http://nginx:80/v1/workflows/run`.

Committed echo slice: `dify/apps/email_helpdesk.yml` (Start→End, End emits
`reply_text`). Phase 5 authors the full graph and re-exports.

## Pins

| Component | Tag |
| --- | --- |
| Dify API / web | `1.16.1` |
| Sandbox / plugin-daemon | `0.2.15` / `0.6.3-local` |
| Postgres / Redis | `15.13-alpine` / `6.2.20-alpine` |
| Weaviate / Ollama | `1.27.0` / `0.11.4` (Ollama: 2 CPU / 2 GiB) |
| Nginx / Squid | `1.27.5` / `6.6-24.04_beta` |
| GreenMail | `2.1.11` |
| Helpdesk Postgres | `15.13-alpine` (same pin as Dify Postgres; ticket-domain store) |
| Embedding (Phase 6) | `granite-embedding:30m` via Ollama |

## Ports (loopback only)

| Bind | Service |
| --- | --- |
| `localhost:13080` | Dify UI and Service API (nginx → web/api) |
| `localhost:5003` | Plugin daemon debug |
| `localhost:3025` / `3143` / `8081` | GreenMail SMTP / IMAP / API |
| `localhost:15432` | Helpdesk Postgres (local pytest / tools) |
| `localhost:18080` | Ticketing HTTP (`/v1/…`) and MCP (`/mcp`) |

Weaviate, Ollama, Dify Postgres, Redis: no host ports. Browse Dify with the
**same hostname** as `NEXT_PUBLIC_SOCKET_URL` in `dify/.env` (default
`ws://localhost:13080`). Set `REDIS_SOCKET_TIMEOUT=3600` so Studio does not
stall on “Syncing data” (Dify 1.16.1 Socket.IO pub/sub).

## Env files

`make bootstrap` copies examples to gitignored `dify/.env` and `.env`, then
runs `uv sync --all-extras` so host tools (`pytest`, Alembic, Ruff) have a
`.venv`.
App-stack Compose reads `.env` for `${VAR}` interpolation with **no**
`:-` fallbacks — missing keys fail fast. Escalation is inactivity on
`updated_at` (not calendar time from create). The default timer is
ticketing `Settings.escalation_seconds` (86400); set `ESCALATION_SECONDS`
in `.env` only to override. `DATABASE_URL` is required for the
ticketing process (Compose injects the in-network DSN; host `DATABASE_URL`
in `.env` is for Alembic and other host tools).

Compose uses `dify/.env` twice on purpose: `--env-file dify/.env` for YAML
`${VAR}` interpolation, and service `env_file` for container injection. Never
commit `.env` files, provider keys, or secrets in DSL.

## First admin (FR-10)

Fresh volumes only: open `http://localhost:13080` and register. Suggested
local values: `admin@example.test` / `local-dify-admin-change-me`.
`INIT_PASSWORD` is an optional pre-install gate, **not** the login password.

## Yandex models (SEC-8) — document only in Phase 2

**Yandex Cloud AI Studio** is the only supported external provider (many Studio
FMs OK). Do **not** install the OpenAI provider, watsonx, Cohere, or Jina.
Embedding stays local Ollama.

There is usually no dedicated “Yandex” marketplace tile. Use Dify’s
**OpenAI-API-compatible** provider with Yandex Cloud’s OpenAI-compatible
foundation-models base URL, API key, folder/catalog id, and a Yandex model
name. Store credentials only in Dify’s encrypted provider store.

Live Yandex calls are **not** a Phase 2/4 gate (opt-in later). Ollama stays
internal for embeddings (`http://ollama:11434`; pull `granite-embedding:30m`
in Phase 6). Retrieval later: bi-encoder then LLM-as-reranker (Studio FM,
model TBD) — not a Cohere/Jina rerank slot.

## Phase 2 proof

1. Both stacks up; GreenMail `GET http://127.0.0.1:8081/api/service/readiness` → 200.
2. Studio Workflow Start → End (no LLM); run echoes an input. A committed
   secret-free echo export lives at `dify/apps/email_helpdesk.yml` (End
   `reply_text`). Full graph is Phase 5.
3. Named volumes retain Dify Postgres / Weaviate across ordinary down/up.

Learning checkpoint: Dify stack vs app stack isolation; Ollama local vs Yandex
Cloud AI Studio external; what survives restart (named volumes, not mailbox
state).

## Phase 3 ticketing

1. App stack includes healthy `helpdesk-db` and `ticketing`.
2. `uv run pytest tests/contract tests/unit` passes (HTTP + MCP seams).

MVP store: `tickets` and `messages`; `tickets.text` is masked ticket text
set at create (immutable after); a message always belongs to a ticket;
employee scope via `tickets.user_id` (MCP `user_id` tool argument,
synthetic sender email); one-way text masking; append inserts a message
and bumps `tickets.updated_at` (not ticket text or status); escalate is
HTTP status-only on inactivity; no outbox table (SMTP is Phase 4 gateway).
`create-ticket` still does not insert a `messages` row; the email workflow
(Phase 5) will `append-message` the first user mail after create.

Learning checkpoint: one deep ticketing interface protects invariants across
MCP (LLM) and HTTP escalate-stale.
