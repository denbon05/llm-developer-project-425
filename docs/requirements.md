# v1 Requirements

This document defines observable v1 behavior. Domain terms are defined in
[CONTEXT.md](../CONTEXT.md); module placement and interfaces are defined in
[architecture.md](architecture.md).

## Functional requirements

- **FR-1 — Email channel.** GreenMail is mandatory for the initial integration
  and deterministic end-to-end tests. The gateway must poll generic IMAP and
  send through generic SMTP. It processes plain text and sanitized HTML in
  English and ignores attachment contents. The default poll interval is one
  minute; it is configurable and may be shortened in tests.
- **FR-2 — Safe intake.** Input-size and per-sender rate limits apply before
  model calls. After normalization and those limits, and before any Dify or
  model call, the gateway applies a configured toxicity/abuse word-list
  (regex). A match sends a static reply, creates no ticket, and skips Dify.
  Injection patterns and the helpdesk-scope classifier remain separate Dify
  concerns. v1 has no sender or domain allowlist.
- **FR-3 — Controlled routing.** After normalization, limits, the toxicity
  gate, and PII masking, each request that reaches Dify follows this order:
  1. An injection/scope gate distinguishes `injection`, `non_helpdesk`, and
     legitimate help-desk content.
  2. Injection receives a static response and never creates a ticket.
     Non-helpdesk content receives a bounded refusal and never creates a
     ticket. A classifier outage quarantines the request and produces a
     deferred acknowledgement rather than failing open.
  3. A legitimate follow-up to `open` or `escalated` appends once to that
     ticket and acknowledges it without RAG or another ticket. A follow-up to
     `answered` also transitions it to `open`. A reply to `closed` creates a
     new independent ticket.
  4. Only when no existing-ticket path applies may a list/status intent return
     the employee's scoped tickets. Otherwise Dify retrieval applies the
     evidence threshold. Sufficient evidence produces a grounded answer and
     does **not** create a ticket, even when the employee explicitly asked for
     one. Insufficient evidence automatically creates a ticket.
  5. A legitimate request without a specific category uses `other`.
- **FR-4 — Knowledge and citations.** v1 uses one Dify knowledge base with
  High-Quality hybrid retrieval, local `granite-embedding:30m` through an
  internal resource-limited Ollama container, persistent bundled Weaviate, and
  no reranker initially. Its corpus contains 5–10 concise synthetic English
  documents; the planning target is about eight, delegated after contracts are
  fixed. Canonical knowledge is versioned in Git. Citation labels and URLs
  come from trusted repository metadata, never from model-generated URLs.
- **FR-5 — Ticket ownership and interfaces.** The ticketing module owns durable
  ticket, message, conversation-correlation, idempotency, escalation, and
  outbound-delivery state. It exposes private REST operations to the gateway
  and only narrow capability-scoped MCP tools to Dify; the model cannot supply
  an arbitrary employee identity. Its PostgreSQL is separate from Dify's
  PostgreSQL.
- **FR-6 — Ticket model.** Actors are `employee`, `assistant`, `operator`, and
  `system`; categories are `bug`, `access`, `docs`, `feature`, and `other`;
  states are `open`, `escalated`, `answered`, and `closed`.
- **FR-7 — Ticket lifecycle.** A new ticket starts `open`. Configured operator
  inactivity changes it to `escalated`. For v1 demos and tests, an
  authenticated manual MCP operation records an operator response and changes
  an active ticket to `answered`. An employee reply to `answered` reopens it to
  `open`. Without an employee reply, `answered` auto-closes after a configurable
  interval whose default is 24 hours. A reply to a closed thread creates a new
  independent ticket in v1. A separate daily scheduled Dify workflow queries
  eligible stale tickets, requests escalation and auto-close transitions, and
  sends an idempotent deterministic operator digest/reminder through the
  gateway without an LLM. Reminders repeat on the configured interval while a
  ticket remains `escalated`.
