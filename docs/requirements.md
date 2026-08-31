# v1 Requirements

This document defines observable v1 behavior. Domain terms are defined in
[CONTEXT.md](../CONTEXT.md); module placement and interfaces are defined in
[architecture.md](architecture.md).

## Scope / boundaries

v1 is the LLM email path. The **email gateway** owns IMAP/SMTP (GreenMail is
the adapter). **Dify** is the brain: it answers from company knowledge or
opens a ticket when it cannot. Ticket/KB persistence follows the table in
FR-3. `open` tickets whose `updated_at` is older than the inactivity
threshold (default 24h / `escalation_seconds`) become `escalated` via
existing ticketing HTTP (status-only). Later employee mail still follows
the non-`closed` path; the human/operator path remains out of scope.
`answered` and `closed` stay in the schema unused. The employee cannot
force ticket creation when knowledge can answer and no non-`closed`
ticket exists.

## Functional requirements

- **FR-1 — Email channel.** GreenMail is mandatory for the initial integration
  and deterministic end-to-end tests. The gateway polls **generic IMAP** (not
  the GreenMail HTTP mail API, not a Dify schedule for IMAP) and sends through
  generic SMTP. It processes plain text and sanitized HTML in English and
  ignores attachment contents. The default poll interval is one minute; it is
  configurable and may be shortened in tests.
- **FR-2 — Safe intake.** Size and per-sender rate limits are **deferred**
  (not a Phase 4 gate). After normalization and before any Dify call, the
  gateway applies one-way PII masking (`src/privacy`) so Studio logs never see
  raw PII. Toxicity then hello are **gateway regex** (ordered intake rules in
  `email_gateway.replies`): static SMTP body, no Dify, no KB, no MCP, no
  ticket. A hello match must be the whole remaining text so a real question
  still reaches Dify. Injection patterns and the helpdesk-scope classifier
  remain separate Dify concerns. v1 has no sender or domain allowlist.
- **FR-3 — Controlled routing.** After normalization and masking, the gateway
  POSTs a blocking Dify run unless gateway intake already replied (it does
  **not** call MCP). Dify calls `list-my-tickets` to branch. Injection/scope
  (Phase 7) distinguish `injection`, `non_helpdesk`, and legitimate
  help-desk content:
  injection gets a static block and **no ticket**; non-helpdesk a bounded
  refusal (those `reply_text` values SMTP when the workflow finishes). A
  gateway Dify HTTP or outputs failure is not fail-open: log the error, skip
  SMTP, leave the message UNSEEN, retry on the next poll. None of those
  paths create a ticket from the gateway.
  Legitimate content follows this table (employee **cannot** override):

  | State | KB can answer | DB |
  | --- | --- | --- |
  | No non-`closed` ticket | yes | **no** ticket, **no** `messages` — email only + citations |
  | No non-`closed` ticket | no | `create-ticket` (`tickets.text` only) **and** `append-message` user (inbound mail) **then** `append-message` agent (reply). |
  | Non-`closed` ticket already exists (`open` **or** `escalated`) | yes or no | **always** append user + agent; **still run KB** |

  On a knowledge gap (row 2), `reply_text` admits the miss; End `ticket_id`
  is set; SMTP includes that id (gateway `Ticket:` line). `create-ticket`
  MCP remains text-only (no `messages` row at the tool). The **workflow**
  adds the first user mail via `append-message`. After a non-`closed`
  ticket exists, persist messages even if KB could answer. The
  ticket must exist and `ticket.user_id` must match `user_id` or append is
  `NOT_FOUND`. Append inserts a message and bumps `tickets.updated_at`; it
  does not change ticket text or status. Agent rows may include usage.
  On the knowledge-gap path the categorizer runs sequentially (after the
  answer LLM, before `create-ticket`) and emits one `TicketCategory`.
  Unknown category strings are `NOT_ELIGIBLE`. Skip the categorizer on
  KB-hit and follow-up paths. Escalate is option A (no human):
  `POST /v1/tickets/escalate-stale` still flips idle `open` → `escalated`
  (status-only). Later employee mail still uses the non-closed path above.
  `append-message` does not change status (ticket stays `escalated`). Do
  not reopen. There is no operator UI; the human/operator path remains
  out of scope. Dify does not own escalate rules.
