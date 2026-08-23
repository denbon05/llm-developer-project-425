"""Gateway constants."""

STATIC_ACK_TEXT = (
    "Your request was received. Automated processing could not be completed."
)
"""Canned SMTP body; never inbound or model text."""

GREETING_REPLY_TEXT = "Hello. How can I help you?"
"""Canned SMTP body."""

TOXICITY_TERMS = ("idiot", "stupid", "shut up", "hate you")
"""Insults and short hostile phrases."""

SMTP_TIMEOUT_SECONDS = 30
"""SMTP connect/login/send timeout (seconds)."""

HTTP_ERROR_STATUS_MIN = 400
"""HTTP statuses at or above this are errors."""

FAIL_HTTP_ERROR = "http_error"
"""Transport or HTTP client failure; not SMTP text."""

FAIL_HTTP_STATUS = "http_status"
"""HTTP status was an error; not SMTP text."""

FAIL_BAD_JSON = "bad_json"
"""Response body was not valid JSON."""

FAIL_OUTPUTS_INVALID = "outputs_invalid"
"""Workflow End outputs failed validation."""
