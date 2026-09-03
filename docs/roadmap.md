# Delivery Roadmap

Work proceeds as bounded vertical phases. One focused agent owns each phase; a
coordinating agent reviews its evidence against the same glossary,
requirements, and architecture before the next phase starts. No implementation
agent owns the whole system. Each phase updates affected documentation and
ends with a verification gate and a short learning checkpoint.

Phases 1–8 are historical (done). `list-my-tickets` already matches the
Studio-binding contract (`text`, optional `statuses`).

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
- **Verification gate:** contract tests at HTTP and MCP seams cover categories,
  user/agent roles, scoped list, create (`text` only),
  append for chat history, agent append with usage on a ticket (bumps `updated_at`, not
  ticket text or status), masking, and HTTP escalate-stale (`open` tickets
  older than the threshold on `created_at`).
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
- **Scope:** author `email_helpdesk` in the UI as the graph in
  [architecture.md](architecture.md) (early `list-my-tickets` tool node
  bound to live ticketing, retrieve then answer LLM, non-closed vs KB-hit
  vs knowledge-gap branches, sequential appends, categorizer only on the
  gap path, End `reply_text` / `ticket_id` / `source_filenames`). Re-export
  secret-free no-model DSL (Code/Template stubs). Same gateway tests
  against fake Dify. Malformed/failure → error log, no SMTP, leave UNSEEN
  (retry next poll). Not live Yandex.
- **Verification gate:** done. Committed `dify/apps/email_helpdesk.yml` is
  the architecture topology with no-model Code/Template stubs (not an
  echo). Merge-gate stays **fake Dify**. Malformed/failure skip SMTP and
  leave UNSEEN. Live check: mail client as `employee1@example.test` **To:**
  `support@example.test`; gateway polled; employee received the stub Dify
  reply. Studio Preview: first mail creates ticket + two messages; second
  mail same sender appends (no create CONFLICT). Phase 6 Knowledge
  Retrieval; Phase 7 live Yandex.
- **Learning checkpoint:** show how the small blocking HTTP contract permits
  replacement of Studio internals while Dify still orchestrates the graph.

## Phase 6 — Knowledge and evaluation

- **Owner:** a separate bounded knowledge/evaluation agent, only after the
  contracts and source metadata rules are fixed.
- **Scope:** create about eight synthetic English Markdown documents (within
  the required 5–10) and golden retrieval cases, ingest one
  `employee-helpdesk` knowledge base, and preserve stable trusted repository
  source IDs/URLs to `knowledge_base/` paths. Eval suite folder layout is
  chosen in this phase. Record search settings in the eval catalog.
  Measurement with local Ollama embeddings and Knowledge Retrieval
  Weighted Score. No sensitive data. This agent does not change
  application architecture.
- **Verification gate:** done. Eight synthetic English pages in
  `knowledge_base/`; Dify dataset `employee-helpdesk`; golden catalog and
  opt-in scorer in `tests/eval/`. `make test` checks the catalog and
  exported Knowledge Retrieval settings (no Dify); `make eval` measures
  retrieval against live Dify/Weaviate/Ollama and requires each expected
  document to rank first. No sensitive data. Phase 7 is live Yandex.
- **Learning checkpoint:** explain why Git is canonical, Weaviate is derived,
  and retrieval quality is measured rather than assumed.

## Phase 7 — Controlled intelligence

- **Owner:** bounded Yandex/RAG integration agent.
- **Scope:** cheap gateway regex for obvious injection/SQL phrases (before
  Dify) plus intent SML (`safe` | `injection` | `off-topic`; injection and
  off-topic skip KR/generator and all MCP and do not create or append
  tickets; they may share one static Template `reply_text`);
  knowledge-gap reply admits the miss, creates a ticket, SMTP includes the
  new `ticket_id`; no read-back of `messages`; SEC-2 mask format; live
  Yandex generator; categorizer SML; grounded citations; token
  accounting; gateway threading/context (SMTP ``In-Reply-To`` /
  ``References``; split latest ``request_text`` from quoted ``blockquote``
  before Dify). Toxicity/hello remain gateway regex (Phase 4).
- **Verification gate:** done. `email_helpdesk` uses live Yandex on the
  answer LLM and classifiers (intent SML then ticket/KB graph; categorizer
  SML on the gap path). Gateway regex is toxicity, then cheap
  injection/SQL phrases, then hello; residual injection/off-topic stay in
  Dify and may share one Template. SMTP skips `Sources:` when
  `reply_text` contains the knowledge-gap marker. Merge-gate stays
  **fake Dify**; live Yandex is opt-in smoke.
- **Learning checkpoint:** identify where nondeterministic model behavior is
  constrained by deterministic gates, types, thresholds, and tools.

## Phase 8 — Lifecycle and recovery

- **Owner:** bounded lifecycle/verification agent, with final coordinating
  review.
- **Scope:** second Dify app (Schedule Trigger) that **only** HTTP-calls
  existing `POST /v1/tickets/escalate-stale` with an HTTP retry policy;
  plus negatives (including injection), restore/re-ingestion, security
  checks, and GreenMail with local/fake model behavior. Escalate-stale
  already exists from Phase 3 (cutoff is `created_at` while `open`).
  Dify does not own escalate rules.
- **Verification gate:** done. Committed `dify/apps/escalate_stale.yml` is
  Schedule Trigger (every minute) → HTTP POST `/v1/tickets/escalate-stale`
  with retry (3 × 100ms). App env `ESCALATION_SECONDS=30` is passed as
  `older_than_seconds`; cutoff rules stay in ticketing. Merge-gate stays
  **fake Dify**. Live GreenMail, live Yandex, and `make eval` remain
  opt-in (no separate submission pack). Restore/re-ingest is the
  documented Studio/Git procedure in [setup.md](setup.md).
- **Learning checkpoint:** escalate is status-only HTTP from a second app;
  Dify does not decide who is stale. Gateway Dify failure stays no-SMTP /
  UNSEEN. Git is canonical knowledge; Weaviate is rebuilt from
  `knowledge_base/`. Remaining limits: no operator path; local schedule is
  every minute / 30s; live models stay opt-in.
