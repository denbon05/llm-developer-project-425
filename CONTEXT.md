# Domain Glossary

These terms describe the help-desk domain. Required behavior and technical
design belong in the linked requirements and architecture documents.

## Actors

- **Employee** — the person seeking internal help and the author of inbound
  help-desk messages.
- **Assistant** — the automated author of grounded answers, ticket
  confirmations, static blocks/refusals, and deferred acknowledgements.
- **Operator** — the authorized human author of support responses.
- **System** — the non-human author of lifecycle and delivery records and
  operator digests.

## Core terms

- **Conversation** — the logically correlated exchange of messages for an
  employee email thread. A conversation may have no ticket or may produce
  separate tickets over time.
- **Message** — one immutable contribution to a conversation, attributed to
  exactly one actor.
- **Ticket** — an independently tracked help-desk work item requiring operator
  attention, with one category, one lifecycle state, and a message history.
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

## Ticket categories

- **bug** — an existing tool, device, or process is malfunctioning or producing
  an error.
- **access** — an account, permission, authentication, or authorization issue.
- **docs** — company guidance is missing, unclear, inconsistent, or incorrect.
- **feature** — a request for a new capability or an enhancement.
- **other** — a legitimate help-desk matter that does not fit the four specific
  categories.

## Ticket states

- **open** — active and awaiting operator action.
- **escalated** — still active and awaiting operator action after its response
  target was missed.
- **answered** — the operator has responded and the ticket awaits employee
  follow-up or the end of the response window.
- **closed** — no further work is active for that ticket.
