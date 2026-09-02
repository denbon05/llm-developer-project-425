"""Unit tests for HTML/plain extraction and ignored attachments."""

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email_gateway.normalize import (
    extract_body,
    sanitize_html,
    split_quoted_body,
)

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


# Latest unquoted question vs quoted remainder (portable `>` / HTML blockquote).
_LATEST_QUESTION = "How do I reset the VPN token?"
_QUOTED_PREVIOUS_ANSWER = "Use the self-service portal."
_PLAIN_BODY_WITH_QUOTE = (
    f"{_LATEST_QUESTION}\n\n"
    f"> {_QUOTED_PREVIOUS_ANSWER}\n"
    "> Then wait five minutes."
)
_PLAIN_QUOTE_BLOCK = f"> {_QUOTED_PREVIOUS_ANSWER}\n> Then wait five minutes."
_PLAIN_BODY_WITHOUT_QUOTE = "Please enable split-tunnel VPN for travel."


def test_split_quoted_body_separates_latest_from_quote() -> None:
    """First `>` line starts the quote; earlier text is the latest question."""
    request_text, blockquote = split_quoted_body(_PLAIN_BODY_WITH_QUOTE)
    assert request_text == _LATEST_QUESTION
    assert blockquote == _PLAIN_QUOTE_BLOCK
    assert _LATEST_QUESTION not in blockquote
    assert _QUOTED_PREVIOUS_ANSWER not in request_text


def test_split_quoted_body_without_quote_keeps_full_request() -> None:
    """No `>` quote: request_text is the full body and blockquote is empty."""
    request_text, blockquote = split_quoted_body(_PLAIN_BODY_WITHOUT_QUOTE)
    assert request_text == _PLAIN_BODY_WITHOUT_QUOTE
    assert blockquote == ""


_QUOTE_ONLY_BODY = "> Forwarded: the whole message is a quote."


def test_split_quoted_body_empty_latest_falls_back_to_full_body() -> None:
    """Empty unquoted split: request_text is the full body, quote is empty."""
    request_text, blockquote = split_quoted_body(_QUOTE_ONLY_BODY)
    assert request_text == _QUOTE_ONLY_BODY
    assert blockquote == ""


# Attribution + `>` quote: latest question must not include the On/wrote line.
_ATTRIBUTION_QUESTION = "Can I request day off for my teammate on his behalf?"
_ATTRIBUTION_LINE = "On 31/8/26 18:56, [email] wrote:"
_ATTRIBUTION_QUOTED_ANSWER = "Yes, you can request a day off."
_ATTRIBUTION_BODY = (
    f"{_ATTRIBUTION_QUESTION}\r\n\r\n"
    f"{_ATTRIBUTION_LINE}\r\n"
    f"> {_ATTRIBUTION_QUOTED_ANSWER}"
)
_ATTRIBUTION_QUOTE_BLOCK = (
    f"{_ATTRIBUTION_LINE}\n> {_ATTRIBUTION_QUOTED_ANSWER}"
)


def test_split_quoted_body_on_wrote_attribution_is_blockquote() -> None:
    """`On ... wrote:` and following `>` lines are quote, not request_text."""
    request_text, blockquote = split_quoted_body(_ATTRIBUTION_BODY)
    assert request_text == _ATTRIBUTION_QUESTION
    assert blockquote == _ATTRIBUTION_QUOTE_BLOCK
    assert _ATTRIBUTION_LINE not in request_text
    assert _ATTRIBUTION_QUOTED_ANSWER not in request_text
    assert _ATTRIBUTION_QUESTION not in blockquote


_ATTRIBUTION_ONLY_BODY = (
    f"{_ATTRIBUTION_LINE}\r\n> {_ATTRIBUTION_QUOTED_ANSWER}"
)


def test_split_quoted_body_attribution_only_falls_back_to_full_body() -> None:
    """Attribution with no unquoted text: full body is request_text."""
    request_text, blockquote = split_quoted_body(_ATTRIBUTION_ONLY_BODY)
    assert request_text == _ATTRIBUTION_ONLY_BODY.strip()
    assert blockquote == ""


_HTML_LATEST_QUESTION = "Need the VPN reset steps"
_HTML_QUOTED_ANSWER = "Last time we used the portal."
_HTML_WITH_BLOCKQUOTE = (
    f"<p>{_HTML_LATEST_QUESTION}</p>"
    f"<blockquote>{_HTML_QUOTED_ANSWER}</blockquote>"
    "<script>alert(1)</script>"
)


def test_sanitize_html_blockquote_is_plain_quote_for_split() -> None:
    """HTML <blockquote> inner text becomes a `>` line for the body split."""
    body = sanitize_html(_HTML_WITH_BLOCKQUOTE)
    request_text, blockquote = split_quoted_body(body)
    assert request_text == _HTML_LATEST_QUESTION
    assert _HTML_QUOTED_ANSWER in blockquote
    assert blockquote.startswith(">")
    assert _HTML_LATEST_QUESTION not in blockquote
    assert "alert" not in request_text
    assert "alert" not in blockquote


def test_sanitize_html_blockquote_only_falls_back() -> None:
    """HTML that is only a blockquote: visible quote text is request_text."""
    html = (
        f"<blockquote>{_HTML_QUOTED_ANSWER}</blockquote>"
        "<script>alert(1)</script>"
    )
    request_text, blockquote = split_quoted_body(sanitize_html(html))
    assert _HTML_QUOTED_ANSWER in request_text
    assert blockquote == ""
    assert "alert" not in request_text


def test_sanitize_html_blockquote_keeps_inline_tags_on_one_quote_line() -> None:
    """Inline tags inside <blockquote> stay on one `>` line, not many."""
    html = (
        f"<p>{_HTML_LATEST_QUESTION}</p>"
        "<blockquote>Use the <b>self-service</b> portal.</blockquote>"
    )
    request_text, blockquote = split_quoted_body(sanitize_html(html))
    assert request_text == _HTML_LATEST_QUESTION
    assert "self-service" in blockquote
    assert "self-service" not in request_text
    assert blockquote.count(">") == 1


def test_extract_html_body_preserves_quote_for_plain_split() -> None:
    """HTML-only extract encodes blockquote for the plain `>` split."""
    msg = MIMEText(_HTML_WITH_BLOCKQUOTE, "html")
    body = extract_body(msg)
    request_text, blockquote = split_quoted_body(body)
    assert request_text == _HTML_LATEST_QUESTION
    assert _HTML_QUOTED_ANSWER in blockquote
    assert _HTML_LATEST_QUESTION not in blockquote
    assert "alert" not in body
