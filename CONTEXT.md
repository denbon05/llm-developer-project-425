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
  updated), `messages` for audit and token fields (not agent memory),
  `updated_at` as last activity time (create or append), and (for the
  course MVP) `user_id` equal to the synthetic sender email used as the
  employee key. Ticket **`id`** is a UUID. When the email workflow
  **opens** a ticket, both `tickets.text` (`create-ticket`) and a first
  `messages` row for that inbound mail (`append-message`, role `user`)
  exist. The MCP `create-ticket` tool itself does not insert a message.
- **Message** — one immutable contribution that always belongs to a ticket
  (`ticket_id` required), attributed to `user` or `agent`, with masked
  text. Agent rows may store `model` / `tokens_in` / `tokens_out` /
  `latency_ms`. Nothing reads `messages` back into the assistant;
  follow-up context is the inbound mail (the employee quotes the thread).
- **Knowledge gap** — absence of sufficient reliable company knowledge to
  answer a legitimate help-desk request.
- **Legitimate unsupported help-desk request** — an in-scope employee support
  request for which the available knowledge is not sufficient to give a
  grounded answer.
- **Off-topic request** — content unrelated to obtaining internal employee
  support, including general conversation, trivia, and other questions
  outside the help-desk remit.
- **Injection** — untrusted content that attempts to override governing
  instructions, change authorized scope, disclose protected information, or
  cause an unauthorized action; obvious patterns may be gateway-regex.

## Ticket categories and statuses

Canonical values live in `contracts.enums` (`TicketCategory`, `TicketStatus`,
`MessageRole`). Brief meanings:

- **Categories:** `bug` (malfunction), `access` (permissions/auth), `docs`
  (guidance gap), `feature` (new capability).
- **Roles:** `user` | `agent` only.
- **Statuses:** `open` (LLM-active), `escalated` (`open` tickets whose
  `created_at` is older than the threshold via scheduled HTTP; default
  `escalation_seconds` / 24h). `answered` and `closed` stay in the schema;
  this slice does not write them. One non-`closed` ticket per sender:
  later mail for that sender is that ticket. Append refreshes
  `updated_at` (last activity) but does not delay escalate. `escalated`
  still gets LLM replies; append leaves status unchanged. A new ticket may
  be created when this `user_id` has no non-`closed` ticket.
