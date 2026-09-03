# Platform setup

Local run of the private Dify and application stacks. Product behavior:
[requirements.md](requirements.md), [architecture.md](architecture.md).
Do not commit `.env`, `dify/.env`, provider keys, or secrets in DSL.

Host tools: `uv`, plus Docker Desktop (Compose v2) on `PATH`.

## Local setup

Pins, ports, and GreenMail accounts are in the tables below.

1. **Bootstrap** (gitignored `dify/.env` and `.env`, then `uv sync`):

   ```bash
   make bootstrap
   ```

2. **Tests** (optional; no Compose, no paid models; fake Dify):

   ```bash
   make test
   ```

   This does not prove the live Studio graph or indexed retrieval.
   `make eval` is the separate opt-in live knowledge check described
   below.

3. **Stacks** (two terminals; Dify first — it creates `helpdesk_private`):

   ```bash
   make dify-stack-up    # terminal 1
   make app-stack-up     # terminal 2
   ```

   Stop with `make app-stack-down` then `make dify-stack-down`. Make runs
   `docker compose` (Podman is not supported). Use `docker compose … logs|ps`
   as needed. Volume wipe is manual `down -v` (irreversible). The app stack
   starts without Dify (GreenMail must be healthy).

   First `make dify-stack-up` also runs `ollama-pull`, which downloads
   `OLLAMA_EMBEDDING_MODEL` into the Ollama volume. Later starts reuse
   the volume (pull is a no-op). Wait until that container exits 0 before
   creating a knowledge base.

   | Project | File | Role |
   | --- | --- | --- |
   | `helpdesk-dify` | `dify/compose.yml` | Dify platform; **creates** `helpdesk_private` |
   | `helpdesk-app` | `compose.yml` | GreenMail, helpdesk Postgres, ticketing, email-gateway; joins `helpdesk_private` as **external** |

4. **Fresh Dify volumes.** Register at `http://localhost:13080`. Suggested
   local admin: `admin@example.test` / `local-dify-admin-change-me`.
   `INIT_PASSWORD` is not the login password.

5. **MCP** is workspace-level, not in `dify/apps/email_helpdesk.yml`. After
   both stacks are up, in Studio: **Tools → MCP** → add Streamable HTTP.
   Name/identifier `ticketing`. URL **exactly** `http://ticketing:8080/mcp/`
   (trailing slash; in-network, not `localhost:18080`). Expect
   `list-my-tickets`, `create-ticket`, `append-message`. If you change
   `SSRF_PROXY_ALLOW_PRIVATE_DOMAINS` (already `ticketing` in
   `dify/.env.example`), recreate `ssrf_proxy` and `plugin_daemon`.

6. **Workflow app.** On a fresh Studio, **Create** → **Import DSL** →
   `dify/apps/email_helpdesk.yml` (Knowledge Retrieval Weighted Score, MCP tool nodes,
   IF/ELSE, live Yandex LLM and classifier, Ticket ID and Reply
   aggregators, End `reply_text` / `ticket_id`). See
   [dify/apps/README.md](../dify/apps/README.md).

7. **Escalate app.** **Create** → **Import DSL** →
   `dify/apps/escalate_stale.yml`. This is a **Schedule Trigger** app, not
   User Input. Graph: trigger → HTTP POST
   `http://ticketing:8080/v1/tickets/escalate-stale` (same `ticketing`
   allowlist as MCP; in-network, not `localhost:18080`). App env
   `ESCALATION_SECONDS` is **30** and is sent as JSON
   `older_than_seconds`. Ticketing still owns the cutoff (`open` +
   `created_at`). HTTP Request retry: 3 attempts, 100ms interval. Publish
   and enable the trigger. No gateway API key. Re-export secret-free DSL
   to `dify/apps/escalate_stale.yml` only when the graph changed. The
   committed cadence is every minute / 30s (local demo).

8. **App API key.** Workflow sidebar **API Access** → Create API Key →
   gitignored `.env` as `DIFY_EMAIL_HELPDESK_API_KEY`. Gateway uses
   in-network `http://nginx:80/v1/workflows/run` (host:
   `http://localhost:13080/v1/workflows/run`).

