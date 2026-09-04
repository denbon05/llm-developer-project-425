# v1 Requirements

This document defines observable v1 behavior. Domain terms are defined in
[CONTEXT.md](../CONTEXT.md); module placement and interfaces are defined in
[architecture.md](architecture.md).

## Scope / boundaries

v1 is the LLM email path. Ticket/KB persistence follows FR-3. Escalate
follows FR-7. Escalation digest email is in v1 (FR-9); there is no
operator UI, inbound operator workflow, or modeled human replies.
`answered` and `closed` stay in the schema unused by the LLM path. The
employee cannot force ticket creation when knowledge can answer and no
non-`closed` ticket exists.

## Functional requirements

- **FR-1 — Email channel.** GreenMail is mandatory for the initial
  integration and deterministic end-to-end tests. The gateway polls
  **generic IMAP** (not the GreenMail HTTP mail API, not a Dify schedule
  for IMAP) and sends through generic SMTP. It processes plain text and
  sanitized HTML in English and ignores attachment contents. The default
  poll interval is one minute; it is configurable and may be shortened in
  tests. Beside the IMAP loop, the gateway process exposes a **private
  HTTP listener**: `POST /v1/emails/send` at
  `http://email-gateway:8080/v1/emails/send`. JSON is `{subject,
  tickets}` — no `to` / recipient field. `subject` is required and
  trusted (Dify Template or constant). The gateway formats the operator
  mail from `tickets` (optional flat one-ticket fields `ticket_id`,
  `user_id`, `category`, `created_at`, `text`). Do not send an LLM
  `body`. Recipient is env
  `OPERATOR_EMAIL` (not a secret) and **must not** equal the IMAP intake
  mailbox (`IMAP_USER` / `support@example.test`); digest to the polled
  inbox would be treated as employee mail. Local GreenMail uses a distinct
  account `operator@example.test`. From/SMTP auth uses existing
  `SMTP_USER`. Invalid or missing digest (no `tickets`, no flat ticket
  fields): no SMTP, error to the caller.
  Digest SMTP is best-effort at-least-once (FR-8) and is **not** IMAP
  `\Seen` / employee-reply threading. SEC-4 “live mail-session recipient”
  applies to **employee replies only**; digest uses `OPERATOR_EMAIL`.
- **FR-2 — Safe intake.** Size and per-sender rate limits are deferred. After
  normalization and before any Dify call, the gateway applies one-way PII
  masking (`src/privacy`) so Studio logs never see raw PII. Ordered
  **gateway regex** (in `email_gateway.replies`) runs on the full masked
  subject+body before the `request_text`/`blockquote` split: toxicity,
  then cheap injection/SQL phrases, then hello. A match is a static SMTP
  body, no Dify, no KB, no MCP, no ticket. Cheap phrases include “ignore
  previous instruction”, “ignore previous instructions”, and DROP TABLE
  (case-insensitive). A hello match must be the whole remaining text so a
  real question still reaches Dify. Residual/subtle cases use Dify intent
  SML (`safe` | `injection` | `off-topic`) in FR-3. v1 has no sender or
  domain allowlist.
- **FR-3 — Controlled routing.** After normalization and masking, the
  gateway POSTs a blocking Dify run (Start fields `user_email`, `subject`,
  `request_text` = already-masked latest question, `blockquote` =
  already-masked quoted thread or `""`) unless gateway intake already
  replied. The gateway does **not** call MCP. Dify first classifies Start
  `request_text` as `safe`, `injection`, or `off-topic`. `injection` and
  `off-topic` skip KR, the answer LLM, and all MCP (no create, no append —
  including no append on an existing ticket). They may share one static
  Template `reply_text`. That body SMTP when the workflow finishes. A
  gateway Dify HTTP or outputs failure is not fail-open: log the error,
  skip SMTP, leave the message UNSEEN, retry on the next poll. None of
  those paths create a ticket from the gateway. `safe` then calls
  `list-my-tickets` and follows this table (employee **cannot** override):

  | State | KB can answer | DB |
  | --- | --- | --- |
  | No non-`closed` ticket | yes | **no** ticket, **no** `messages` — email only + citations |
  | No non-`closed` ticket | no | `create-ticket` (`tickets.text` only) **and** `append-message` user (inbound mail) **then** `append-message` agent (reply). |
  | Non-`closed` ticket already exists (`open` **or** `escalated`) | yes or no | **always** append user + agent; **still run KB** |

  On a knowledge gap (row 2), `reply_text` admits the miss; End
  `ticket_id` is set; SMTP includes that id (gateway `Ticket:` line). After
  a non-`closed` ticket exists, persist messages even if KB could answer;
  End still emits `ticket_id` and SMTP includes `Ticket:`. End `ticket_id`
  is empty or omitted on a KB hit with no ticket (no `Ticket:` line). The
  **workflow** adds the first user mail via `append-message` after
  `create-ticket`. On the knowledge-gap path the categorizer runs
  sequentially (after the answer LLM, before `create-ticket`) and emits
  one `TicketCategory`. Unknown category strings are `NOT_ELIGIBLE`. Skip
  the categorizer on KB-hit and follow-up paths.
