"""Fetch unread mail, send replies, mark read after a successful send.

This client talks to a generic mailbox. It does not know about GreenMail.
"""

from __future__ import annotations

import imaplib
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.policy import default

from email_gateway import constants
from email_gateway.config import Settings
from email_gateway.logging_config import get_logger
from email_gateway.normalize import normalize_inbound

logger = get_logger(__name__)

# IMAP tokens (RFC 3501). Quoted so they are not mistaken for Python names.
_IMAP_INBOX = "INBOX"
_IMAP_OK = "OK"
# UNSEEN: messages that do not have \Seen. Fetch uses BODY.PEEK so SEARCH
# stays true until we explicitly STORE \Seen after SMTP success.
_IMAP_UNSEEN = "UNSEEN"
_IMAP_ADD_FLAGS = "+FLAGS"
_IMAP_SEEN_FLAG = r"(\Seen)"
# SEARCH: data[0] is the space-separated UID blob (empty if none).
_IMAP_SEARCH_BLOB_INDEX = 0
# FETCH tuple: (meta, rfc822_bytes); payload is index 1.
_IMAP_FETCH_RFC822_INDEX = 1
_IMAP_FETCH_MIN_TUPLE_LEN = 2
_IMAP_UID_ASCII = "ascii"
# BODY.PEEK[] = full RFC822 without implicitly setting \Seen.
_FETCH_RFC822_PEEK = "(BODY.PEEK[])"
# RFC 5322 reply subject prefix (case-insensitive match, canonical "Re:").
_REPLY_PREFIX = "Re:"


@dataclass(frozen=True)
class InboundMessage:
    """One inbound message after normalize, plus the mailbox id for later."""

    uid: str
    sender: str
    subject: str
    body: str


class Client:
    """Fetch unread mail, send a reply, mark read after a successful send."""

    def __init__(self, settings: Settings) -> None:
        """Store host settings. Each public method opens its own connection."""
        self._settings = settings

    def fetch_unseen(self) -> list[InboundMessage]:
        """Load unread messages without marking them read."""
        client = self._imap_connect()
        try:
            _select_inbox(client)
            uids = _search_unseen_uids(client)
            inbound_messages: list[InboundMessage] = []
            for uid in uids:
                rfc822_bytes = _fetch_rfc822(client, uid)
                parsed: Message = BytesParser(policy=default).parsebytes(
                    rfc822_bytes
                )
                sender, subject, body = normalize_inbound(parsed)
                inbound_messages.append(
                    InboundMessage(
                        uid=uid,
                        sender=sender,
                        subject=subject,
                        body=body,
                    )
                )
            return inbound_messages
        finally:
            _imap_logout(client)

    def mark_seen(self, uid: str) -> None:
        """Mark this message read. Call only after the reply was sent.

        That flag is a local mailbox hint, not proof the recipient got mail.
        """
        client = self._imap_connect()
        try:
            _select_inbox(client)
            client.uid("STORE", uid, _IMAP_ADD_FLAGS, _IMAP_SEEN_FLAG)
        finally:
            _imap_logout(client)

    def send_reply(self, *, to_addr: str, subject: str, body: str) -> bool:
        """Send a reply to ``to_addr``. Return True if the server accepted."""
        if not to_addr:
            logger.warning(
                "smtp_skip_no_recipient", extra={"skip_reason": "no_sender"}
            )
            return False
        outgoing = EmailMessage()
        outgoing["From"] = self._settings.smtp_user
        outgoing["To"] = to_addr
        outgoing["Subject"] = _format_reply_subject(subject)
        outgoing.set_content(body)
        try:
            with smtplib.SMTP(
                self._settings.smtp_host,
                self._settings.smtp_port,
                timeout=constants.SMTP_TIMEOUT_SECONDS,
            ) as smtp:
                _smtp_login(
                    smtp,
                    self._settings.smtp_user,
                    self._settings.smtp_password,
                )
                smtp.send_message(outgoing)
        except (OSError, smtplib.SMTPException) as exc:
            logger.exception(
                "smtp_send_failed",
                extra={"exc_type": type(exc).__name__},
            )
            return False
        logger.info("smtp_sent")
        return True

    def _imap_connect(self) -> imaplib.IMAP4:
        """Connect and log in. The caller must log out."""
        client = imaplib.IMAP4(
            self._settings.imap_host, self._settings.imap_port
        )
        _imap_login(
            client, self._settings.imap_user, self._settings.imap_password
        )
        return client


