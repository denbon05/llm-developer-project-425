# v1 Requirements

This document defines observable v1 behavior. Domain terms are defined in
[CONTEXT.md](../CONTEXT.md); module placement and interfaces are defined in
[architecture.md](architecture.md).

## Scope / boundaries

v1 is the LLM email path: Dify answers from company knowledge or opens a
ticket when it cannot. A knowledge hit is emailed with a citation; no ticket
and no `messages` row. Knowledge gap or an explicit ticket request uses
`create-ticket`; further dialogue uses `append-message` on that ticket.
`open` tickets whose `updated_at` is older than the inactivity threshold
(default 24h / `escalation_seconds`) become `escalated`. This slice ends
there; after escalate is out of scope and not modeled. `answered` and
`closed` stay in the schema unused.

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
     ticket. A classifier outage produces a static acknowledgement rather
     than failing open (gateway-local; no quarantine table).
  3. A list/status intent may return the employee's scoped tickets
     (`list-my-tickets`). Otherwise Dify retrieval applies the evidence
     threshold.
  4. A knowledge hit produces a grounded cited reply by email only. No
     ticket. No `messages` row. Chat exists only in mail.
  5. A knowledge gap or an explicit ticket request uses `create-ticket` when
     this `user_id` has no non-`closed` ticket (`text` → `tickets.text`).
     The call returns the ticket id. Dialogue history is `append-message` on that ticket (required
     `ticket_id`, `user_id`, `text`, `role`). The ticket must exist and
     `ticket.user_id` must match `user_id` or the call is `NOT_FOUND`.
     Append inserts a message and bumps `tickets.updated_at` (activity);
     it does not change ticket text or status. Agent rows may include usage.
  6. A legitimate request without a specific category uses `other`.
- **FR-4 — Knowledge and citations.** v1 uses one Dify knowledge base with
  High-Quality hybrid retrieval, local `granite-embedding:30m` through an
  internal resource-limited Ollama container, persistent bundled Weaviate, and
  no reranker initially. Its corpus contains 5–10 concise synthetic English
  documents; the planning target is about eight, delegated after contracts are
  fixed. Canonical knowledge is versioned in Git. Citation labels and URLs
  come from trusted repository metadata, never from model-generated URLs.
- **FR-5 — Ticket ownership and interfaces.** The ticketing module owns durable
  tickets, messages, and escalation validity. MCP tools are
  `create-ticket`, `list-my-tickets`, `append-message`; `user_id` (sender
  email) is a tool argument, not an HTTP header. Private HTTP is scheduled
  `POST /v1/tickets/escalate-stale` (private network, no shared secret), not a
  resource REST API. v1 persists a minimal schema (`tickets` and `messages`)
  in application PostgreSQL (`helpdesk-db`), separate from Dify's PostgreSQL.
  SMTP send/receive stays in the email gateway; v1 does not use an application
  outbox table.
- **FR-6 — Ticket model.** Message roles, categories, statuses, and domain error
  codes are the `contracts.enums` StrEnums (`MessageRole`, `TicketCategory`,
  `TicketStatus`, `DomainErrorCode`); see that module for values. Roles are
  `user` | `agent` only. Each ticket stores `user_id` as the synthetic sender
  email (course MVP) and masked ticket text in `tickets.text` (set at
  create, not updated later). A message always belongs to a ticket
  (`ticket_id` required FK). Tutor-shaped `model`
  / `tokens_in` / `tokens_out` / `latency_ms` land on agent messages at
  `append-message` time. Persistence uses VARCHAR for enum fields (ORM enums,
  not Postgres ENUM types); see architecture MVP schema.
