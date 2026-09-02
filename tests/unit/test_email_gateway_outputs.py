"""Unit tests for blocking End outputs and source filename checks."""

import pytest

from email_gateway import constants
from email_gateway.config import build_authorization_header
from email_gateway.outputs import OutputsError, parse_outputs

# Same prefix as tests/integration/testdata.py.
_CITATION_URL_BASE = (
    "https://github.com/example/helpdesk/blob/main/knowledge_base/"
)
_APP_KEY = "app-xxx"
_BEARER_APP_KEY = f"Bearer {_APP_KEY}"
_REPLY_HELLO = "hello"
_REPLY_OK = "ok"
_SOURCE_FILENAME = "vpn-access.md"
_SOURCE_FILENAME_NESTED = "../secret.md"
_TICKET_ID = "t-1"
_WORKFLOW_STATUS_SUCCEEDED = "succeeded"


def test_authorization_does_not_double_bearer() -> None:
    """Existing Bearer prefix is kept; a bare key gets Bearer added."""
    assert build_authorization_header(_BEARER_APP_KEY) == _BEARER_APP_KEY
    assert build_authorization_header(f"'{_BEARER_APP_KEY}'") == _BEARER_APP_KEY
    assert build_authorization_header(_APP_KEY) == _BEARER_APP_KEY


def test_parse_outputs_requires_reply_text() -> None:
    """Missing End reply_text is malformed."""
    with pytest.raises(OutputsError):
        parse_outputs(
            {"data": {"status": _WORKFLOW_STATUS_SUCCEEDED, "outputs": {}}},
            citation_url_base=_CITATION_URL_BASE,
        )


def test_parse_outputs_accepts_ticket_id() -> None:
    """Optional End ticket_id is kept and appended to the SMTP body."""
    result = parse_outputs(
        {
            "data": {
                "status": _WORKFLOW_STATUS_SUCCEEDED,
                "outputs": {
                    "reply_text": _REPLY_OK,
                    "ticket_id": _TICKET_ID,
                },
            }
        },
        citation_url_base=_CITATION_URL_BASE,
    )
    assert result.ticket_id == _TICKET_ID
    assert result.source_filenames == []
    assert result.reply_text.startswith(_REPLY_OK)
    assert constants.TICKET_ID_HEADING in result.reply_text
    assert _TICKET_ID in result.reply_text


def test_parse_outputs_empty_source_filenames_ok() -> None:
    """Empty source_filenames is a KB miss, not a validation error."""
    result = parse_outputs(
        {
            "data": {
                "status": _WORKFLOW_STATUS_SUCCEEDED,
                "outputs": {
                    "reply_text": _REPLY_HELLO,
                    "source_filenames": [],
                },
            }
        },
        citation_url_base=_CITATION_URL_BASE,
    )
    assert result.reply_text == _REPLY_HELLO
    assert result.ticket_id is None
    assert result.source_filenames == []


def test_parse_outputs_source_filenames_list() -> None:
    """A list of filenames becomes a Sources footer of citation URLs."""
    result = parse_outputs(
        {
            "data": {
                "status": _WORKFLOW_STATUS_SUCCEEDED,
                "outputs": {
                    "reply_text": _REPLY_OK,
                    "source_filenames": [_SOURCE_FILENAME],
                },
            }
        },
        citation_url_base=_CITATION_URL_BASE,
    )
    citation_url = f"{_CITATION_URL_BASE}{_SOURCE_FILENAME}"
    assert result.source_filenames == [_SOURCE_FILENAME]
    assert result.reply_text.startswith(_REPLY_OK)
    assert constants.CITATION_SOURCES_HEADING in result.reply_text
    assert citation_url in result.reply_text


def test_parse_outputs_skips_sources_on_knowledge_gap_miss() -> None:
    """A knowledge-gap reply skips Sources even when filenames are set."""
    mixed_marker = constants.KNOWLEDGE_GAP_REPLY_MARKER.swapcase()
    payload = {
        "data": {
            "status": _WORKFLOW_STATUS_SUCCEEDED,
            "outputs": {
                "reply_text": mixed_marker,
                "ticket_id": _TICKET_ID,
                "source_filenames": [_SOURCE_FILENAME],
            },
        }
    }
    result = parse_outputs(payload, citation_url_base=_CITATION_URL_BASE)
    citation_url = f"{_CITATION_URL_BASE}{_SOURCE_FILENAME}"
    assert result.ticket_id == _TICKET_ID
    assert result.source_filenames == [_SOURCE_FILENAME]
    assert constants.CITATION_SOURCES_HEADING not in result.reply_text
    assert citation_url not in result.reply_text
    assert constants.TICKET_ID_HEADING in result.reply_text
    assert _TICKET_ID in result.reply_text
    parse_outputs(payload, citation_url_base="")


def test_parse_outputs_empty_base_rejects_filenames() -> None:
    """Non-empty source_filenames require a configured URL prefix."""
    with pytest.raises(OutputsError):
        parse_outputs(
            {
                "data": {
                    "status": _WORKFLOW_STATUS_SUCCEEDED,
                    "outputs": {
                        "reply_text": _REPLY_OK,
                        "source_filenames": [_SOURCE_FILENAME],
                    },
                }
            },
            citation_url_base="",
        )


def test_parse_outputs_rejects_nested_source_filename() -> None:
    """A nested path or URL is not a knowledge_base filename."""
    with pytest.raises(OutputsError):
        parse_outputs(
            {
                "data": {
                    "status": _WORKFLOW_STATUS_SUCCEEDED,
                    "outputs": {
                        "reply_text": _REPLY_OK,
                        "source_filenames": [_SOURCE_FILENAME_NESTED],
                    },
                }
            },
            citation_url_base=_CITATION_URL_BASE,
        )


def test_parse_outputs_rejects_nested_filename_on_knowledge_gap() -> None:
    """Invalid filenames still fail when reply_text is a knowledge-gap miss."""
    mixed_marker = constants.KNOWLEDGE_GAP_REPLY_MARKER.swapcase()
    with pytest.raises(OutputsError):
        parse_outputs(
            {
                "data": {
                    "status": _WORKFLOW_STATUS_SUCCEEDED,
                    "outputs": {
                        "reply_text": mixed_marker,
                        "source_filenames": [_SOURCE_FILENAME_NESTED],
                    },
                }
            },
            citation_url_base=_CITATION_URL_BASE,
        )
