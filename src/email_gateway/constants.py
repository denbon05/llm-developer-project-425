"""Gateway constants."""

# Canned SMTP body; never inbound/model text (no fail-open).
STATIC_ACK_TEXT = (
    "Your request was received. Automated processing could not be completed."
)

# SMTP body when the inbound mail is only a greeting (no Dify call).
GREETING_REPLY_TEXT = "Hello. How can I help you?"

# Case-insensitive; word-list is provisional (see requirements).
TOXICITY_TERMS = ("idiot", "stupid", "shut up", "hate you")

# SMTP connect/login/send budget (seconds). Not the Dify HTTP timeout.
SMTP_TIMEOUT_SECONDS = 30

# HTTP status >= this means the workflow run did not succeed.
HTTP_ERROR_STATUS_MIN = 400
