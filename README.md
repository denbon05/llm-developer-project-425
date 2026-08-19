# Dify Help Desk


[![Actions Status](https://github.com/denbon05/llm-developer-project-425/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/denbon05/llm-developer-project-425/actions)


An email help-desk assistant for employees. The **gateway** owns IMAP/SMTP;
**Dify** is the brain. A knowledge hit with no open ticket is emailed with
citations (no ticket, no `messages` row). A knowledge gap with no open
ticket opens a ticket (`create-ticket`; `text` in `tickets.text`) **and**
records the first user mail via `append-message`. An already-open ticket
always appends user + agent and still retrieves. The employee cannot force
a ticket when knowledge can answer.

This repository is an LLM-focused slice, not a full help-desk product.
If an `open` ticket’s `updated_at` is older than the inactivity threshold
(default 24h / `escalation_seconds`), it becomes `escalated` via scheduled
HTTP. Dialogue via `append-message` refreshes `updated_at` and delays that
step. After `escalated` is out of scope and not modeled. There is no
operator UI or modeled human reply in this slice. `answered` and `closed`
remain in the schema and are unused here.

## Status

**Phase 4** email gateway is in place: Compose `email-gateway` polls IMAP,
masks via `src/privacy`, POSTs blocking Dify `…/v1/workflows/run`, SMTP-replies,
then sets IMAP `\Seen`. Merge-gate / `make test` uses **fake Dify** (no live
Studio or Yandex). Live echo against Dify is opt-in. A committed Start→End
echo export is at `dify/apps/email_helpdesk.yml`. Platform setup:
[docs/setup.md](docs/setup.md).

Host tools (local run and tests): `uv`, plus Docker or Podman on `PATH`.

```bash
make bootstrap         # env files + uv sync --all-extras
make dify-stack-up     # terminal 1
make app-stack-up      # terminal 2 — GreenMail + helpdesk-db + ticketing + email-gateway
make test              # fake Dify; GreenMail via Testcontainers
```

## Fixed v1 scope

These bullets constrain the LLM slice above, not a human operator help-desk.

- Self-host Dify on a private LAN/VPN as the AI brain. The gateway depends on
  a small blocking Service API contract, not Studio internals.
- Use **Yandex Cloud AI Studio** as the only external model provider. Use
  local `granite-embedding:30m` through Ollama with one Dify knowledge base
  and persistent Weaviate. Later: LLM-as-reranker (Studio FM, model TBD).
- Start with GreenMail for email integration and deterministic end-to-end
  tests; use English synthetic, non-sensitive content and ignore attachments.
- Keep transport outside Dify. Mask PII before any Dify call. Toxicity/hello
  are gateway regex (static SMTP; no Dify). Ticket/KB routing is a Dify
  graph (MCP only from Dify). Classifier/workflow outage → static
  acknowledgement (no fail-open). Escalate is scheduled HTTP from a second
  Dify app; rules stay in ticketing.
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