- **FR-4 — Knowledge and citations.** v1 uses one Dify knowledge base
  (`employee-helpdesk`), persistent bundled Weaviate, and local embeddings
  through an internal resource-limited Ollama container. The email
  workflow Knowledge Retrieval node uses Weighted Score. Recorded search
  settings live in `tests/eval/golden_retrieval.json`. Corpus: eight
  concise synthetic English documents in `knowledge_base/`. Canonical
  knowledge is
  versioned in Git. End `source_filenames` are `knowledge_base/` filenames
  from retrieval, never model-generated URLs. The gateway builds
  `{CITATION_URL_BASE}{filename}` and appends a `Sources:` footer to the
  SMTP body. It rejects names that are not a single filename. Empty,
  omitted, or null `source_filenames` is a KB miss (no footer).
- **FR-5 — Ticket ownership and interfaces.** The ticketing module owns durable
  tickets, messages, and escalation validity. MCP tools are
  `create-ticket`, `list-my-tickets`, `append-message`; `user_id` (sender
  email) is a tool argument, not an HTTP header. `list-my-tickets` returns
  only tickets for that `user_id`, newest `updated_at` first, each with
  masked `tickets.text`. Optional `statuses` (list of status strings):
  omitted/`None` defaults to `open`, `escalated`, and `answered` (so list
  agrees with create’s non-closed invariant; `answered` is unused by the
  LLM writer path). Empty `statuses=[]` returns no rows. Unknown status
  strings are `NOT_ELIGIBLE`. Private HTTP is scheduled
  `POST /v1/tickets/escalate-stale` (private network, no shared secret), not a
  resource REST API. v1 persists a minimal schema (`tickets` and `messages`)
  in application PostgreSQL (`helpdesk-db`), separate from Dify's PostgreSQL.
  SMTP send/receive stays in the email gateway; v1 does not use an application
  outbox table. Only Dify calls MCP; the gateway does not.
- **FR-6 — Ticket model.** Message roles, categories, statuses, and domain error
  codes are the `contracts.enums` StrEnums (`MessageRole`, `TicketCategory`,
  `TicketStatus`, `DomainErrorCode`); see that module for values. Roles are
  `user` | `agent` only. Each ticket stores `user_id` as the synthetic sender
  email (course MVP) and masked ticket text in `tickets.text` (set at
  create, not updated later). A message always belongs to a ticket
  (`ticket_id` required FK). `model`
  / `tokens_in` / `tokens_out` / `latency_ms` land on agent messages at
  `append-message` time. Those rows are audit and token accounting, not
  agent memory (no list-messages tool). Persistence uses VARCHAR for enum
  fields (ORM enums, not Postgres ENUM types); see architecture MVP schema.
- **FR-7 — Ticket lifecycle.** A new ticket starts `open`. Escalation is
  inactivity on `updated_at`, not calendar time from create that ignores
  chat. Scheduled HTTP selects `status=open` with `updated_at` older than
  a threshold (`older_than_seconds`, default `Settings.escalation_seconds`
  / 86400) and sets `escalated` (status-only; no lifecycle messages).
  Ongoing dialogue delays escalate. After `escalated`, later employee mail
  still follows the non-closed path (KB + answer + two appends); status
  stays `escalated`. No reopen. `answered` and `closed` remain in
  the enum/schema; the LLM path does not write them. Tests or another
  system may poke those statuses. `append-message` inserts a message and
  bumps `tickets.updated_at`; it does not change ticket text or status.
- **FR-8 — Delivery semantics.** Ticket/message effects are best-effort and
  at-least-once. The gateway may mark an inbound message processed
  (IMAP `\Seen`) after successful SMTP of an intake or workflow reply.
  A failed Dify call does not SMTP and does not set `\Seen`. Poll retries
  may repeat mutations.
  Outbound SMTP is gateway-owned and at-least-once: a crash after send but
  before `\Seen` can duplicate the email on the next poll. Documented SMTP
  duplicate window: **one poll interval** (default 60s) **plus** the blocking
  Dify wait. No outbox table. Receiver-visible exactly-once is not claimed.
