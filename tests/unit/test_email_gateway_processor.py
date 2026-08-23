"""Unit tests for mapping Dify CallResult onto SMTP bodies."""

from email_gateway.clients.dify import CallResult
from email_gateway.outputs import ValidatedOutputs
from email_gateway.processor import build_outbound_from_workflow

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
