"""Send and read mail in GreenMail for gateway tests.

Uses blocking stdlib clients; see ``docs/adr/0001-greenmail-sync-imap.md``.
"""

from __future__ import annotations

import imaplib
import smtplib
import time
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.policy import default
from typing import Any

from email_gateway.normalize import extract_body

# Synthetic mailboxes (login:password@domain in GREENMAIL_OPTS).
SUPPORT_EMAIL = "support@example.test"
SUPPORT_PASSWORD = "support-pass"
EMPLOYEE_EMAIL = "employee1@example.test"
EMPLOYEE_PASSWORD = "employee1-pass"
OPERATOR_EMAIL = "operator@example.test"
OPERATOR_PASSWORD = "operator-pass"

# GreenMail standalone test listeners (container-internal).
GREENMAIL_SMTP_PORT = 3025
GREENMAIL_IMAP_PORT = 3143
GREENMAIL_API_PORT = 8080

# Bind all interfaces inside the container (host ports are mapped separately).
_GREENMAIL_BIND_HOST = "0.0.0.0"

# IMAP mailbox and command tokens (RFC 3501).
_IMAP_MAILBOX = "INBOX"
_IMAP_STATUS_OK = "OK"
_IMAP_UID_SEARCH = "SEARCH"
_IMAP_UID_FETCH = "FETCH"
_IMAP_CRITERION_ALL = "ALL"
_IMAP_CRITERION_UNSEEN = "UNSEEN"
# Peek so listing bodies does not set \\Seen (gateway owns that flag).
_IMAP_FETCH_BODY_PEEK = "(BODY.PEEK[])"
_IMAP_STORE_ADD_FLAGS = "+FLAGS"
_IMAP_FLAG_DELETED = r"(\Deleted)"
# imaplib.search charset: None means "not specified" (not UTF-8).
_IMAP_SEARCH_CHARSET_UNSPECIFIED = None
# SEARCH/UID SEARCH: data[0] is the space-separated id blob (empty if none).
_IMAP_SEARCH_BLOB_INDEX = 0
# FETCH: data[0] is (meta, rfc822_bytes); [1] is the message payload.
_IMAP_FETCH_PART_INDEX = 0
_IMAP_FETCH_RFC822_INDEX = 1
_IMAP_UID_ASCII = "ascii"

_ADDR_AT = "@"
# Keep the domain intact when splitting local-part from addr-spec.
_LOCAL_PART_MAXSPLIT = 1

# Default wait_for_inbox_bodies: at least one SMTP-delivered message.
_MIN_INBOX_COUNT = 1


def _format_greenmail_user_spec(email: str, password: str) -> str:
    """Username, password, and domain in GreenMail's users format."""
    local_part, domain = email.split(_ADDR_AT, _LOCAL_PART_MAXSPLIT)
    return f"{local_part}:{password}@{domain}"


GREENMAIL_OPTS = (
    "-Dgreenmail.setup.test.all "
    f"-Dgreenmail.hostname={_GREENMAIL_BIND_HOST} "
    "-Dgreenmail.users="
    f"{_format_greenmail_user_spec(SUPPORT_EMAIL, SUPPORT_PASSWORD)},"
    f"{_format_greenmail_user_spec(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)},"
    f"{_format_greenmail_user_spec(OPERATOR_EMAIL, OPERATOR_PASSWORD)} "
    "-Dgreenmail.verbose"
)

# SMTP submit from the test process (not the gateway's send timeout).
_SMTP_TIMEOUT_SECONDS = 10
# Poll until GreenMail reflects IMAP state after SMTP.
_WAIT_TIMEOUT_SECONDS = 15.0
_WAIT_POLL_SECONDS = 0.2


class GreenMailEndpoints:
    """Host and mapped ports for one running GreenMail container."""

    __slots__ = ("host", "smtp_port", "imap_port")

    def __init__(self, host: str, smtp_port: int, imap_port: int) -> None:
        self.host = host
        self.smtp_port = smtp_port
        self.imap_port = imap_port


def deliver_message(
    greenmail: GreenMailEndpoints,
    message: Message,
    *,
    user: str = EMPLOYEE_EMAIL,
    password: str = EMPLOYEE_PASSWORD,
) -> None:
    """Send ``message`` as ``user`` (employee to support by default)."""
    with smtplib.SMTP(
        greenmail.host,
        greenmail.smtp_port,
        timeout=_SMTP_TIMEOUT_SECONDS,
    ) as smtp:
        _smtp_login(smtp, user, password)
        smtp.send_message(message)


def wait_for_inbox_bodies(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
    *,
    min_count: int = _MIN_INBOX_COUNT,
    timeout: float = _WAIT_TIMEOUT_SECONDS,
) -> list[str]:
    """Wait until the inbox has at least ``min_count`` messages; return text."""
    deadline = time.monotonic() + timeout
    inbox_bodies_so_far: list[str] = []
    while time.monotonic() < deadline:
        inbox_bodies_so_far = list_inbox_bodies(greenmail, user, password)
        if len(inbox_bodies_so_far) >= min_count:
            return inbox_bodies_so_far
        time.sleep(_WAIT_POLL_SECONDS)
    raise AssertionError(
        f"timed out waiting for {min_count} inbox messages, "
        f"last={len(inbox_bodies_so_far)}"
    )