- **FR-4 — Knowledge and citations.** v1 uses one Dify knowledge base
  (`employee-helpdesk`), persistent bundled Weaviate, and local embeddings
  through an internal resource-limited Ollama container. The email
  workflow Knowledge Retrieval node uses Weighted Score. Recorded search
  settings live in `tests/eval/golden_retrieval.json`. Corpus: eight
  concise synthetic English documents in `knowledge_base/`. Canonical
  knowledge is versioned in Git; Weaviate is derived and rebuildable. End
  `source_filenames` are `knowledge_base/` filenames from retrieval, never
  model-generated URLs. The gateway builds `{CITATION_URL_BASE}{filename}`
  and appends a `Sources:` footer to the SMTP body unless End `reply_text`
  contains the knowledge-gap marker (`I don't know`, the same string as
  the workflow IF/ELSE `value` / `LLM_KNOWLEDGE_GAP_REPLY`). That check is
  case-insensitive; the footer is skipped even if `source_filenames` is a
  non-empty list. It rejects names that are not a single filename. Empty,
  omitted, or null `source_filenames` still skip the footer.
- **FR-5 — Ticket ownership and interfaces.** The ticketing module owns
  durable tickets, messages, and escalation validity. MCP tools are
  `create-ticket`, `list-my-tickets`, `append-message`; `user_id` (sender
  email) is a tool argument, not an HTTP header. `create-ticket` stores
  masked `text` in `tickets.text` only (no `messages` row) and rejects if
  this `user_id` already has a non-`closed` ticket. `list-my-tickets`
  returns only tickets for that `user_id`, newest `updated_at` first, each
  with masked `tickets.text`. Optional `statuses` (list of status
  strings): omitted/`None` defaults to `open`, `escalated`, and `answered`
  (so list agrees with create’s non-closed invariant; `answered` is unused
  by the LLM writer path). Empty `statuses=[]` returns no rows. Unknown
  status strings are `NOT_ELIGIBLE`. `append-message` requires `ticket_id`,
  `user_id`, `text`, and `role`. The ticket must exist and
  `ticket.user_id` must match `user_id` or append is `NOT_FOUND` (invented
  ids and another employee’s ids included). Append inserts a message and
  bumps `tickets.updated_at`; it does not change ticket text or status.
  Agent rows may include usage. Return is `message_id` and `ticket_id`.
  Private HTTP is scheduled `POST /v1/tickets/escalate-stale` (private
  network, no shared secret), not a resource REST API. The JSON is
  `count` and `tickets`: the same rows just escalated, each with at
  least `ticket_id`, `user_id` (MVP synthetic sender email — same SEC-4
  exception as stored `tickets.user_id`; the operator needs who),
  `category`, `status` (now `escalated`), `text` (already masked; the
  same store humans read), and `created_at`. Empty run: `count` 0,
  empty `tickets`. Logs must not contain ticket text (SEC-5): log
  threshold, count, ids only. Ticket `text` in this HTTP response is
  required for the operator digest; it is not a log. Do not add a separate
  list-stale HTTP or MCP tool; one POST mutates and returns the payload.
  Dify calls both this route and gateway `POST /v1/emails/send`.
  The gateway does not call MCP and does not decide escalate. v1 persists
  a minimal schema (`tickets` and `messages`) in application PostgreSQL
  (`helpdesk-db`), separate from Dify's PostgreSQL. SMTP send/receive
  stays in the email gateway; v1 does not use an application outbox
  table. Only Dify calls MCP. The answer LLM does not invent `user_id` /
  `ticket_id`; workflow wiring supplies them.
- **FR-6 — Ticket model.** Message roles, categories, statuses, and domain
  error codes are the `contracts.enums` StrEnums (`MessageRole`,
  `TicketCategory`, `TicketStatus`, `DomainErrorCode`); see that module for
  values. Roles are `user` | `agent` only. Each ticket stores `user_id` as
  the synthetic sender email (course MVP) and masked ticket text in
  `tickets.text` (set at create, not updated later). A message always
  belongs to a ticket (`ticket_id` required FK). `model` / `tokens_in` /
  `tokens_out` / `latency_ms` land on agent messages at `append-message`
  time. Those rows are audit and token accounting, not agent memory (no
  list-messages tool). Persistence uses VARCHAR for enum fields (ORM
  enums, not Postgres ENUM types); see architecture MVP schema.
