"""Inbound mail → sender, subject, body. Attachments are ignored.

Flow: ``normalize_inbound`` reads From and Subject, then ``extract_body``
walks MIME parts (plain preferred, else HTML). HTML goes through
``sanitize_html`` / ``_TextExtractor``: skip script/style, break on block
tags, then strip leftover markup.
"""

from __future__ import annotations

import re
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr
from html import unescape
from html.parser import HTMLParser

# Inner HTML of these tags is never emitted as body text.
_SKIP_TAGS = frozenset({"script", "style"})
# Block-ish tags become a newline so paragraphs do not run together.
_BREAK_TAGS = frozenset(
    {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "hr"}
)
# Leftover markup after the parser (e.g. undeclared tags).
_TAG_RE = re.compile(r"<[^>]+>")
# Visible-text separators after dropping tags.
_BLOCK_BREAK = "\n"
_TAG_PLACEHOLDER = " "
# Unclosed skip-tag nesting; 0 means we are collecting visible text.
_SKIP_DEPTH_NONE = 0

# MIME / RFC 2045 tokens when walking the message.
_CONTENT_TYPE_PLAIN = "text/plain"
_CONTENT_TYPE_HTML = "text/html"
_DISPOSITION_ATTACHMENT = "attachment"
_HEADER_CONTENT_DISPOSITION = "Content-Disposition"
_HEADER_SUBJECT = "Subject"
_HEADER_FROM = "From"
# Part omitted charset: treat payload as UTF-8.
_DEFAULT_CHARSET = "utf-8"
# Malformed bytes become U+FFFD; do not fail the whole body.
_DECODE_ERRORS = "replace"


class _TextExtractor(HTMLParser):
    """Stdlib HTML → visible text (no extra HTML dependency).

    Parser callbacks run in document order: start tag, data, end tag.
    ``_skip_depth`` counts open script/style so nested skip tags stay quiet.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = _SKIP_DEPTH_NONE

    def handle_starttag(
        self, tag: str, _attrs: list[tuple[str, str | None]]
    ) -> None:
        """Open a tag: maybe start skipping, maybe insert a block break."""
        lowered = tag.lower()
        # Later handle_data is dropped until matching end tags close this.
        if lowered in _SKIP_TAGS:
            self._skip_depth += 1
        # Keep adjacent blocks from concatenating into one line.
        if lowered in _BREAK_TAGS:
            self._chunks.append(_BLOCK_BREAK)

    def handle_endtag(self, tag: str) -> None:
        """Close a skip tag; extra closes must not drive depth negative."""
        if tag.lower() in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        """Collect text nodes unless we are inside script/style."""
        if self._skip_depth:
            return
        self._chunks.append(data)

    def extract_text(self) -> str:
        """Join chunks, drop leftover tags, collapse blank lines."""
        raw = unescape("".join(self._chunks))
        without_tags = _TAG_RE.sub(_TAG_PLACEHOLDER, raw)
        lines = [line.strip() for line in without_tags.splitlines()]
        return _BLOCK_BREAK.join(line for line in lines if line)


def sanitize_html(html: str) -> str:
    """Run ``_TextExtractor`` to completion and return visible text."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.extract_text()


def _decode_part(part: Message) -> str:
    """Decode a leaf part's payload; missing charset → UTF-8 with replace."""
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        charset = part.get_content_charset() or _DEFAULT_CHARSET
        return payload.decode(charset, errors=_DECODE_ERRORS)
    raw = part.get_payload()
    return raw if isinstance(raw, str) else ""


def _is_attachment(part: Message) -> bool:
    """True when Content-Disposition names an attachment (bytes ignored)."""
    disposition = str(part.get(_HEADER_CONTENT_DISPOSITION) or "").lower()
    return _DISPOSITION_ATTACHMENT in disposition


def extract_body(message: Message) -> str:
    """Walk MIME: skip attachments; prefer all text/plain, else HTML."""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in message.walk():
        if part.is_multipart() or _is_attachment(part):
            continue
        content_type = part.get_content_type()
        if content_type == _CONTENT_TYPE_PLAIN:
            plain_parts.append(_decode_part(part))
        elif content_type == _CONTENT_TYPE_HTML:
            html_parts.append(_decode_part(part))
    if plain_parts:
        return _BLOCK_BREAK.join(plain_parts).strip()
    if html_parts:
        return sanitize_html(_BLOCK_BREAK.join(html_parts)).strip()
    return ""


def decode_subject(message: Message) -> str:
    """RFC 2047-decoded Subject, or empty if the header is missing."""
    raw = message.get(_HEADER_SUBJECT)
    if not raw:
        return ""
    return str(make_header(decode_header(raw)))


def extract_sender_mailbox(message: Message) -> str:
    """Live From mailbox used as SMTP reply recipient (SEC-4)."""
    _, addr = parseaddr(str(message.get(_HEADER_FROM) or ""))
    return addr.strip()


def normalize_inbound(message: Message) -> tuple[str, str, str]:
    """Return ``(sender, subject, body)`` with attachments excluded."""
    return (
        extract_sender_mailbox(message),
        decode_subject(message),
        extract_body(message),
    )
