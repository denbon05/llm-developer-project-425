# Delivery Roadmap

Work proceeds as bounded vertical phases. One focused agent owns each phase; a
coordinating agent reviews its evidence against the same glossary,
requirements, and architecture before the next phase starts. No implementation
agent owns the whole system. Each phase updates affected documentation and
ends with a verification gate and a short learning checkpoint.

Phases 1–3 are historical (done). Current work is Phase 4.

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
- **Learning checkpoint:** explain the participants/roles, deterministic
  routing rules, trust seams, and module ownership. The gateway depends on
  the small blocking HTTP contract (`/v1/workflows/run` + Start/End fields),
  not Studio internals. Dify remains the orchestrator of the LLM/KB/MCP
  graph.

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
- **Scope:** implement helpdesk PostgreSQL with the MVP schema (`tickets` and
  `messages`), migrations, private HTTP
  (`POST /v1/tickets/escalate-stale`) and MCP (`create-ticket`,
  `list-my-tickets`, `append-message`), `user_id` as an MCP tool argument
  (synthetic sender email), persistence-time text masking, and escalate as
  status-only. No outbox/quarantine tables. No email gateway or Dify
  workflows in this phase. `create-ticket` does **not** insert a `messages`
  row (invariant kept in later phases).
- **Verification gate:** contract tests at HTTP and MCP seams cover categories
  (including `other`), user/agent roles, scoped list, create (`text` only),
  append for chat history, agent append with usage on a ticket (bumps `updated_at`, not
  ticket text or status), masking, and HTTP escalate-stale (inactivity on
  `updated_at`).
- **Learning checkpoint:** explain how one deep ticketing interface protects
  business invariants across two adapters.

## Phase 4 — Prove the email slice (slim)

- **Owner:** bounded email-gateway agent.
- **Scope:** Compose `email-gateway`. Gateway IMAP poll (generic IMAP;
  GreenMail adapter; default 1 minute, configurable), normalize plain text /
  sanitized HTML, ignore attachments, one-way mask via `src/privacy`,
  blocking Dify Service API contract (fake in CI; live echo opt-in), SMTP
  reply using the live mail-session recipient, IMAP `\Seen` after success,
  restart recovery, documented SMTP duplicate window (one poll interval plus
  blocking wait). Gateway regex intake: toxicity then hello (static SMTP, no
  Dify). No gateway MCP, no escalate-in-gateway, no size/rate gate.
- **Verification gate:** GreenMail tests against **fake Dify** for those
  behaviors (normalization, attachments ignored, mask-before-Dify, blocking
  contract, SMTP, `\Seen`, restart, duplicate window). Merge-gate stays on
  the fake; local/opt-in may call live Dify echo.
- **Learning checkpoint:** distinguish mailbox processing hints (`\Seen`) from
  receiver-visible email delivery guarantees and at-least-once internal
  ticket/message effects.

## Phase 5 — Author the email Workflow

- **Owner:** bounded Dify-workflow agent.
- **Scope:** author `email_helpdesk` in the UI: `list-my-tickets` branch,
  KB/MCP paths, End contract (`reply_text` / `ticket_id` / `citations`).
  Re-export secret-free DSL. Same gateway tests against fake + no-model/live
  slice. Malformed/failure → static acknowledgement, no fail-open (gateway
  sends it). Not live Yandex verification.
- **Verification gate:** gateway contract tests pass against fake and a
  no-model Dify slice; malformed output and workflow failure yield a static
  acknowledgement; no Yandex-specific response shape leaks through the
  interface.
- **Learning checkpoint:** show how the small blocking HTTP contract permits
  replacement of Studio internals while Dify still orchestrates the graph.

## Phase 6 — Knowledge and evaluation

- **Owner:** a separate bounded knowledge/evaluation agent, only after the
  contracts and source metadata rules are fixed.
- **Scope:** create about eight synthetic English Markdown documents (within
  the required 5–10) and golden retrieval cases, ingest one
  `employee-helpdesk` knowledge base, and preserve stable trusted repository
  source IDs/URLs to `knowledge_base/` paths. Eval suite folder layout is
  chosen in this phase. Record `candidate_k=10` / `rerank_top_k=3` / `0.7`.
  Bi-encoder measurement with local `granite-embedding:30m`. Yandex
  LLM-as-reranker may still be TBD / Phase 7. No sensitive data. This agent
  does not change application architecture.
- **Verification gate:** reproducible re-ingestion and measured bi-encoder
  retrieval meet the golden cases; recorded k/threshold values; no Cohere/Jina
  rerank slot; no sensitive data.
- **Learning checkpoint:** explain why Git is canonical, Weaviate is derived,
  and retrieval quality is measured rather than assumed.

## Phase 7 — Controlled intelligence

- **Owner:** bounded Yandex/RAG integration agent.
- **Scope:** injection/scope, Yandex generator, evidence gating per the
  ticket/KB table, LLM-rerank TBD, grounded citations, token accounting.
  Toxicity stays a Dify node (not gateway).
- **Verification gate:** merge-gate uses fake Dify and local dependencies.
  Live Yandex classifier/generator, usage matching, and full Dify/Yandex
  behavior are opt-in smoke/evaluation checks.
- **Learning checkpoint:** identify where nondeterministic model behavior is
  constrained by deterministic gates, types, thresholds, and tools.

## Phase 8 — Lifecycle and recovery

- **Owner:** bounded lifecycle/verification agent, with final coordinating
  review.
- **Scope:** second Dify app (Schedule Trigger, daily / 24h) that **only**
  HTTP-calls existing `POST /v1/tickets/escalate-stale`; plus negatives,
  restore/re-ingestion, security checks, and GreenMail acceptance with
  local/fake model behavior. Escalate-stale already exists from Phase 3.
  Dify does not own escalate rules.
- **Verification gate:** every acceptance criterion in
  [requirements.md](requirements.md) has the required evidence: deterministic
  criteria run locally, while live-model criteria run opt-in and are reported
  separately rather than inferred from fakes.
- **Learning checkpoint:** present the end-to-end trust story, failure
  semantics, recovery procedure, remaining limitations, and tutor evidence.