def _format_reply_subject(subject: str) -> str:
    """Add ``Re:`` unless the subject already starts with it."""
    stripped = subject.strip()
    if stripped.lower().startswith(_REPLY_PREFIX.lower()):
        return stripped
    return f"{_REPLY_PREFIX} {stripped}" if stripped else _REPLY_PREFIX


def _parse_local_part(user: str) -> str:
    """Username before the first ``@``.

    Some servers reject a full address at login and want this part only.
    """
    return user.split("@", 1)[0]


def _imap_login(client: imaplib.IMAP4, user: str, password: str) -> None:
    """Log in; if the full address fails, retry with the part before ``@``."""
    try:
        client.login(user, password)
    except imaplib.IMAP4.error as exc:
        if "@" not in user:
            # No "@": retry local-part would be the same string as ``user``.
            raise
        logger.warning(
            "imap_login_retry_local_part",
            extra={"exc_type": type(exc).__name__},
        )
        client.login(_parse_local_part(user), password)


def _smtp_login(smtp: smtplib.SMTP, user: str, password: str) -> None:
    """Log in; if the full address fails, retry with the part before ``@``."""
    try:
        smtp.login(user, password)
    except smtplib.SMTPAuthenticationError as exc:
        if "@" not in user:
            # No "@": retry local-part would be the same string as ``user``.
            raise
        logger.warning(
            "smtp_login_retry_local_part",
            extra={"exc_type": type(exc).__name__},
        )
        smtp.login(_parse_local_part(user), password)


def _select_inbox(client: imaplib.IMAP4) -> None:
    """Open the inbox. Raise if the server refuses."""
    status, _ = client.select(_IMAP_INBOX)
    if status != _IMAP_OK:
        raise RuntimeError("imap_select_failed")


def _search_unseen_uids(client: imaplib.IMAP4) -> list[str]:
    """Return ids of messages that are not marked read."""
    status, data = client.uid("SEARCH", _IMAP_UNSEEN)
    if status != _IMAP_OK or not data or data[_IMAP_SEARCH_BLOB_INDEX] is None:
        return []
    uid_list_bytes = data[_IMAP_SEARCH_BLOB_INDEX]
    if not uid_list_bytes:
        return []
    return [
        token.decode(_IMAP_UID_ASCII)
        for token in uid_list_bytes.split()
        if token
    ]


def _fetch_rfc822(client: imaplib.IMAP4, uid: str) -> bytes:
    """Download the full message for this UID without marking it read."""
    status, data = client.uid("FETCH", uid, _FETCH_RFC822_PEEK)
    if status != _IMAP_OK or not data:
        raise RuntimeError("imap_fetch_failed")
    for item in data:
        if isinstance(item, tuple) and len(item) >= _IMAP_FETCH_MIN_TUPLE_LEN:
            payload = item[_IMAP_FETCH_RFC822_INDEX]
            if isinstance(payload, bytes):
                return payload
    raise RuntimeError("imap_fetch_empty")


def _imap_logout(client: imaplib.IMAP4) -> None:
    """Log out. Ignore it if the connection already dropped."""
    try:
        client.logout()
    except OSError as exc:
        logger.warning(
            "imap_logout_failed",
            extra={"exc_type": type(exc).__name__},
            exc_info=True,
        )