- **FR-7 — Ticket lifecycle.** A new ticket starts `open`. Escalation is
  calendar age from `created_at` while `status=open`, not inactivity on
  `updated_at`. Scheduled HTTP selects `status=open` with `created_at`
  older than a threshold (`older_than_seconds`, default
  `Settings.escalation_seconds` / 86400) and sets `escalated`
  (status-only; no lifecycle messages). The JSON returns those rows for
  the digest (FR-5); Dify must **not** encode age/cutoff IF/ELSE.
  Follow-up appends keep the ticket `open` but do not delay escalate.
  After `escalated`, later employee mail still follows the non-closed
  path in FR-3 (KB + answer + two appends); status stays `escalated`. No
  reopen. `answered` and `closed` remain in the enum/schema; the LLM path
  does not write them. Tests or another system may poke those statuses.
  Dify does not own escalate rules.
- **FR-8 — Delivery semantics.** Ticket/message effects are best-effort and
  at-least-once. The gateway may mark an inbound message processed (IMAP
  `\Seen`) after successful SMTP of an intake or workflow reply. A failed
  Dify call does not SMTP and does not set `\Seen`. Poll retries may
  repeat mutations. Outbound SMTP is gateway-owned and at-least-once: a
  crash after send but before `\Seen` can duplicate the email on the next
  poll. Documented SMTP duplicate window: **one poll interval** (default
  60s) **plus** the blocking Dify wait. Digest SMTP is also
  gateway-owned and at-least-once. Ticketing commit happens **before**
  digest send: if SMTP fails, tickets stay `escalated` and
  **will not** appear in a later digest (lost digest; no rollback; no
  spam loop). Dify retry on the gateway HTTP can duplicate the digest.
  Exactly-once is not claimed. Digest send is not IMAP `\Seen`. No
  outbox table.
- **FR-9 — Dify lifecycle.** Two Workflow-type Studio Apps:
  1. `email_helpdesk` — User Input start; gateway blocking Service API
     `POST …/v1/workflows/run`. Committed export
     `dify/apps/email_helpdesk.yml`.
  2. `escalate_stale` — Schedule Trigger. Committed export
     `dify/apps/escalate_stale.yml`. JSON may include
     `older_than_seconds` from the app env (`ESCALATION_SECONDS`). Graph:
     1. Schedule Trigger (every minute; `ESCALATION_SECONDS=30` as
        `older_than_seconds`; HTTP retry 3 × 100ms on the ticketing call).
     2. HTTP `POST /v1/tickets/escalate-stale`.
     3. Parse the ticketing JSON (`count`, `tickets`).
     4. IF `count` is 0 → End. No digest SMTP.
     5. HTTP POST `http://email-gateway:8080/v1/emails/send` with
        JSON `{subject, tickets}` from Parse body. No recipient. `subject`
        is trusted (Dify Template or constant). The gateway formats the
        mail; this app has no digest LLM.
     No escalate logic in Dify (no age IF/ELSE). User Input vs Trigger
     are different start types; keep two apps. Local cadence and HTTP
     retry: Recorded parameters.
  Apps are authored in the UI, then exported as secret-free DSL under
  `dify/apps/` (one export per Studio App). The gateway depends on this
  small HTTP contract, not Studio internals (console session URLs).
  Provider-specific response shapes must not leak into callers.
- **FR-10 — Deployment and recovery.** Run two pinned Compose projects on a
  private shared network: `dify/compose.yml` (Dify platform) and root
  `compose.yml` (application stack), wrapped by Make targets such as
  `make dify-stack-up`. Start Dify first (it creates `helpdesk_private`).
  Use persistent volumes, reproducible migrations, and knowledge
  re-ingestion (see [setup.md](setup.md)). Restart preserves ticket/message
  data; deleting the vector index and re-ingesting canonical Git documents
  restores retrieval. Automation is limited to clear Compose, Make, and
  documentation entry points rather than Ansible. Document the one-time
  Dify administrator and Yandex-provider setup that cannot be automated
  safely.
- **FR-11 — Interface clarity.** Public interfaces must use clear domain
  names, explicit types, and versioned contracts. Later comments and
  docstrings explain non-obvious reasons, not restate code.

## Security and privacy constraints

- **SEC-1 — Data policy.** v1 is English-only and uses synthetic,
  non-sensitive data, but applies production-like privacy controls.