- **FR-8 — Delivery semantics.** A stable inbound idempotency key must make
  internal effects exactly-once across polling retries and restarts. Outbound
  SMTP is at-least-once: a crash after SMTP acceptance but before durable
  acknowledgement may cause a duplicate within a documented retry window.
- **FR-9 — Dify lifecycle.** Dify Apps are authored node-by-node in the UI,
  then exported as secret-free DSL under `dify/apps/` (one export per Studio
  App). v1 plans two Workflow-type Apps: the gateway-facing email helpdesk
  workflow and the scheduled ticket lifecycle workflow. The first slice of each
  is not generated from handwritten YAML. Dify remains replaceable behind the
  versioned workflow interface, and provider-specific response shapes must not
  leak into callers.
- **FR-10 — Deployment and recovery.** Run two pinned Compose projects on a
  private shared network: `dify/compose.yml` (Dify platform) and root
  `compose.yml` (application stack), wrapped by Make targets such as
  `make dify-stack-up`. Use persistent volumes and reproducible migrations,
  restore procedures, and knowledge re-ingestion. Automation is limited to
  clear Compose, Make, and documentation entry points rather than Ansible.
  Document the one-time Dify administrator and Yandex-provider setup that
  cannot be automated safely.
- **FR-11 — Interface clarity.** Public interfaces must use clear domain names,
  explicit types, and versioned contracts. Later comments and docstrings
  explain non-obvious reasons, not restate code.

## Security and privacy constraints

- **SEC-1 — Data policy.** v1 is English-only and uses synthetic,
  non-sensitive data, but applies production-like privacy controls.
- **SEC-2 — PII minimization.** Deterministic masking runs before content is
  sent to Dify and independently before content enters durable business
  fields. Required detection covers email addresses, phone-like values, and
  payment-card candidates that pass a Luhn check. GreenMail necessarily retains
  raw synthetic transport messages and is outside this application-business
  persistence invariant.
- **SEC-3 — Employee scope.** The gateway/ticketing REST seam derives an
  opaque, unguessable conversation/employee capability from normalized mail
  identity. Dify tools receive it outside model-controlled arguments, and the
  ticketing module derives scope from it; the model never supplies `user_id`.
  This is not an allowlist. GreenMail sender identity is suitable only for
  synthetic tests, not production identity authentication.
- **SEC-4 — Delivery identity.** Short-lived outbound recipient data is
  encrypted at rest and removed when no longer needed. Ticket history,
  correlation, metrics, and other durable uses retain only masked or HMAC-based
  identity. This encrypted recipient is the sole raw-PII exception in
  application-controlled business persistence.
- **SEC-5 — Logs and errors.** Application JSON logs and error payloads contain
  no raw message, subject, recipient, retrieved passage, or other raw content.
  They may contain bounded metadata, opaque correlation identifiers, and
  masked values.
- **SEC-6 — Trust.** Employee input, email headers and HTML, retrieved text, and
  model output are untrusted data. Governing instructions, interface schemas,
  authorized tool definitions, and repository-controlled citation mappings
  are trusted. Untrusted text must not be promoted into a trusted instruction
  context.
- **SEC-7 — Access and secrets.** Runtime interfaces remain on a private
  LAN/VPN and the shared container network. MCP operator actions require
  authentication. Secrets stay out of Git and exported Dify DSL.
- **SEC-8 — External models.** Yandex is the only external model processor
  receiving application content in v1. Embedding is local; configuration and
  acceptance checks reject watsonx and every other external model provider.

## Observability constraints

- The gateway consumes Dify Workflow SSE and records `workflow_run_id`,
  end-to-end latency, and the answer-generator node's input and output token
  usage.
- Message records retain the tutor-shaped `model`, `tokens_in`, `tokens_out`,
  and `latency_ms` fields where applicable. There is no separate
  `model_calls` table.
- Persisted token counts must match the corresponding Dify answer-generator
  usage within 10%.
- Logs must make correlation, routing outcome, retries, idempotency decisions,
  ticket transitions, and delivery outcome diagnosable without raw content.

