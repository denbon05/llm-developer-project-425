"""Literals shared by email-gateway integration fixtures and proofs.

Not production constants: synthetic keys, allow-list host, and PII samples.
"""

# Stand-in for CITATION_URL_BASE.
CITATION_URL_BASE = (
    "https://github.com/example/helpdesk/blob/main/knowledge_base/"
)

# Already has Bearer; gateway must not prefix a second Bearer.
DIFY_APP_KEY = "Bearer test-app-key"

# MockTransport never connects; URL only satisfies Settings.
DIFY_WORKFLOW_URL = "http://dify.test/v1/workflows/run"

# Tests call run_poll_cycle; Settings still requires a positive interval.
POLL_INTERVAL_SECONDS = 1
# MockTransport is instant; bound a hung client if the fake is miswired.
DIFY_TIMEOUT_SECONDS = 5.0

# Dify Start field names (architecture contract; not JSON Field).
INPUT_USER_EMAIL = "user_email"
INPUT_SUBJECT = "subject"
INPUT_REQUEST_TEXT = "request_text"
INPUT_BLOCKQUOTE = "blockquote"
START_INPUT_KEYS = frozenset(
    {
        INPUT_USER_EMAIL,
        INPUT_SUBJECT,
        INPUT_REQUEST_TEXT,
        INPUT_BLOCKQUOTE,
    }
)
RESPONSE_MODE_BLOCKING = "blocking"

# Samples that privacy.mask_text must remove from subject+body before Dify.
PII_PHONE = "+33 1 23 45 67 89"
PII_PHONE_MASK = "+** *** ** ** 89"
PII_EMAIL_IN_BODY = "a@b.co"
PII_EMAIL_IN_SUBJECT = "me@corp.test"
PII_CARD = "4111111111111111"  # Luhn-valid Visa test PAN
