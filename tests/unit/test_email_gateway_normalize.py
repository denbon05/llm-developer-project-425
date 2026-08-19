"""Unit tests for HTML/plain extraction and ignored attachments."""

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email_gateway.normalize import extract_body, sanitize_html

# Script/style must drop; inner text of allowed tags stays.
_HTML_WITH_SCRIPT = "<p>Hello <b>VPN</b></p><script>alert(1)</script>"
_PLAIN_PREFERRED = "plain-only"
_VISIBLE_BODY = "visible body"
# Must never appear in extracted body.
_ATTACHMENT_BYTES = b"SECRET_FILE"
_ATTACHMENT_FILENAME = "x.bin"


def test_sanitize_html_drops_script_and_tags() -> None:
    """Script/style and tags drop; visible inner text remains."""
    text = sanitize_html(_HTML_WITH_SCRIPT)
    assert "Hello" in text
    assert "VPN" in text
    assert "alert" not in text
    assert "<" not in text


def test_extract_body_prefers_plain_over_html() -> None:
    """multipart/alternative prefers text/plain over HTML."""
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText("<p>html-only</p>", "html"))
    msg.attach(MIMEText(_PLAIN_PREFERRED, "plain"))
    assert extract_body(msg) == _PLAIN_PREFERRED


def test_extract_body_ignores_attachments() -> None:
    """Attachment bytes never appear in the extracted body."""
    msg = MIMEMultipart()
    msg.attach(MIMEText(_VISIBLE_BODY, "plain"))
    attachment = MIMEApplication(
        _ATTACHMENT_BYTES,
        Name=_ATTACHMENT_FILENAME,
    )
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=_ATTACHMENT_FILENAME,
    )
    msg.attach(attachment)
    body = extract_body(msg)
    assert body == _VISIBLE_BODY
    assert _ATTACHMENT_BYTES.decode() not in body
