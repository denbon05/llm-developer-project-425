"""Inbound mail → sender, subject, body. Attachments are ignored.

Flow: ``normalize_inbound`` reads From and Subject, then ``extract_body``
walks MIME parts (plain preferred, else HTML). HTML goes through
``sanitize_html`` / ``_TextExtractor``: skip script/style, break on block
tags, prefix ``<blockquote>`` lines with ``>``, then strip leftover markup.
The processor splits the full body into ``request_text`` / ``blockquote``
for Dify; intake still uses the full body.
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
# HTML quote wrapper; inner visible text is emitted as ``>``-prefixed lines.
_BLOCKQUOTE_TAG = "blockquote"
# Block-ish tags become a newline so paragraphs do not run together.
_BREAK_TAGS = frozenset(
    {
        "p",
        "div",
        "br",
        "tr",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "hr",
        _BLOCKQUOTE_TAG,
    }
)
# Leftover markup after the parser (e.g. undeclared tags).
_TAG_RE = re.compile(r"<[^>]+>")
# Visible-text separators after dropping tags.
_BLOCK_BREAK = "\n"
_TAG_PLACEHOLDER = " "
# Unclosed skip-tag nesting; 0 means we are collecting visible text.
_SKIP_DEPTH_NONE = 0
# Unclosed <blockquote> nesting; 0 means text is not HTML-quoted.
_BLOCKQUOTE_DEPTH_NONE = 0
# First line whose stripped form starts with this begins the quoted remainder.
_QUOTE_PREFIX = ">"
# Prefix written at the start of each HTML-blockquote line (space after ``>``).
_QUOTE_LINE_PREFIX = f"{_QUOTE_PREFIX} "
# Thunderbird/Gmail attribution; that line and everything after is quoted.
_ATTRIBUTION_RE = re.compile(r"^On .+ wrote:\s*$", re.IGNORECASE)

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
    Inside ``<blockquote>``, each visible line is prefixed with ``>`` so the
    one body splitter can treat HTML quotes like plain replies.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = _SKIP_DEPTH_NONE
        self._blockquote_depth = _BLOCKQUOTE_DEPTH_NONE
        self._is_quote_line_start = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Open a tag: maybe start skipping, maybe insert a block break."""
        lowered = tag.lower()
        # Later handle_data is dropped until matching end tags close this.
        if lowered in _SKIP_TAGS:
            self._skip_depth += 1
        # Keep adjacent blocks from concatenating into one line.
        if lowered in _BREAK_TAGS:
            self._chunks.append(_BLOCK_BREAK)
            if self._blockquote_depth or lowered == _BLOCKQUOTE_TAG:
                self._is_quote_line_start = True
        if lowered == _BLOCKQUOTE_TAG:
            self._blockquote_depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Close skip/quote tags; extra closes must not drive depth negative."""
        lowered = tag.lower()
        if lowered in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if lowered == _BLOCKQUOTE_TAG and self._blockquote_depth:
            self._blockquote_depth -= 1
            if self._blockquote_depth == _BLOCKQUOTE_DEPTH_NONE:
                self._is_quote_line_start = False

    def handle_data(self, data: str) -> None:
        """Collect text nodes unless we are inside script/style."""
        if self._skip_depth:
            return
        if not self._blockquote_depth:
            self._chunks.append(data)
            return
        self._chunks.append(self._prefix_quote_lines(data))

    def _prefix_quote_lines(self, data: str) -> str:
        """Prefix ``>`` at line starts so inline HTML stays one quote line."""
        fragments = data.split(_BLOCK_BREAK)
        prefixed: list[str] = []
        for index, fragment in enumerate(fragments):
            if index:
                prefixed.append(_BLOCK_BREAK)
                self._is_quote_line_start = True
            if not fragment:
                continue
            if self._is_quote_line_start:
                stripped = fragment.lstrip()
                if stripped:
                    if not stripped.startswith(_QUOTE_PREFIX):
                        fragment = f"{_QUOTE_LINE_PREFIX}{stripped}"
                    self._is_quote_line_start = False
            prefixed.append(fragment)
        return "".join(prefixed)

    def extract_text(self) -> str:
        """Join full-document chunks, drop leftover tags, collapse blanks."""
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


def _is_quote_boundary_line(line: str) -> bool:
    """True when this line starts a quoted remainder (``>`` or On/wrote)."""
    stripped = line.strip()
    if stripped.startswith(_QUOTE_PREFIX):
        return True
    return _ATTRIBUTION_RE.fullmatch(stripped) is not None


def split_quoted_body(body: str) -> tuple[str, str]:
    """Split a plain body into latest unquoted text and the quoted remainder.

    The first ``>`` line or ``On ... wrote:`` attribution starts the quote.
    That line and everything after (prefixes kept) is ``blockquote``. Text
    before it is ``request_text``. Empty unquoted text falls back to the
    full body and an empty blockquote so retrieval never gets an empty query.
    """
    lines = body.splitlines()
    quote_index: int | None = None
    for index, line in enumerate(lines):
        if _is_quote_boundary_line(line):
            quote_index = index
            break
    if quote_index is None:
        return body.strip(), ""
    request_text = _BLOCK_BREAK.join(lines[:quote_index]).strip()
    blockquote = _BLOCK_BREAK.join(lines[quote_index:])
    if not request_text:
        return body.strip(), ""
    return request_text, blockquote


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
        return sanitize_html(_BLOCK_BREAK.join(html_parts))
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
