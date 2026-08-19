"""Validate blocking ``data.outputs``; reject citations outside repo base.

Flow: ``parse_outputs`` reads the Service API JSON, requires a non-empty
``reply_text``, rejects a non-string ``ticket_id``, optionally takes
``citations``, then checks citation URLs are under the configured
repository prefix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Service API JSON keys (blocking ``/v1/workflows/run`` body).
_KEY_DATA = "data"
_KEY_STATUS = "status"
_KEY_OUTPUTS = "outputs"
_KEY_REPLY_TEXT = "reply_text"
_KEY_TICKET_ID = "ticket_id"
_KEY_CITATIONS = "citations"
# Dify marks a finished graph this way; other values are a failed run.
_STATUS_SUCCEEDED = "succeeded"

# Stable OutputsError messages (logged; SMTP then uses static ack).
_ERR_CITATIONS_NOT_JSON = "citations_not_json"
_ERR_CITATIONS_NOT_LIST = "citations_not_list"
_ERR_CITATION_NOT_STRING = "citation_not_string"
_ERR_CITATION_BASE_EMPTY = "citation_base_empty"
_ERR_CITATION_OUTSIDE_BASE = "citation_outside_base"
_ERR_MISSING_DATA = "missing_data"
_ERR_WORKFLOW_NOT_SUCCEEDED = "workflow_not_succeeded"
_ERR_MISSING_OUTPUTS = "missing_outputs"
_ERR_MISSING_REPLY_TEXT = "missing_reply_text"
_ERR_TICKET_ID_NOT_STRING = "ticket_id_not_string"


@dataclass(frozen=True)
class ValidatedOutputs:
    """Trusted End fields the gateway consumes after schema checks."""

    reply_text: str
    citations: list[str] = field(default_factory=list)


class OutputsError(ValueError):
    """Missing or malformed End outputs (static-ack path)."""


def _parse_citation_urls(raw: Any) -> list[str]:
    """Normalize End ``citations`` to a list of non-empty URL strings.

    Omitted or empty is a KB miss (no citations). A JSON string is allowed
    when the End node cannot emit a list. Anything else is malformed.
    """
    if raw is None or raw == "":
        return []
    value: Any = raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OutputsError(_ERR_CITATIONS_NOT_JSON) from exc
    if not isinstance(value, list):
        raise OutputsError(_ERR_CITATIONS_NOT_LIST)
    urls: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise OutputsError(_ERR_CITATION_NOT_STRING)
        urls.append(item.strip())
    return urls


def _require_urls_under_repo_base(urls: list[str], repo_base: str) -> None:
    """Require every URL to start with the configured repository prefix."""
    if not urls:
        return
    base = repo_base.strip()
    if not base:
        raise OutputsError(_ERR_CITATION_BASE_EMPTY)
    for url in urls:
        if not url.startswith(base):
            raise OutputsError(_ERR_CITATION_OUTSIDE_BASE)


def parse_outputs(
    payload: dict[str, Any],
    *,
    citation_repo_base: str,
) -> ValidatedOutputs:
    """Require ``data.outputs.reply_text``; optional citations."""
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
    if ticket_raw not in (None, "") and not isinstance(ticket_raw, str):
        raise OutputsError(_ERR_TICKET_ID_NOT_STRING)
    citations = _parse_citation_urls(outputs.get(_KEY_CITATIONS))
    _require_urls_under_repo_base(citations, citation_repo_base)
    return ValidatedOutputs(reply_text=reply, citations=citations)
