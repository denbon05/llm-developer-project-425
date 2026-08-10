# Dify Help Desk


[![Actions Status](https://github.com/denbon05/llm-developer-project-425/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/denbon05/llm-developer-project-425/actions)


An email help-desk assistant for employees. The v1 design answers supported
questions from company knowledge and creates durable tickets when available
evidence is insufficient.

## Status

Phase 1 is documentation only: the domain, requirements, interfaces, trust
model, and delivery phases are defined. The runtime setup, Dify workflow,
containers, ticketing application, email gateway, and knowledge corpus are not
implemented yet.

## Fixed v1 scope

- Self-host Dify on a private LAN/VPN as a replaceable AI brain behind a small,
  versioned interface.
- Use Yandex as the only external foundation-model API. Use local
  `granite-embedding:30m` through Ollama with one Dify knowledge base and
  persistent Weaviate.
- Start with GreenMail for email integration and deterministic end-to-end
  tests; use English synthetic, non-sensitive content and ignore attachments.
- Keep transport and ticket state outside Dify. The deterministic flow either
  updates an existing ticket, returns a grounded answer when evidence
  suffices (no ticket, even on an explicit ticket ask), creates a ticket for
  insufficient evidence, blocks toxicity at the gateway with a static reply, or
  safely rejects/defers the request.
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