def wait_for_unseen(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
    *,
    timeout: float = _WAIT_TIMEOUT_SECONDS,
) -> int:
    """Wait until there is unread mail; return how many unread ids."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        unseen_count = len(list_unseen_uids(greenmail, user, password))
        if unseen_count:
            return unseen_count
        time.sleep(_WAIT_POLL_SECONDS)
    raise AssertionError("timed out waiting for UNSEEN mail")


def list_inbox_messages(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
) -> list[Message]:
    """Parsed inbox messages, without marking them read."""
    client = imap_login(greenmail, user, password)
    try:
        client.select(_IMAP_MAILBOX)
        # Charset omitted: ALL is ASCII (avoids imaplib charset=None stubs).
        status, data = client.uid(_IMAP_UID_SEARCH, _IMAP_CRITERION_ALL)
        uids = _parse_search_ids(status, data)
        messages: list[Message] = []
        for uid in uids:
            status, fetched = client.uid(
                _IMAP_UID_FETCH,
                uid,
                _IMAP_FETCH_BODY_PEEK,
            )
            assert status == _IMAP_STATUS_OK
            rfc822_bytes = _read_rfc822_from_fetch(fetched)
            messages.append(
                BytesParser(policy=default).parsebytes(rfc822_bytes)
            )
        return messages
    finally:
        client.logout()


def list_inbox_bodies(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
) -> list[str]:
    """Text of every inbox message, without marking them read."""
    return [
        extract_body(parsed)
        for parsed in list_inbox_messages(greenmail, user, password)
    ]


def list_unseen_uids(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
) -> list[str]:
    """Ids of messages that are not marked read."""
    client = imap_login(greenmail, user, password)
    try:
        client.select(_IMAP_MAILBOX)
        status, data = client.uid(_IMAP_UID_SEARCH, _IMAP_CRITERION_UNSEEN)
        return _parse_search_ids(status, data)
    finally:
        client.logout()


def make_text_mail(
    *,
    subject: str,
    body: str,
    from_addr: str = EMPLOYEE_EMAIL,
    to_addr: str = SUPPORT_EMAIL,
) -> EmailMessage:
    """A plain-text message from employee to support unless overridden."""
    message = EmailMessage()
    message["From"] = from_addr
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(body)
    return message


def purge_inbox(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
) -> None:
    """Delete every inbox message for ``user``."""
    client = imap_login(greenmail, user, password)
    try:
        client.select(_IMAP_MAILBOX)
        status, data = client.search(
            _IMAP_SEARCH_CHARSET_UNSPECIFIED,
            _IMAP_CRITERION_ALL,
        )
        for sequence in _parse_search_ids(status, data):
            client.store(sequence, _IMAP_STORE_ADD_FLAGS, _IMAP_FLAG_DELETED)
        client.expunge()
    finally:
        client.logout()


def imap_login(
    greenmail: GreenMailEndpoints,
    user: str,
    password: str,
) -> imaplib.IMAP4:
    """Log in; if the full address fails, retry with the part before ``@``."""
    client = imaplib.IMAP4(greenmail.host, greenmail.imap_port)
    try:
        client.login(user, password)
    except imaplib.IMAP4.error:
        client.login(_parse_local_part(user), password)
    return client


def _read_search_id_blob(status: str, data: list[Any] | None) -> bytes | None:
    """Raw search-id bytes, or None if the mailbox had no matches."""
    if status != _IMAP_STATUS_OK or not data:
        return None
    blob = data[_IMAP_SEARCH_BLOB_INDEX]
    if not isinstance(blob, bytes) or not blob:
        return None
    return blob


def _parse_search_ids(status: str, data: list[Any] | None) -> list[str]:
    """Turn a search result into string ids."""
    blob = _read_search_id_blob(status, data)
    if blob is None:
        return []
    return [token.decode(_IMAP_UID_ASCII) for token in blob.split()]


def _read_rfc822_from_fetch(fetched: list[Any]) -> bytes:
    """Pull the raw message bytes out of a fetch result."""
    first_part = fetched[_IMAP_FETCH_PART_INDEX]
    rfc822 = first_part[_IMAP_FETCH_RFC822_INDEX]
    if not isinstance(rfc822, bytes):
        raise TypeError("IMAP FETCH did not return RFC822 bytes")
    return rfc822


def _parse_local_part(user: str) -> str:
    """Username before the first ``@``."""
    return user.split(_ADDR_AT, _LOCAL_PART_MAXSPLIT)[0]


def _smtp_login(smtp: smtplib.SMTP, user: str, password: str) -> None:
    """Log in; if the full address fails, retry with the part before ``@``."""
    try:
        smtp.login(user, password)
    except smtplib.SMTPAuthenticationError:
        smtp.login(_parse_local_part(user), password)
