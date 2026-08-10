# Delivery Roadmap

Work proceeds as bounded vertical phases. One focused agent owns each phase; a
coordinating agent reviews its evidence against the same glossary,
requirements, and architecture before the next phase starts. No implementation
agent owns the whole system. Each phase updates affected documentation and
ends with a verification gate and a short learning checkpoint.

## Phase 1 — Fix the design

- **Owner:** bounded documentation author, followed by a fresh documentation
  reviewer.
- **Scope:** only `README.md`, `CONTEXT.md`, `AGENTS.md`,
  `docs/requirements.md`, `docs/architecture.md`, and `docs/roadmap.md`. No
  application,
  infrastructure, Dify, knowledge, dependency, script, or test implementation.
- **Verification gate:** all source decisions are traceable; the documents are
  concise, non-duplicative, and mutually consistent; calibrated parameters
  remain explicitly provisional where noted.
- **Learning checkpoint:** explain the actors, deterministic routing rules,
  trust seams, module ownership, and why Dify remains replaceable.

## Phase 2 — Prove the private platform

- **Owner:** bounded platform agent.
- **Scope:** create pinned `dify/compose.yml` and root `compose.yml` behind the
  root `Makefile` (including `make dify-stack-up` and an application up target)
  and private shared network; start Dify with persistent Weaviate and
  resource-limited Ollama; start GreenMail; prove a minimal `Start → End` Dify
  workflow; document the one-time Dify administrator/Yandex-provider setup.
- **Verification gate:** reproducible health/start/stop checks, pinned versions,
  private-only interfaces, persistent-volume restart proof, and no committed
  secrets.
- **Learning checkpoint:** demonstrate stack isolation, local versus external
  model responsibilities, and what must survive a restart.

## Phase 3 — Build the ticketing slice

- **Owner:** bounded ticketing agent.
- **Scope:** implement ticket PostgreSQL, migrations, the private REST and
  narrow MCP contracts, capability-derived employee scope, one-writer message
  ownership, persistence-time masking, idempotency, and the ticket state
  machine.
- **Verification gate:** contract tests at REST and MCP seams cover categories,
  actors, scoped list/follow-up behavior, reconciliation, idempotency,
  lifecycle, operator response, reopen, and auto-close.
- **Learning checkpoint:** explain how one deep ticketing interface protects
  business invariants across two adapters.

## Phase 4 — Prove the email slice

- **Owner:** bounded email-gateway agent.
- **Scope:** connect GreenMail to the gateway, the privacy module, the
  pre-Dify toxicity/abuse word-list gate, a fake of the versioned Dify
  interface, ticketing inbox/outbox operations, and SMTP reply delivery with a
  configurable one-minute default poll.
- **Verification gate:** deterministic GreenMail tests prove normalization,
  attachment exclusion, limits, toxicity static replies without a Dify call,
  pre-Dify masking, exactly-once internal effects, restart recovery, and the
  documented SMTP duplicate window.
- **Learning checkpoint:** distinguish inbox idempotency from receiver-visible
  email delivery guarantees.

## Phase 5 — Replace the fake with Dify

- **Owner:** bounded Dify-workflow agent.
- **Scope:** author the email helpdesk Workflow App in the UI node-by-node,
  expose the agreed input/output contract over Workflow SSE, capture run/usage
  metadata, and export reviewed secret-free DSL under `dify/apps/`.
- **Verification gate:** the same gateway contract tests pass against fake and
  a no-model Dify slice; malformed output and workflow failure defer safely; no
  Yandex-specific response shape leaks through the interface. This gate does
  not claim to verify live Yandex behavior.
- **Learning checkpoint:** show how the small interface permits replacement
  while SSE metadata remains observable.

## Phase 6 — Build knowledge and evaluation

- **Owner:** a separate bounded knowledge/evaluation agent, only after the
  contracts and source metadata rules are fixed.
- **Scope:** create about eight synthetic English Markdown documents (within
  the required 5–10) and golden retrieval cases, ingest one
  `employee-helpdesk` knowledge base, and preserve stable trusted repository
  source IDs/URLs. Eval suite folder layout is chosen in this phase (co-locate
  cases and rubrics). This agent does not change application architecture.
- **Verification gate:** reproducible re-ingestion and measured hybrid
  retrieval meet the golden cases using local `granite-embedding:30m`; Top K
  and threshold are recorded; no reranker or sensitive data is introduced.
- **Learning checkpoint:** explain why Git is canonical, Weaviate is derived,
  and retrieval quality is measured rather than assumed.

## Phase 7 — Integrate controlled intelligence

- **Owner:** bounded Yandex/RAG integration agent.
- **Scope:** add deterministic injection checks, bounded Yandex
  injection/scope classification, ticket-context routing, retrieval evidence
  gating (answer wins when evidence suffices; no ticket on explicit ask),
  grounded generation, trusted citations, and token accounting. Gateway
  toxicity remains outside Dify.
- **Verification gate:** merge-gate route tests use fake Dify behavior and local
  dependencies. Real Yandex classifier/generator routes, live usage matching,
  and full Dify/Yandex behavior are opt-in smoke/evaluation checks.
- **Learning checkpoint:** identify where nondeterministic model behavior is
  constrained by deterministic gates, types, thresholds, and tools.

## Phase 8 — Verify lifecycle and recovery

- **Owner:** bounded lifecycle/verification agent, with final coordinating
  review.
- **Scope:** complete the daily no-LLM Dify lifecycle App for idempotent
  operator digests/repeated reminders and eligible auto-close requests, export
  it under `dify/apps/`, plus negative paths, restore/re-ingestion exercises,
  security checks, and full GreenMail system acceptance with local/fake model
  behavior.
- **Verification gate:** every acceptance criterion in
  [requirements.md](requirements.md) has the required evidence: deterministic
  criteria run locally, while live-model criteria run opt-in and are reported
  separately rather than inferred from fakes.
- **Learning checkpoint:** present the end-to-end trust story, failure
  semantics, recovery procedure, remaining limitations, and tutor evidence.