- **SEC-2 — PII minimization.** Deterministic **one-way** masking runs
  before content is sent to Dify and independently before ticket/message
  **text** enters durable business fields. Masking uses one visible format
  (the same in every store humans read): email → `[email]`; phone →
  `+** *** ** ** NN` (last two digits kept); card →
  `****-****-****-****`. It is not reversible encrypt/decrypt. Required
  detection covers email addresses, phone-like values, and payment-card
  candidates that pass a Luhn check. GreenMail necessarily retains raw
  synthetic transport messages and is outside this text-masking invariant.
- **SEC-3 — Employee scope.** `user_id` is the synthetic sender email (MVP).
  MCP tools take that value as a tool argument (JSON body), not an
  `x-user-id` header. Ticketing scopes each call to the `user_id` on that
  call (list/create/append cannot touch another employee's ticket ids).
  This is not an allowlist and is not production identity authentication;
  a caller who can invoke MCP can pass any synthetic email.
- **SEC-4 — Delivery identity.** The email gateway keeps the live SMTP/IMAP
  recipient from the current mail session when sending **employee
  replies**. Digest mail uses env `OPERATOR_EMAIL`, not a body recipient
  and not the live session. v1 does not persist an encrypted outbox
  recipient table. The sole intentional raw-PII exception in
  application-controlled business persistence is MVP `tickets.user_id`
  (synthetic sender email). Ticket/message **text** and logs remain
  masked.
- **SEC-5 — Logs and errors.** Application JSON logs and error payloads
  contain no raw message, subject, recipient, retrieved passage, digest
  body/subject/recipient, or other raw content. They may contain bounded
  metadata, opaque correlation identifiers, and masked values.
- **SEC-6 — Trust.** Employee input, email headers and HTML, retrieved text,
  model output, and ticket `text` in escalate-stale / digest payloads are
  untrusted data. Governing instructions, interface schemas, authorized
  tool definitions, repository-controlled citation mappings, digest
  `subject` (Template or constant), and `OPERATOR_EMAIL` are trusted.
  Untrusted text must not be promoted into a trusted instruction context.
  Malicious instructions in retrieved knowledge cannot change routing,
  tool authorization, or repository-controlled citation filenames.
- **SEC-7 — Access and secrets.** Runtime interfaces remain on a private
  LAN/VPN and the shared container network. MCP tools take `user_id` as a
  tool argument. Secrets stay out of Git and exported Dify DSL. The
  workflow app key lives in gitignored `.env`
  (`DIFY_EMAIL_HELPDESK_API_KEY`).
- **SEC-8 — External models.** This slice uses **Yandex Cloud AI Studio**
  as the external generator; embedding stays local Ollama.

## Observability

- The gateway uses the **blocking** Service API JSON (`data.outputs` and
  any `workflow_run_id` / usage metadata on that response). SSE is
  optional.
- Agent message records retain `model`, `tokens_in`, `tokens_out`, and
  `latency_ms` fields set at `append-message` time (audit and tokens; not
  read back as agent memory). There is no separate `model_calls` table or
  `record-usage` HTTP route. Persisted token counts must match the
  corresponding Dify answer-generator usage within 10% (live/opt-in).
- Logs must make correlation, routing outcome, retries, ticket
  transitions, delivery outcome, and digest send success/failure
  diagnosable without raw content (escalate already logs count and
  ticket ids).
- Merge-gate / `make test` uses a **fake** of the Start/End contract (no
  paid models, no live Studio). It does use local GreenMail via
  Testcontainers. Fake tests do not verify live Studio, Yandex, or
  indexed retrieval.

## Exclusions

- operator UI, inbound operator workflow / modeled human replies, and
  auto-close (escalation digest email is in v1; the LLM still replies on
  the employee path)
- provider comparison, runtime switching, and failover
- Yandex-managed agent/workflow/database runtime services beyond Yandex
  Cloud AI Studio foundation-model endpoints
- a real or public mailbox, real-mail sender assurance/authentication,
  public ingress, and sender/domain allowlists
- attachment processing, multilingual behavior, and real or sensitive data
- broader NLP-based PII discovery beyond the required deterministic types
- linked historical tickets after a closed-thread reply
- input-size / per-sender rate limits (deferred)
- Ansible or other infrastructure orchestration beyond minimal Compose/Make
- a separate submission pack

## Recorded parameters

Local demo: Schedule Trigger every minute; Dify app env
`ESCALATION_SECONDS=30` sent as `older_than_seconds`; HTTP Request retry
3 × 100ms on the ticketing `escalate-stale` call. Do not copy that retry
onto `send` (duplicate-digest risk; FR-8).
`OPERATOR_EMAIL=operator@example.test` for local GreenMail.
Recorded retrieval defaults live in
`tests/eval/golden_retrieval.json`. Live Yandex, live GreenMail, and
`make eval` stay opt-in.
