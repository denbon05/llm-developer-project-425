# Platform setup

Operational entry points for the private Dify + GreenMail stacks. Product
behavior: [requirements.md](requirements.md), [architecture.md](architecture.md).

## Run (two terminals)

```bash
make bootstrap           # env files + start-order hint
make dify-stack-up       # terminal 1 — creates helpdesk_private
make app-stack-up        # terminal 2 — GreenMail (needs that network)
```

Stop with `make app-stack-down` then `make dify-stack-down`. Use
`docker compose … logs|ps` as needed. Volume wipe is manual `down -v`
(irreversible).

| Project | File | Role |
| --- | --- | --- |
| `helpdesk-dify` | `dify/compose.yml` | Dify, its Postgres, Weaviate, Ollama, Redis, sandbox; **creates** `helpdesk_private` |
| `helpdesk-app` | `compose.yml` | GreenMail; joins `helpdesk_private` as **external** |

Ticket Postgres arrives in Phase 3. Celery beat is omitted until Phase 8.

## Pins

| Component | Tag |
| --- | --- |
| Dify API / web | `1.16.1` |
| Sandbox / plugin-daemon | `0.2.15` / `0.6.3-local` |
| Postgres / Redis | `15.13-alpine` / `6.2.20-alpine` |
| Weaviate / Ollama | `1.27.0` / `0.11.4` (Ollama: 2 CPU / 2 GiB) |
| Nginx / Squid | `1.27.5` / `6.6-24.04_beta` |
| GreenMail | `2.1.11` |
| Embedding (Phase 6) | `granite-embedding:30m` via Ollama |

## Ports (loopback only)

| Bind | Service |
| --- | --- |
| `localhost:13080` | Dify UI (nginx → web/api) |
| `localhost:5003` | Plugin daemon debug |
| `localhost:3025` / `3143` / `8081` | GreenMail SMTP / IMAP / API |

Weaviate, Ollama, Dify Postgres, Redis: no host ports. Browse Dify with the
**same hostname** as `NEXT_PUBLIC_SOCKET_URL` in `dify/.env` (default
`ws://localhost:13080`). Set `REDIS_SOCKET_TIMEOUT=3600` so Studio does not
stall on “Syncing data” (Dify 1.16.1 Socket.IO pub/sub).

## Env files

`make bootstrap` copies examples to gitignored `dify/.env` and `.env`.

Compose uses `dify/.env` twice on purpose: `--project-directory dify` for YAML
`${VAR}` interpolation, and service `env_file` for container injection. Never
commit `.env` files, provider keys, or secrets in DSL.

## First admin (FR-10)

Fresh volumes only: open `http://localhost:13080` and register. Suggested
local values: `admin@example.test` / `local-dify-admin-change-me`.
`INIT_PASSWORD` is an optional pre-install gate, **not** the login password.

Reset later:

```bash
docker compose -f dify/compose.yml --project-directory dify exec -it api \
  flask reset-password
```

## Yandex models (SEC-8) — document only in Phase 2

Yandex is the **only** allowed external model processor. Do **not** install the
OpenAI provider or point at `api.openai.com`.

There is usually no dedicated “Yandex” marketplace tile. Use Dify’s
**OpenAI-API-compatible** provider with Yandex Cloud’s OpenAI-compatible
foundation-models base URL, API key, folder/catalog id, and a Yandex model
name. Store credentials only in Dify’s encrypted provider store.

Live Yandex calls are **not** a Phase 2 gate (opt-in later). Ollama stays
internal for embeddings (`http://ollama:11434`; pull `granite-embedding:30m`
in Phase 6).

## Phase 2 proof

1. Both stacks up; GreenMail `GET http://127.0.0.1:8081/api/service/readiness` → 200.
2. Studio Workflow Start → End (no LLM); run echoes an input. No handwritten
   durable DSL under `dify/apps/` (FR-9; Phase 5/8 exports).
3. Named volumes retain Dify Postgres / Weaviate across ordinary down/up.

Learning checkpoint: Dify stack vs app stack isolation; Ollama local vs Yandex
external; what survives restart (named volumes, not mailbox state).
