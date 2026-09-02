"""Validate blocking ``data.outputs``; append ticket and Sources footers.

Flow: ``parse_outputs`` reads the Service API JSON, requires a non-empty
``reply_text``, accepts optional ``ticket_id`` and ``source_filenames``,
then appends those onto the SMTP body. Sources are omitted when
``reply_text`` contains the knowledge-gap marker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from email_gateway import constants

# Service API JSON keys (blocking ``/v1/workflows/run`` body).
_KEY_DATA = "data"
_KEY_STATUS = "status"
_KEY_OUTPUTS = "outputs"
_KEY_REPLY_TEXT = "reply_text"
_KEY_TICKET_ID = "ticket_id"
_KEY_SOURCE_FILENAMES = "source_filenames"
# Dify marks a finished graph this way; other values are a failed run.
_STATUS_SUCCEEDED = "succeeded"
_DOT_PATH_SEGMENTS = frozenset({".", ".."})

# Stable OutputsError messages (logged; not SMTP body text).
_ERR_SOURCE_FILENAMES_INVALID = "source_filenames_invalid"
_ERR_CITATION_URL_BASE_EMPTY = "citation_url_base_empty"
_ERR_MISSING_DATA = "missing_data"
_ERR_WORKFLOW_NOT_SUCCEEDED = "workflow_not_succeeded"
_ERR_MISSING_OUTPUTS = "missing_outputs"
_ERR_MISSING_REPLY_TEXT = "missing_reply_text"
_ERR_TICKET_ID_NOT_STRING = "ticket_id_not_string"


@dataclass(frozen=True)
class ValidatedOutputs:
    """Trusted End fields the gateway consumes after schema checks."""

    reply_text: str
    ticket_id: str | None = None
    source_filenames: list[str] = field(default_factory=list)


class OutputsError(ValueError):
    """Missing or malformed End outputs."""


def _is_source_filename(name: str) -> bool:
    """True when ``name`` is a single path segment, not a URL or nested path."""
    if name in _DOT_PATH_SEGMENTS:
        return False
    return "/" not in name and "\\" not in name


def _parse_source_filenames(raw: Any) -> list[str]:
    """Read End ``source_filenames``; omitted/null/non-list is an empty list."""
    if not isinstance(raw, list):
        return []
    filenames: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise OutputsError(_ERR_SOURCE_FILENAMES_INVALID)
        name = item.strip()
        if not _is_source_filename(name):
            raise OutputsError(_ERR_SOURCE_FILENAMES_INVALID)
        filenames.append(name)
    return filenames


def is_knowledge_gap_miss(reply_text: str) -> bool:
    """True when End ``reply_text`` contains the knowledge-gap marker."""
    return (
        constants.KNOWLEDGE_GAP_REPLY_MARKER.casefold() in reply_text.casefold()
    )


def _build_smtp_body(
    reply_text: str,
    ticket_id: str | None,
    filenames: list[str],
    url_base: str,
) -> str:
    """Append Ticket and Sources blocks when those End fields are set."""
    parts = [reply_text.rstrip()]
    if ticket_id is not None:
        parts.append(f"{constants.TICKET_ID_HEADING} {ticket_id}")
    if filenames and not is_knowledge_gap_miss(reply_text):
        base = url_base.strip()
        if not base:
            raise OutputsError(_ERR_CITATION_URL_BASE_EMPTY)
        urls = [f"{base}{name}" for name in filenames]
        parts.append("\n".join([constants.CITATION_SOURCES_HEADING, *urls]))
    return "\n\n".join(parts)


def parse_outputs(
    payload: dict[str, Any],
    *,
    citation_url_base: str,
) -> ValidatedOutputs:
    """Require ``data.outputs.reply_text``; optional ticket and filenames."""
    data = payload.get(_KEY_DATA)
    if not isinstance(data, dict):
        raise OutputsError(_ERR_MISSING_DATA)
    status = data.get(_KEY_STATUS)
    # Absent status: still accept outputs (some fakes omit it).
    if status is not None and status != _STATUS_SUCCEEDED:
        raise OutputsError(_ERR_WORKFLOW_NOT_SUCCEEDED)
    outputs = data.get(_KEY_OUTPUTS)
    if not isinstance(outputs, dict):
        raise OutputsError(_ERR_MISSING_OUTPUTS)
    reply = outputs.get(_KEY_REPLY_TEXT)
    if not isinstance(reply, str) or not reply.strip():
        raise OutputsError(_ERR_MISSING_REPLY_TEXT)
    ticket_raw = outputs.get(_KEY_TICKET_ID)
    if ticket_raw in (None, ""):
        ticket_id = None
    elif isinstance(ticket_raw, str):
        ticket_id = ticket_raw
    else:
        raise OutputsError(_ERR_TICKET_ID_NOT_STRING)
    filenames = _parse_source_filenames(outputs.get(_KEY_SOURCE_FILENAMES))
    reply_text = _build_smtp_body(
        reply, ticket_id, filenames, citation_url_base
    )
    return ValidatedOutputs(
        reply_text=reply_text,
        ticket_id=ticket_id,
        source_filenames=filenames,
    )
