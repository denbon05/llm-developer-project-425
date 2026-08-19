"""Unit tests for blocking End outputs and citation prefix checks."""

import pytest

from email_gateway.config import build_authorization_header
from email_gateway.outputs import OutputsError, parse_outputs

# Same allow-list prefix as tests/integration/testdata.py.
_CITATION_REPO_BASE = (
    "https://github.com/example/helpdesk/blob/main/knowledge_base/"
)
_APP_KEY = "app-xxx"
_BEARER_APP_KEY = f"Bearer {_APP_KEY}"
_REPLY_HELLO = "hello"
_REPLY_OK = "ok"
_CITATION_OUTSIDE_BASE = "https://evil.example/x"
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
            citation_repo_base=_CITATION_REPO_BASE,
        )


def test_parse_outputs_empty_citations_ok() -> None:
    """Empty citations is a KB miss, not a validation error."""
    result = parse_outputs(
        {
            "data": {
                "status": _WORKFLOW_STATUS_SUCCEEDED,
                "outputs": {"reply_text": _REPLY_HELLO, "citations": []},
            }
        },
        citation_repo_base=_CITATION_REPO_BASE,
    )
    assert result.reply_text == _REPLY_HELLO
    assert result.citations == []


def test_parse_outputs_json_string_citations() -> None:
    """End may emit citations as a JSON string when it cannot emit a list."""
    url = f"{_CITATION_REPO_BASE}vpn.md"
    result = parse_outputs(
        {
            "data": {
                "status": _WORKFLOW_STATUS_SUCCEEDED,
                "outputs": {
                    "reply_text": _REPLY_OK,
                    "citations": f'["{url}"]',
                },
            }
        },
        citation_repo_base=_CITATION_REPO_BASE,
    )
    assert result.citations == [url]


def test_parse_outputs_rejects_citation_outside_base() -> None:
    """A URL that does not start with the repo prefix is rejected."""
    with pytest.raises(OutputsError):
        parse_outputs(
            {
                "data": {
                    "status": _WORKFLOW_STATUS_SUCCEEDED,
                    "outputs": {
                        "reply_text": _REPLY_OK,
                        "citations": [_CITATION_OUTSIDE_BASE],
                    },
                }
            },
            citation_repo_base=_CITATION_REPO_BASE,
        )