## Acceptance criteria

1. A supported GreenMail question produces a grounded English email with a
   clickable trusted repository citation and no ticket.
2. When no existing-ticket path applies and knowledge evidence is sufficient, a
   legitimate request produces a grounded cited answer and no ticket — including
   when the employee explicitly asked for a ticket.
3. A legitimate request below the evidence threshold automatically creates
   exactly one ticket; an uncategorized request is stored as `other`.
4. Toxicity/abuse word-list matches at the gateway produce a static reply with
   no Dify call and no ticket. Injection, non-helpdesk input, and classifier
   outage respectively produce a static block, a bounded refusal, and a
   quarantined deferred acknowledgement; none creates a ticket.
5. A legitimate follow-up appends exactly once: `open`/`escalated` stays on the
   same ticket without RAG, `answered` reopens, and `closed` creates a new
   independent ticket. Before sending a ticket confirmation, REST
   reconciliation verifies the ticket/message effects under the current
   capability/idempotency context.
6. `list-my-tickets` returns only tickets in the current capability's scope,
   and an arbitrary model-supplied employee identity is rejected.
7. Lifecycle tests prove repeated escalation, authenticated operator response,
   reopen, 24-hour default auto-close, and the daily idempotent no-LLM operator
   digest/reminder.
8. Privacy tests show required PII absent from Dify-bound content,
   application-controlled business fields, and application logs/errors. The
   only business-store exception is the encrypted short-lived recipient;
   GreenMail's raw synthetic transport messages are explicitly outside the
   invariant.
9. Retry tests prove exactly-once inbound business effects and demonstrate the
   documented at-least-once SMTP duplicate window.
10. Contract tests preserve `workflow_run_id` and fake SSE usage correctly;
    opt-in live checks compare stored token counts with Dify answer-generator
    usage within 10%.
11. Malicious instructions in retrieved knowledge cannot change routing, tool
    authorization, or repository-controlled citation URLs.
12. Restart and restore checks preserve ticket/idempotency/outbox state; deleting
   the vector index and re-ingesting canonical Git documents restores
   retrieval.
13. Deterministic merge-gate CI uses fake Dify contract behavior, local
    GreenMail/PostgreSQL/retrieval, static DSL/provider/contract checks that
    reject non-Yandex external models, and any no-model Dify slice. Real Yandex
    classifier/generator routes and full live
    Dify/Yandex behavior are opt-in smoke/evaluation checks; fake tests do not
    verify them.
14. Committed Dify App exports under `dify/apps/` contain no secrets and are
    demonstrably derived after the UI-authored workflow slices.
15. Submission evidence for the course substitute stack is a Dify workflow run
    and SSE usage record, ticket state observed through private interfaces
    (plus the permitted direct privacy audit), and a deterministic GreenMail
    end-to-end transcript — not YDB or Yandex-managed application runtimes.

## Exclusions and deferred scope

- watsonx and all non-Yandex external model APIs; provider comparison,
  runtime switching, and failover
- Yandex-managed agent/workflow/database runtime services beyond use of the
  Yandex foundation-model endpoint
- a real or public mailbox, real-mail sender assurance/authentication, public
  ingress, and sender/domain allowlists
- attachment processing, multilingual behavior, and real or sensitive data
- broader NLP-based PII discovery beyond the required deterministic types
- a dedicated operator UI or CLI; v1 uses authenticated manual MCP operations
- linked historical tickets after a closed-thread reply
- reranking, external tracing platforms, and business-calendar escalation
- receiver-visible exactly-once email delivery
- Ansible or other infrastructure orchestration beyond minimal Compose/Make

## Provisional parameters

Exact input-size/rate values, the toxicity word-list contents, retrieval Top K
and evidence threshold, and escalation/reminder intervals will be calibrated at
their phase gates. Until then, the required outcomes above are normative:
inadequate evidence creates a ticket, sufficient evidence answers without a
ticket, toxicity matches skip Dify with a static reply, limits remain enabled,
and escalation repeats on configured intervals.
