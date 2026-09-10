# Employee Helpdesk

[![CI](https://github.com/denbon05/llm-developer-project-425/actions/workflows/ci.yml/badge.svg)](https://github.com/denbon05/llm-developer-project-425/actions/workflows/ci.yml)

An LLM-powered internal email help-desk assistant. Employees email a support
address; the system answers from a knowledge base or — when the knowledge
base cannot answer — opens a tracked support ticket and admits the gap.
Stale open tickets escalate automatically and an operator receives a digest.
There is no human-facing UI; the channel is plain email (IMAP/SMTP).

**Technically interesting:**
- PII is one-way masked before content leaves the gateway (before Dify, before
  ticket storage). Raw employee text never reaches the LLM or the database.
- Trust seams are explicit: employee mail, retrieved passages, and model output
  are untrusted data. Governing instructions, MCP tool schemas, and citation
  filenames are trusted. Untrusted text cannot change routing or authorization.
- Routing is capability-derived, not prompt-inferred: the Dify workflow decides
  create/append/skip via node wiring, not model free-text output.
- The ticketing service exposes both an MCP interface (for Dify tool nodes) and
  a private HTTP interface (for the scheduled escalation trigger).
- A deterministic test suite (unit + integration + contract seams + golden
  retrieval eval) runs against a fake Dify contract and a real GreenMail via
  Testcontainers — no paid model calls in CI.

## Stack

| Layer | Technology |
| --- | --- |
| Email transport | GreenMail (local), generic IMAP/SMTP |
| LLM orchestration | Dify (self-hosted) |
| LLM provider | Yandex Cloud AI Studio (optional; swap any OpenAI-compatible) |
| Embeddings | Ollama + `ibm/granite-embedding:30m` (local) |
| Vector store | Weaviate (persistent, embedded in Dify stack) |
| Ticketing / MCP | FastAPI + MCP server (Python) |
| Database | PostgreSQL (Alembic migrations) |
| Privacy | One-way deterministic PII masking (`src/privacy`) |
| Container orchestration | Docker Compose v2 (two pinned projects) |

## Send a test email

See [Platform setup](docs/setup.md) — the GreenMail accounts and port
list are in that document.

## Dev

Host tools: `uv`, plus Docker Desktop (Compose v2) on `PATH`. Platform
setup: [docs/setup.md](docs/setup.md).

```bash
make bootstrap         # env files + uv sync --all-extras
make dify-stack-up     # terminal 1
make app-stack-up      # terminal 2
make test              # fake Dify; GreenMail via Testcontainers; skips eval
```

Opt-in live retrieval (`make eval`) is in [docs/setup.md](docs/setup.md).

## Documentation

- [Domain glossary](CONTEXT.md)
- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Platform setup](docs/setup.md)
- [Demo screenshots](docs/screenshots/README.md)