- **FR-9 — Dify lifecycle.** Two Workflow-type Studio Apps:
  1. `email_helpdesk` — User Input start; gateway blocking Service API
     `POST …/v1/workflows/run`. Committed export
     `dify/apps/email_helpdesk.yml` is the architecture graph with
     Knowledge Retrieval (Weighted Score, local embeddings) and
     Code/Template stubs for answer and categorizer (not a Start→End
     echo).
  2. Escalate — Schedule Trigger (daily / 24h; hourly allowed for demo)
     that **only** HTTP-calls `POST /v1/tickets/escalate-stale`, with a
     retry policy (counts TBD). No escalate logic in Dify. User Input vs
     Trigger are different start types; keep two apps.
  Apps are authored in the UI, then exported as secret-free DSL under
  `dify/apps/` (one export per Studio App). The gateway depends on this small
  HTTP contract, not Studio internals (console session URLs). Provider-specific
  response shapes must not leak into callers.
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
  enters durable business fields. Masking uses one visible format (the same
  in every store humans read): email → `[email]`; phone →
  `+7 (***) ***-**-NN` (last two digits kept); card →
  `****-****-****-****`. It is not reversible encrypt/decrypt.
  Required detection covers email addresses, phone-like values, and
  payment-card candidates that pass a Luhn check. GreenMail
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
  Dify DSL. The workflow app key lives in gitignored `.env`
  (`DIFY_EMAIL_HELPDESK_API_KEY`).
- **SEC-8 — External models.** **Yandex Cloud AI Studio** is the only allowed
  **external provider** (many Studio foundation models are OK). Embedding
  stays local Ollama. Configuration and acceptance reject OpenAI, watsonx,
  Cohere, Jina, and every other external model provider.

## Observability constraints

- The gateway uses the **blocking** Service API JSON (`data.outputs` and any
  `workflow_run_id` / usage metadata on that response). SSE is optional, not
  required for Phase 4.
- Agent message records retain `model`, `tokens_in`,
  `tokens_out`, and `latency_ms` fields set at `append-message` time (audit
  and tokens; not read back as agent memory). There is no separate
  `model_calls` table or `record-usage` HTTP route.
- Persisted token counts must match the corresponding Dify answer-generator
  usage within 10% (live/opt-in).
- Logs must make correlation, routing outcome, retries, ticket transitions, and
  delivery outcome diagnosable without raw content.

## Acceptance criteria

1. A supported GreenMail question with **no** non-`closed` ticket and a KB hit
   produces a grounded English email with a clickable trusted repository
   citation. No ticket is created and no `messages` row is written. When a
   ticket **is** created (knowledge gap, no non-`closed` ticket), `text` is
   stored
   masked in `tickets.text` (immutable after create) **and** the first user
   mail is an `append-message` row. Later chat lines are also
   `append-message`. `create-ticket` MCP remains text-only.
2. When no existing-ticket path applies and knowledge evidence is sufficient,
   a legitimate request produces a grounded cited email as above — emailed
   only, with no MCP message ids.
3. A legitimate request below the evidence threshold, with no non-`closed`
   ticket, creates exactly one ticket **and** a first user `messages` row,
   then an agent row for the reply. `reply_text` admits the knowledge gap;
   the SMTP body includes the new ticket id. Categorizer runs only on
   this knowledge-gap path (sequential: classify, then create, then
   appends).
4. Toxicity/hello matches in the **gateway** produce a static SMTP body.
   Dify is **not** called. No ticket. Injection (including “ignore previous
   instructions” in the request body) and non-helpdesk input produce a
   static block and a bounded refusal when the workflow finishes; injection
   does not create a ticket.
   A gateway Dify HTTP or outputs failure logs an error, skips SMTP, and
   leaves the message UNSEEN for the next poll (no fail-open canned body);
   none of those paths creates a ticket from the gateway.
5. `append-message` requires `ticket_id`, `user_id`, `text`, and `role`. The
   ticket must exist and match `user_id`; otherwise the write is `NOT_FOUND`.
   Invented ticket ids and ticket ids owned by a different `user_id` are
   rejected. `create-ticket` stores `text` in `tickets.text` only. A new
   ticket is created only when this `user_id` has no non-`closed` ticket.
   Append inserts a message and bumps `tickets.updated_at` (activity); it
   does not rewrite `tickets.text` or change ticket status. A non-`closed`
   ticket (`open` or `escalated`) always appends user + agent and still
   runs KB.
6. `list-my-tickets` returns only tickets for the `user_id` tool argument,
   including masked `text`. Optional `statuses` defaults to `open`,
   `escalated`, and `answered` (hides `closed`); empty `statuses=[]`
   returns no rows; unknown status strings are `NOT_ELIGIBLE`. Course MVP:
   that argument is model-visible; ticketing scopes to it rather than
   rejecting a caller-supplied identity. Dify uses this tool to branch
   on remaining (non-intake) mail. The answer LLM does not invent
   `user_id` / `ticket_id`; workflow wiring supplies them.
