# Platform setup

Local run of the private Dify and application stacks. Product behavior:
[requirements.md](requirements.md), [architecture.md](architecture.md).
Do not commit `.env`, `dify/.env`, provider keys, or secrets in DSL.

## Host tools

`uv`, plus Docker Desktop (Compose v2) on `PATH`.

## Automated

1. **Bootstrap** (gitignored env copies + `uv sync`): `make bootstrap`
2. **Tests** (optional; no app/Dify Compose; fake Dify; GreenMail via
   Testcontainers): `make test` — does not prove live Studio or indexed
   retrieval.
3. **Stacks** (two terminals; Dify first — it creates `helpdesk_private`):

   ```bash
   make dify-stack-up    # terminal 1
   make app-stack-up     # terminal 2
   ```

   Stop app then Dify (`make app-stack-down`, then `make dify-stack-down`).
   Volume wipe is manual `down -v` (irreversible). First Dify up runs
   `ollama-pull`; wait for exit 0 before creating a knowledge base.

   | Project | File | Role |
   | --- | --- | --- |
   | `helpdesk-dify` | `dify/compose.yml` | Dify platform; **creates** `helpdesk_private` |
   | `helpdesk-app` | `compose.yml` | GreenMail, helpdesk Postgres, ticketing, email-gateway; joins `helpdesk_private` as **external** |

## One-time Studio checklist

1. **Register** at `http://localhost:13080`. Suggested admin:
   `admin@example.test` / `local-dify-admin-change-me`. `INIT_PASSWORD` is
   not the login password.
2. **MCP.** **Tools → MCP** → Streamable HTTP. Name `ticketing`. URL
   **exactly** `http://ticketing:8080/mcp/` (trailing slash; in-network, not
   `localhost:18080`). Expect `list-my-tickets`, `create-ticket`,
   `append-message`. Dify 1.16 `statuses` on `list-my-tickets` must not be
   a single variable; omit it or enter a constant array of three strings.
   Do not pass `[]`. SSRF allowlist:
   `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS=ticketing,email-gateway`
   (`dify/.env.example`). If the SSRF allowlist changes, recreate
   `ssrf_proxy` and `plugin_daemon`.
3. **Import** `dify/apps/email_helpdesk.yml`, then
   `dify/apps/escalate_stale.yml`
   ([dify/apps/README.md](../dify/apps/README.md)). Escalate is a
   **Schedule Trigger**, not User Input. HTTP POST
   `http://ticketing:8080/v1/tickets/escalate-stale`. Studio app env
   `ESCALATION_SECONDS=30` as `older_than_seconds` (not root `.env`).
   After a non-zero `count`, HTTP
   `POST http://email-gateway:8080/v1/emails/send` with `{subject,
   tickets}` (gateway formats the mail; no digest LLM). Publish and
   enable the trigger.
4. **App API key** → gitignored `.env` as `DIFY_EMAIL_HELPDESK_API_KEY`.
   Gateway uses in-network `http://nginx:80/v1/workflows/run`.
5. **Mail.** Real client vs GreenMail; `employee1@example.test` **To:**
   `support@example.test`. Operator digest mailbox:
   `operator@example.test` (`OPERATOR_EMAIL`). Accounts:
   [GreenMail](#greenmail).
6. **Ollama embedding provider.** **Text Embedding** (not LLM); model
   `ibm/granite-embedding:30m`; base URL `http://ollama:11434` (Compose
   hostname, not `localhost`); context size **512**.
7. **Knowledge.** Dataset name exactly `employee-helpdesk`. Import the eight
   topic pages under `knowledge_base/` (skip `README.md`); keep filenames.
   Chunk: delimiter `\n\n`, size **512**, overlap **64**, Q&A format off.
   Index High Quality. Retrieval: vector search only (not hybrid). Top K /
   score threshold must match
   [`tests/eval/golden_retrieval.json`](../tests/eval/golden_retrieval.json).
   Skip Convert to Knowledge Pipeline. Bind the Knowledge Retrieval node;
   Weighted Score vector-only (keyword weight 0). Query stays Start
   `request_text`. Rebind `dataset_ids` on a fresh Studio. Prepare sources
   Code node maps titles to End `source_filenames`. Publish. Re-export
   secret-free DSL only when the graph changed.
8. **Knowledge Service API key** in root `.env` (`DIFY_API_BASE_URL`,
   `DIFY_DATASETS_API_KEY`); never in DSL; do not include `Bearer` in the
   key value. Then `make eval`. The evaluator requires exactly one KB
   named `employee-helpdesk`.
9. **Yandex (one-time).** OpenAI-API-compatible tile; API Base
   `https://ai.api.cloud.yandex.net/v1`; Chat mode; credentials only in
   Dify's store; embedding stays local Ollama. Role
   `ai.languageModels.user`; API key scope `yc.ai.languageModels.execute`.
   Copy the model string from Yandex Cloud AI Studio.

## Ports (loopback only)

| Bind | Service |
| --- | --- |
| `localhost:13080` | Dify UI and Service API |
| `localhost:5003` | Plugin daemon debug |
| `localhost:3025` / `3143` / `8081` | GreenMail SMTP / IMAP / API |
| `localhost:15432` | Helpdesk Postgres (host tools) |
| `localhost:18080` | Ticketing HTTP (`/v1/…`) and MCP (`/mcp`) |

Digest HTTP is in-network only (`http://email-gateway:8080`; no host
bind).

Browse Dify with the same hostname as `NEXT_PUBLIC_SOCKET_URL` in
`dify/.env` (default `ws://localhost:13080`). Weaviate, Dify Postgres, and
Redis have no host ports.

## GreenMail

| Account | Password | Role |
| --- | --- | --- |
| `employee1@example.test` | `employee1-pass` | Employee: compose **To:** `support@example.test` |
| `support@example.test` | `support-pass` | Gateway inbox. Do not poll this account as the employee. |
| `operator@example.test` | `operator-pass` | Operator digest mailbox (`OPERATOR_EMAIL`). Must not equal `IMAP_USER`. |

Connect SMTP to `127.0.0.1:3025` and IMAP to `127.0.0.1:3143`. Extra users
belong in `greenmail.users` in `compose.yml` (the operator account is
already there).

## Env files

`make bootstrap` copies examples to gitignored `dify/.env` and `.env`.
Compose interpolates `.env` with no `:-` fallbacks. `DATABASE_URL` is for
host tools; Compose injects the in-network DSN into ticketing.
`DIFY_DATASETS_API_KEY` is host-side eval only. Escalate threshold is the
Studio app env, not root `.env`. Gateway digest recipient (not a
secret): `OPERATOR_EMAIL=operator@example.test`; must not equal
`IMAP_USER`. Keep `REDIS_SOCKET_TIMEOUT=3600`. Image tags are
pinned in `compose.yml` and `dify/compose.yml`. Embedding model:
`ibm/granite-embedding:30m`.

Gateway diagnosis: `docker compose logs email-gateway`. Look for ERROR
`workflow_failed` (`fail_reason`, `http_status`).

## Restart vs wipe vs re-ingest

Ordinary `up`/`down` keeps named volumes. `down -v` wipes data
(irreversible). To re-ingest from Git: remove the documents on
`employee-helpdesk` (or recreate that dataset), import the eight topic
pages again, rebind the Knowledge Retrieval node if the dataset is new,
then `make eval`. Use the same filenames and chunk settings as the
checklist.
