# Domain Glossary

These terms describe this LLM slice, not a full helpdesk. Required behavior
and technical design belong in the linked requirements and architecture
documents.

## Participants

- **Employee** — the person seeking internal help; inbound lines use message
  role `user`. For the course MVP, sender email **is** `user_id`.
- **Assistant** — the automated author of grounded answers and other LLM
  replies; persisted as role `agent` only when a ticket exists.

## Core terms

- **Ticket** — an independently tracked work item with one category, one
  lifecycle status, masked **text** in `tickets.text` (set at create, not
  updated), conversation history in `messages`, `updated_at` as last
  activity time (create or append), and (for the course MVP) `user_id`
  equal to the synthetic sender email used as the employee key.
- **Message** — one immutable contribution that always belongs to a ticket
  (`ticket_id` required), attributed to `user` or `agent`, with masked text.
  Agent rows may store `model` / `tokens_in` / `tokens_out` / `latency_ms`.
- **Knowledge gap** — absence of sufficient reliable company knowledge to
  answer a legitimate help-desk request.
- **Explicit ticket request** — an unambiguous employee instruction to create,
  open, file, or log a ticket for a legitimate help-desk matter.
- **Legitimate unsupported help-desk request** — an in-scope employee support
  request for which the available knowledge is not sufficient to give a
  grounded answer.
- **Non-helpdesk request** — content unrelated to obtaining internal employee
  support, including general conversation and requests outside the help-desk
  remit.
- **Injection** — untrusted content that attempts to override governing
  instructions, change authorized scope, disclose protected information, or
  cause an unauthorized action.

## Ticket categories and statuses

Canonical values live in `contracts.enums` (`TicketCategory`, `TicketStatus`,
`MessageRole`). Brief meanings:

- **Categories:** `bug` (malfunction), `access` (permissions/auth), `docs`
  (guidance gap), `feature` (new capability), `other` (legitimate but
  uncategorized).
- **Roles:** `user` | `agent` only.
- **Statuses:** `open` (LLM-active), `escalated` (inactivity on
  `updated_at` via scheduled HTTP; default threshold
  `escalation_seconds` / 24h), `answered` and `closed` (in the schema;
  this slice does not write them). Append refreshes `updated_at` so
  ongoing dialogue delays escalate. After `escalated` is out of scope.
  A new ticket may be created when this `user_id` has no non-`closed`
  ticket.