7. Escalation tests prove scheduled HTTP `POST /v1/tickets/escalate-stale`
   moves `open` tickets with stale `updated_at` to `escalated` without
   inserting messages. An append that refreshes `updated_at` keeps that
   ticket `open` while a similarly aged idle ticket escalates. After
   `escalated`, later employee mail still appends user + agent and still
   runs KB; status stays `escalated`. A Dify Schedule Trigger app (Phase 8)
   only calls this HTTP (retry policy, counts TBD); it does not encode
   escalate rules. The human/operator path remains out of scope.
8. Privacy tests show required PII absent from Dify-bound content, durable
   ticket/message **text**, and application logs/errors, and that remaining
   matches use the SEC-2 mask shapes. The documented business-store
   exception is MVP `tickets.user_id` (synthetic sender email); GreenMail's
   raw synthetic transport messages are explicitly outside the text-masking
   invariant.
9. Gateway retry handling uses mailbox hints (`\Seen` after successful SMTP
   of an intake or workflow reply; Dify failure leaves UNSEEN) and
   best-effort semantics; tests demonstrate the documented at-least-once
   SMTP duplicate window (one poll interval plus blocking Dify wait).
10. Contract tests preserve `workflow_run_id` / usage when present on the
    **blocking** JSON. Merge-gate uses a **fake** of the Start/End contract
    (no paid models, no live Studio). Phase 4 treated a live echo as
    enough; later opt-in checks may compare stored token counts with
    generator usage within 10%.
11. Malicious instructions in retrieved knowledge cannot change routing, tool
    authorization, or repository-controlled citation filenames.
12. Restart and restore checks preserve ticket/message data; deleting the
    vector index and re-ingesting canonical Git documents restores retrieval.
13. Deterministic merge-gate CI uses fake Dify contract behavior, local
    GreenMail/PostgreSQL/retrieval, static DSL/provider/contract checks that
    reject non-Yandex-Cloud-AI-Studio external models, and any no-model Dify
    slice. Real Yandex classifier/generator routes and full live
    Dify/Yandex behavior are opt-in smoke/evaluation checks; fake tests do not
    verify them.
14. Committed Dify App exports under `dify/apps/` contain no secrets and are
    demonstrably derived after the UI-authored workflow slices.
15. Submission evidence for the course substitute stack is a Dify workflow run
    and blocking-response usage/run metadata (SSE not required), ticket status
    observed through private interfaces (plus the permitted direct privacy
    audit), and a deterministic GreenMail end-to-end transcript — not YDB or
    Yandex-managed application runtimes.

## Exclusions

- operator UI, modeled human replies, and auto-close (the human/operator
  path after `escalated` remains out of scope; the LLM still replies)
- OpenAI, watsonx, Cohere, Jina, and all non–Yandex Cloud AI Studio external
  model APIs; provider comparison, runtime switching, and failover
- Yandex-managed agent/workflow/database runtime services beyond Yandex Cloud
  AI Studio foundation-model endpoints
- a real or public mailbox, real-mail sender assurance/authentication, public
  ingress, and sender/domain allowlists
- attachment processing, multilingual behavior, and real or sensitive data
- broader NLP-based PII discovery beyond the required deterministic types
- linked historical tickets after a closed-thread reply
- input-size / per-sender rate limits as a current gate (deferred)
- Ansible or other infrastructure orchestration beyond minimal Compose/Make

## Provisional parameters

Toxicity word-list contents, escalation intervals, and escalate HTTP
retry counts will be calibrated at their phase gates. Recorded retrieval
defaults live in `tests/eval/golden_retrieval.json`. Until then, the
required outcomes above are normative:
KB hit with no non-`closed` ticket → email only (no ticket, no `messages`);
knowledge gap with no non-`closed` ticket → `create-ticket` plus first-user
`append-message` then agent append; non-`closed` ticket → always append
user+agent and still retrieve; toxicity/hello → gateway static SMTP, no
Dify, no ticket; gateway Dify HTTP/outputs failure → error log, no SMTP,
leave UNSEEN (no fail-open); `open` tickets inactive on `updated_at`
escalate over HTTP.
