# Dify Help Desk


[![Actions Status](https://github.com/denbon05/llm-developer-project-425/actions/workflows/hexlet-check.yml/badge.svg)](https://github.com/denbon05/llm-developer-project-425/actions)


## Send a test email

There is no public mailbox. Mail is local GreenMail. The inbox is
available only while the app stack is running (`make app-stack-up`).

1. One-time machine setup (skip if already done): `make bootstrap`, then
   the Studio checklist in [docs/setup.md](docs/setup.md) (import the
   workflows, API key, knowledge base, Yandex).
2. Start the stacks and leave them running:

   ```bash
   make dify-stack-up    # terminal 1
   make app-stack-up     # terminal 2
   ```

3. In a mail client, add the **employee** account (not support). Use
   IMAP, not POP. If the client auto-picks SSL or STARTTLS, turn that
   off; GreenMail is plain localhost. If login fails, use username
   `employee1` (local part), not the full address.

   | Setting | Value |
   | --- | --- |
   | Account type | IMAP |
   | Email address | `employee1@example.test` |
   | Username | `employee1` |
   | Password | `employee1-pass` |
   | Incoming host | `127.0.0.1` |
   | Incoming port | `3143` |
   | Incoming encryption | None (no SSL, no STARTTLS) |
   | Incoming authentication | Normal password |
   | Outgoing host | `127.0.0.1` |
   | Outgoing port | `3025` |
   | Outgoing encryption | None (no SSL, no STARTTLS) |
   | Outgoing authentication | Normal password (same username and password) |

4. Compose **To:** `support@example.test`. Send a short English question
   (for example guest Wi-Fi). Do not log in as `support@example.test`;
   that mailbox is the gateway inbox.
5. Wait about one minute (poll interval). The reply arrives in the same
   employee inbox.

To see an escalation digest, add `operator@example.test` the same way
(username `operator`, password `operator-pass`, same hosts and ports).
That account is only for reading digest mail, not for sending employee
questions.

Recorded run of that path: [docs/screenshots](docs/screenshots/README.md).

## Dev

An email help-desk assistant for employees. A knowledge hit with no
non-`closed` ticket is emailed with citations (no ticket, no `messages`
row). A knowledge gap with no non-`closed` ticket opens a ticket and
records the inbound mail; the reply admits the miss. A non-`closed`
ticket (`open` or `escalated`) always appends user + agent and still
retrieves. Stale `open` tickets become `escalated` over scheduled HTTP,
and the operator receives an escalation digest email. There is no
operator UI.

Trusted: governing instructions, MCP tool schemas, repository citation
filenames, digest `subject`, and `OPERATOR_EMAIL`.

Untrusted: employee mail (headers, HTML, body), retrieved knowledge,
model output, and ticket `text`. Untrusted text must not be copied into
trusted instructions, routing, or authorization.

Host tools: `uv`, plus Docker Desktop (Compose v2) on `PATH`. Platform
setup: [docs/setup.md](docs/setup.md).

```bash
make bootstrap         # env files + uv sync --all-extras
make dify-stack-up     # terminal 1
make app-stack-up      # terminal 2
make test              # fake Dify; GreenMail via Testcontainers; skips eval
```

Opt-in live retrieval (`make eval`) is in [docs/setup.md](docs/setup.md).

## Documentation

- [Domain glossary](CONTEXT.md)
- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Platform setup](docs/setup.md)
- [Demo screenshots](docs/screenshots/README.md)
