# Dify Help Desk


[![Actions Status](https://github.com/denbon05/llm-developer-project-425/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/denbon05/llm-developer-project-425/actions)


An email help-desk assistant for employees. The v1 design answers supported
questions from company knowledge by email with a citation (no ticket, no
`messages` row). When knowledge is insufficient or the employee asks for a
ticket, it opens a ticket (`create-ticket`; `text` in `tickets.text`, set
once) and further dialogue uses `append-message` on that ticket.

This repository is an LLM-focused slice, not a full help-desk product.
Inbound employee email is handled by Dify: knowledge hit → email only;
knowledge gap → ticket plus recorded AI↔employee history. If an `open`
ticket’s `updated_at` is older than the inactivity threshold (default
24h / `escalation_seconds`), it becomes `escalated`. Dialogue via
`append-message` refreshes `updated_at` and delays that step. After
`escalated` is out of scope and not modeled. There is no operator UI
or modeled human reply in this slice. `answered` and `closed` remain
in the schema and are unused here.

## Status

Phase 3 ticketing slice: helpdesk PostgreSQL with `tickets` / `messages`,
MCP tools (`create-ticket`, `list-my-tickets`, `append-message`), private
HTTP `POST /v1/tickets/escalate-stale`, MCP `user_id` (sender email) as a
tool argument, and one-way text masking. Platform setup:
[docs/setup.md](docs/setup.md). Email gateway, knowledge corpus, and Dify
helpdesk workflows are not in this slice.

Host tools (local run and tests): `uv`, plus Docker or Podman on `PATH`.

```bash
make bootstrap         # env files + uv sync --all-extras
make dify-stack-up     # terminal 1
make app-stack-up      # terminal 2 — GreenMail + helpdesk-db + ticketing
make test              # or: uv run pytest
```

## Fixed v1 scope

These bullets constrain the LLM slice above, not a human operator help-desk.

- Self-host Dify on a private LAN/VPN as a replaceable AI brain behind a small,
  versioned interface.
- Use Yandex as the only external foundation-model API. Use local
  `granite-embedding:30m` through Ollama with one Dify knowledge base and
  persistent Weaviate.
- Start with GreenMail for email integration and deterministic end-to-end
  tests; use English synthetic, non-sensitive content and ignore attachments.
- Keep transport and ticket status outside Dify. The deterministic flow either
  emails a grounded cited reply (no ticket, no persisted message), creates a
  ticket for insufficient evidence (`text` in `tickets.text` at create), blocks
  toxicity at the gateway with a static reply, or
  returns a static acknowledgement on classifier/workflow outage (no
  fail-open). `open` tickets whose `updated_at` is older than the
  inactivity threshold escalate over scheduled HTTP.
- Deploy as two pinned Compose projects on a private shared network
  (`compose.yml` and `dify/compose.yml`) and keep deterministic CI free of paid
  model calls.

## Trusted and untrusted content

- **Trusted:** governing instructions, interface/tool schemas, and
  repository-controlled citation mappings.
- **Untrusted:** email content, retrieved passages, and model output. They
  remain data and cannot change routing or authorization.

See [architecture](docs/architecture.md#trust-seams) for the complete trust
model.

## Documentation

- [Domain glossary](CONTEXT.md)
- [Requirements and acceptance criteria](docs/requirements.md)
- [Architecture and interfaces](docs/architecture.md)
- [Bounded delivery roadmap](docs/roadmap.md)
- [Platform setup](docs/setup.md)
