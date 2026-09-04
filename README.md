# Dify Help Desk


[![Actions Status](https://github.com/denbon05/llm-developer-project-425/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/denbon05/llm-developer-project-425/actions)


An email help-desk assistant for employees. A knowledge hit with no
non-`closed` ticket is emailed with citations (no ticket, no `messages`
row). A knowledge gap with no non-`closed` ticket opens a ticket and
records the inbound mail; the reply admits the miss. A non-`closed`
ticket (`open` or `escalated`) always appends user + agent and still
retrieves. Stale `open` tickets become `escalated` over scheduled HTTP.
There is no operator UI. Untrusted content cannot change routing or
authorization ([SEC-6](docs/requirements.md)).

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