- **FR-7 — Ticket lifecycle.** A new ticket starts `open`. Escalation is
  inactivity on `updated_at`, not calendar time from create that ignores
  chat. Scheduled HTTP selects `status=open` with `updated_at` older than
  a threshold (`older_than_seconds`, default `Settings.escalation_seconds`
  / 86400) and sets `escalated` (status-only; no lifecycle messages).
  Ongoing dialogue delays escalate. `answered` and `closed` remain in
  the enum/schema; the LLM path does not write them. Tests or another
  system may poke those statuses. `append-message` inserts a message and
  bumps `tickets.updated_at`; it does not change ticket text or status.
- **FR-8 — Delivery semantics.** Ticket/message effects are best-effort and
  at-least-once. The gateway may mark an inbound message processed
  (for example IMAP `\Seen`) after successful handling; poll retries may
  repeat mutations. Outbound SMTP is gateway-owned and at-least-once: a crash
  around send may duplicate the email within a documented retry window.
- **FR-9 — Dify lifecycle.** Dify Apps are authored node-by-node in the UI,
  then exported as secret-free DSL under `dify/apps/` (one export per Studio
  App). v1 plans the gateway-facing email helpdesk Workflow App. Escalation is
  scheduled HTTP, not a required Dify lifecycle App. The first slice is not
  generated from handwritten YAML. Dify remains replaceable behind the
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
- **SEC-2 — PII minimization.** Deterministic **one-way** masking runs before
  content is sent to Dify and independently before ticket/message **text**
  enters durable business fields. Masking replaces matches with placeholders
  (for example `[EMAIL]`, `[PHONE]`, `[CARD]`); it is not reversible
  encrypt/decrypt. Required detection covers email addresses, phone-like
  values, and payment-card candidates that pass a Luhn check. GreenMail
  necessarily retains raw synthetic transport messages and is outside this
  text-masking invariant.
