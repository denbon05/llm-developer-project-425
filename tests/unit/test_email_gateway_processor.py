"""Unit tests for mapping Dify CallResult onto SMTP bodies."""

from http import HTTPStatus

from email_gateway.clients.dify import CallResult
from email_gateway.outputs import ValidatedOutputs
from email_gateway.processor import (
    build_outbound_from_workflow,
    is_retryable_workflow_failure,
)

_WORKFLOW_REPLY = "grounded answer"
_WORKFLOW_RUN_ID = "wf-1"


def test_build_outbound_from_workflow_uses_end_reply_text() -> None:
    """Succeeded End outputs become the SMTP body."""
    result = CallResult(
        ok=True,
        outputs=ValidatedOutputs(reply_text=_WORKFLOW_REPLY),
        workflow_run_id=_WORKFLOW_RUN_ID,
    )
    reply = build_outbound_from_workflow(result)
    assert reply is not None
    assert reply.source == "workflow_outputs"
    assert reply.text == _WORKFLOW_REPLY
    assert reply.workflow_run_id == _WORKFLOW_RUN_ID


def test_build_outbound_from_workflow_failure_returns_none() -> None:
    """A failed ``CallResult`` yields ``None`` (no outbound body)."""
    result = CallResult(ok=False, outputs=None, workflow_run_id=None)
    assert build_outbound_from_workflow(result) is None


def test_retryable_http_error_and_5xx() -> None:
    """Transport misses and 5xx/429/408 are retried; other 4xx are not."""
    transport_miss = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=None,
        fail_reason="http_error",
    )
    server_error = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=None,
        fail_reason="http_status",
        http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )
    rate_limited = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=None,
        fail_reason="http_status",
        http_status=HTTPStatus.TOO_MANY_REQUESTS,
    )
    request_timeout = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=None,
        fail_reason="http_status",
        http_status=HTTPStatus.REQUEST_TIMEOUT,
    )
    not_found = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=None,
        fail_reason="http_status",
        http_status=HTTPStatus.NOT_FOUND,
    )
    bad_outputs = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=_WORKFLOW_RUN_ID,
        fail_reason="outputs_invalid",
    )
    assert is_retryable_workflow_failure(transport_miss)
    assert is_retryable_workflow_failure(server_error)
    assert is_retryable_workflow_failure(rate_limited)
    assert is_retryable_workflow_failure(request_timeout)
    assert not is_retryable_workflow_failure(not_found)
    assert not is_retryable_workflow_failure(bad_outputs)