9. **Mail.** Use a real client against GreenMail, not Dify. As
   `employee1@example.test`, send **To:** `support@example.test`. Confirm
   `email-gateway` polls it and the employee inbox gets the workflow
   reply. Accounts: [GreenMail](#greenmail).

10. **Ollama embedding provider (Studio, one-time).** Manual steps. **Integrations → Model Provider → Ollama**. Add a
   **Text Embedding** model (not an LLM):
   - Model name: `OLLAMA_EMBEDDING_MODEL` (`ibm/granite-embedding:30m`)
   - Base URL: `OLLAMA_BASE_URL` (`http://ollama:11434`). Studio runs in
     a container and must use the Compose hostname, not `localhost`.
   - Context size: **512** (this model's window). Leave the default
     and chunks get truncated or score badly.

11. **Knowledge dataset (Studio, one-time).** **Knowledge → Create →
    Create a ready-to-use knowledge base.** Name it `employee-helpdesk`.
    Import from file the eight topic pages under `knowledge_base/`
    (skip `README.md`). Keep those filenames.

    **Chunk Settings:** custom. Delimiter `\n\n` (our pages are
    paragraphs). Chunk size **512** (Dify defaults to 1024; this embedding
    model’s window is 512), overlap **64** (overlap = size / 8).
    Leave **Chunk using Q&A format** off — that asks an LLM to rewrite
    each chunk as question/answer pairs; we index the policy text as
    written and we do not want a chat model at ingest.

    **Index:** High Quality, embedding model from step 9.

    **Retrieval Setting:** **vector search** (the local embedding model).
    Do not use full-text or hybrid here — hybrid mixes keyword search
    and is Dify's UI recommendation, but this slice measures embeddings.
    Top K and score threshold must match
    [`tests/eval/golden_retrieval.json`](../tests/eval/golden_retrieval.json).
    Skip
    **Convert to Knowledge Pipeline** (a different ingest graph; the
    ready-to-use dataset is enough).

    Wait until documents are indexed. Then in `email_helpdesk` open the
    **Knowledge Retrieval** node (already in the imported DSL) and
    select dataset `employee-helpdesk`. Set the node to **Weighted
    Score** with vector-only weights (keyword weight 0). Top K, score
    threshold, and embedding model must match the eval catalog.
    Exported `dataset_ids` are
    instance-local; a fresh Studio must rebind. Query stays Start
    `request_text`. Keep IF/ELSE and MCP. The **Prepare sources** Code node
    maps retrieval `title` (imported filename) to End `source_filenames` and
    `has_kb_hits` from whether retrieval `result` is empty. The gateway
    turns those filenames into Git URLs. Do not put URLs in the LLM
    prompt or a Sources template. Publish. Re-export secret-free DSL to
    `dify/apps/email_helpdesk.yml` only when the graph changed.

12. **Knowledge Service API key and retrieval evaluation.** In Dify,
    open **Knowledge**, select **Service API** in the top-right, and
    create an API key. A knowledge key can access every knowledge base
    visible to its Dify account, so keep it only in the gitignored root
    `.env`:

    ```dotenv
    DIFY_API_BASE_URL=http://localhost:13080/v1
    DIFY_DATASETS_API_KEY='dataset-...'
    ```

    `DIFY_API_BASE_URL` defaults to that local URL, but recording it
    makes a non-default Dify endpoint explicit. Do not include `Bearer`
    in the stored key value and never put the key in the exported DSL.
    With Dify running and all eight documents indexed, run:

    ```bash
    make eval
    ```

    The evaluator loads these values with Pydantic Settings, lists
    accessible knowledge bases, and requires exactly one with the exact
    name `employee-helpdesk`. It then calls Dify's retrieval endpoint
    for every golden query with the same Weighted Score settings as the
    Knowledge Retrieval node. Each expected filename must own the
    first-ranked indexed chunk. This check uses Dify, Weaviate, and
    local Ollama, but no Yandex or paid model.

When wiring Studio tool nodes: Dify 1.16 MCP array `statuses` on
`list-my-tickets` must not be a single **variable**. Omit it (ticketing
defaults to open/escalated/answered) or enter a **constant array** of
those three strings. Do not pass `[]` (returns no rows). `user_id` is a
variable from Start `user_email`.

## Restart and re-ingest

Ordinary stop/start (`make app-stack-down` / `make dify-stack-down`, then
the matching `*-up`) keeps named volumes: helpdesk Postgres
(tickets/messages) and Weaviate. Do not add `-v` unless you intend to
wipe data.

To rebuild retrieval from Git: in Studio, remove the documents on
`employee-helpdesk` (or recreate that dataset), import the eight topic
pages under `knowledge_base/` again (skip `README.md`; same filenames and
chunk settings as step 11), rebind the Knowledge Retrieval node if the
dataset is new, then `make eval`. Git remains canonical; Weaviate is
derived.

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
| Embedding | `ibm/granite-embedding:30m` via Ollama (`ollama-pull` on stack up) |

## Ports (loopback only)

| Bind | Service |
| --- | --- |
| `localhost:13080` | Dify UI and Service API (nginx → web/api) |
| `localhost:5003` | Plugin daemon debug |
| `localhost:3025` / `3143` / `8081` | GreenMail SMTP / IMAP / API |
| `localhost:15432` | Helpdesk Postgres (local pytest / tools) |
| `localhost:18080` | Ticketing HTTP (`/v1/…`) and MCP (`/mcp`) |

Browse Dify with the same hostname as `NEXT_PUBLIC_SOCKET_URL` in
`dify/.env` (default `ws://localhost:13080`). Weaviate, Dify Postgres,
and Redis have no host ports.

## GreenMail

| Account | Password | Role |
| --- | --- | --- |
| `employee1@example.test` | `employee1-pass` | Employee: compose **To:** `support@example.test` |
| `support@example.test` | `support-pass` | Gateway inbox. Do not poll this account as the employee. |

Connect SMTP to `127.0.0.1:3025` and IMAP to `127.0.0.1:3143`. Extra users
belong in `greenmail.users` in `compose.yml` (not the client UI).

## Env files

`make bootstrap` copies examples to gitignored `dify/.env` and `.env`,
then `uv sync --all-extras`. App-stack Compose interpolates `.env` with
no `:-` fallbacks. Compose uses `dify/.env` twice: `--env-file` for YAML
interpolation and service `env_file` for container injection.
`DATABASE_URL` in `.env` is for host tools; Compose injects the
in-network DSN into ticketing. Ticketing `Settings.escalation_seconds`
defaults to 86400 when the escalate HTTP body omits `older_than_seconds`.
The Schedule Trigger app sends `older_than_seconds` from its own Studio
env `ESCALATION_SECONDS` (30 in `dify/apps/escalate_stale.yml`), not from
root `.env`. The root `DIFY_DATASETS_API_KEY` is for the opt-in host-side
retrieval evaluator; it is not injected into application containers. Keep
`REDIS_SOCKET_TIMEOUT=3600` (already in the Dify example) so Studio does
not stall on “Syncing data”.

Gateway diagnosis: `docker compose logs email-gateway`. Look for ERROR
`workflow_failed` (`fail_reason`, `http_status`).

## Yandex foundation models

One-time provider setup (FR-10). Credentials stay in Dify’s encrypted
store; never Git or exported DSL. Policy:
[requirements.md](requirements.md) SEC-8. This slice uses Yandex Cloud AI
Studio as the external generator. Embedding stays local Ollama.

1. **Yandex Cloud.** Grant the service account role
   `ai.languageModels.user`. Create an API key with scope
   `yc.ai.languageModels.execute`.

2. **Dify Studio.** **Integrations → Model Provider** → add
   **OpenAI-API-compatible** (usually no “Yandex” tile; that is Dify’s
   label for an OpenAI-compatible HTTP client, used here to reach the
   Yandex endpoint, not a ban on other tiles):
   - **API Key:** the Yandex Cloud secret (Dify encrypted store only)
   - **API Base URL:** `https://ai.api.cloud.yandex.net/v1`
   - **Completion mode:** **Chat**
   - **Model name:** copy the model **string** from Yandex Cloud AI Studio.