- **SEC-3 — Employee scope.** `user_id` is the synthetic sender email (MVP).
  MCP tools take that value as a tool argument (JSON body), not an
  `x-user-id` header. Ticketing scopes each call to the `user_id` on that
  call (list/create/append cannot touch another employee's ticket ids). This
  is not an allowlist and is not production identity authentication; a caller
  who can invoke MCP can pass any synthetic email.
- **SEC-4 — Delivery identity.** The email gateway keeps the live SMTP/IMAP
  recipient from the current mail session when sending replies. v1 does not
  persist an encrypted outbox recipient table. The sole intentional raw-PII
  exception in application-controlled business persistence is MVP
  `tickets.user_id` (synthetic sender email). Ticket/message **text** and logs
  remain masked.
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
  LAN/VPN and the shared container network. MCP tools take `user_id` as a
  tool argument. Secrets stay out of Git and exported
  Dify DSL.
- **SEC-8 — External models.** Yandex is the only external model processor
  receiving application content in v1. Embedding is local; configuration and
  acceptance checks reject watsonx and every other external model provider.

## Observability constraints

- The gateway consumes Dify Workflow SSE and records `workflow_run_id`,
  end-to-end latency, and the answer-generator node's input and output token
  usage.
- Agent message records retain the tutor-shaped `model`, `tokens_in`,
  `tokens_out`, and `latency_ms` fields set at `append-message` time. There
  is no separate `model_calls` table or `record-usage` HTTP route.
- Persisted token counts must match the corresponding Dify answer-generator
  usage within 10%.
- Logs must make correlation, routing outcome, retries, ticket transitions, and
  delivery outcome diagnosable without raw content.

## Acceptance criteria

1. A supported GreenMail question produces a grounded English email with a
   clickable trusted repository citation. No ticket is created and no
   `messages` row is written. When a ticket is created, `text` is stored
   masked in `tickets.text` (immutable after create). Chat lines are
   `append-message` on that ticket.
2. When no existing-ticket path applies and knowledge evidence is sufficient,
   a legitimate request produces a grounded cited email as above — emailed
   only, with no MCP message ids.
3. A legitimate request below the evidence threshold automatically creates
   exactly one ticket; an uncategorized request is stored as `other`.
4. Toxicity/abuse word-list matches at the gateway produce a static reply with
   no Dify call and no ticket. Injection, non-helpdesk input, and classifier
   outage respectively produce a static block, a bounded refusal, and a
   static acknowledgement; none creates a ticket.
5. `append-message` requires `ticket_id`, `user_id`, `text`, and `role`. The
   ticket must exist and match `user_id`; otherwise the write is `NOT_FOUND`.
   Invented ticket ids and ticket ids owned by a different `user_id` are
   rejected. `create-ticket` stores `text` in `tickets.text` only. A new
   ticket is created only when this
   `user_id` has no non-`closed` ticket. Append inserts a message and bumps
   `tickets.updated_at` (activity); it does not rewrite `tickets.text` or
   change ticket status.
6. `list-my-tickets` returns only tickets for the `user_id` tool argument.
   Course MVP: that argument is model-visible; ticketing scopes to it rather
   than rejecting a caller-supplied identity.
7. Escalation tests prove scheduled HTTP `POST /v1/tickets/escalate-stale`
   moves `open` tickets with stale `updated_at` to `escalated` without
   inserting messages. An append that refreshes `updated_at` keeps that
   ticket `open` while a similarly aged idle ticket escalates.
8. Privacy tests show required PII absent from Dify-bound content, durable
   ticket/message **text**, and application logs/errors. The documented
   business-store exception is MVP `tickets.user_id` (synthetic sender
   email); GreenMail's raw synthetic transport messages are explicitly
   outside the text-masking invariant.
9. Gateway retry handling uses mailbox hints (for example `\Seen` after success)
   and best-effort semantics; tests demonstrate the documented at-least-once
   SMTP duplicate window.
10. Contract tests preserve `workflow_run_id` and fake SSE usage correctly;
    opt-in live checks compare stored token counts with Dify answer-generator
    usage within 10%.
11. Malicious instructions in retrieved knowledge cannot change routing, tool
    authorization, or repository-controlled citation URLs.
12. Restart and restore checks preserve ticket/message data; deleting the
   vector index and re-ingesting canonical Git documents restores retrieval.
13. Deterministic merge-gate CI uses fake Dify contract behavior, local
    GreenMail/PostgreSQL/retrieval, static DSL/provider/contract checks that
    reject non-Yandex external models, and any no-model Dify slice. Real Yandex
    classifier/generator routes and full live
    Dify/Yandex behavior are opt-in smoke/evaluation checks; fake tests do not
    verify them.
14. Committed Dify App exports under `dify/apps/` contain no secrets and are
    demonstrably derived after the UI-authored workflow slices.
15. Submission evidence for the course substitute stack is a Dify workflow run
    and SSE usage record, ticket status observed through private interfaces
    (plus the permitted direct privacy audit), and a deterministic GreenMail
    end-to-end transcript — not YDB or Yandex-managed application runtimes.

## Exclusions

- operator UI, modeled human replies, and auto-close (after `escalated` is
  out of scope / not modeled)
- watsonx and all non-Yandex external model APIs; provider comparison,
  runtime switching, and failover
- Yandex-managed agent/workflow/database runtime services beyond use of the
  Yandex foundation-model endpoint
- a real or public mailbox, real-mail sender assurance/authentication, public
  ingress, and sender/domain allowlists
- attachment processing, multilingual behavior, and real or sensitive data
- broader NLP-based PII discovery beyond the required deterministic types
- linked historical tickets after a closed-thread reply
- reranking, external tracing platforms, and business-calendar escalation
- Ansible or other infrastructure orchestration beyond minimal Compose/Make

## Provisional parameters

Exact input-size/rate values, the toxicity word-list contents, retrieval Top K
and evidence threshold, and escalation intervals will be calibrated at
their phase gates. Until then, the required outcomes above are normative:
inadequate evidence creates a ticket when none is active, a grounded cited
email is sent with no ticket and no `messages` row, toxicity matches skip
Dify with a static reply, limits remain enabled, and `open` tickets
inactive on `updated_at` escalate over HTTP.
