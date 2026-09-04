"""Gateway constants."""

# Intake: static SMTP, no Dify.
STATIC_ACK_TEXT = (
    "Your request was received. Automated processing could not be completed."
)
"""Canned SMTP body; never inbound or model text."""

GREETING_REPLY_TEXT = "Hello. How can I help you?"
"""Canned SMTP body."""

TOXICITY_TERMS = ("idiot", "stupid", "shut up", "hate you")
"""Insults and short hostile phrases."""

INJECTION_PHRASE_TERMS = (
    "ignore previous instruction",
    "ignore previous instructions",
    "DROP TABLE",
)
"""Instruction-override and SQL phrases."""

FAIL_SMTP_SEND = "smtp_send"
"""SMTP did not accept the message (log / HTTP detail)."""

SMTP_TIMEOUT_SECONDS = 30
"""SMTP connect/login/send timeout (seconds)."""

# Employee-reply SMTP body.
KNOWLEDGE_GAP_REPLY_MARKER = "I don't know"
"""Substring that marks a knowledge-gap miss in End ``reply_text``."""

CITATION_SOURCES_HEADING = "Sources:"
"""Plain-text SMTP footer heading above gateway-built citation URLs."""

TICKET_ID_HEADING = "Ticket:"
"""Plain-text SMTP line prefix for End ``ticket_id``."""

# Private digest HTTP.
API_PREFIX = "/v1"
"""Private HTTP route prefix (same as ticketing)."""

SEND_EMAIL_ROUTE = "/emails/send"
"""Path under ``API_PREFIX`` for digest SMTP."""

SEND_EMAIL_PATH = f"{API_PREFIX}{SEND_EMAIL_ROUTE}"
"""Full path for ``POST`` digest send."""
