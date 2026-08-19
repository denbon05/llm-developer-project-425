"""Unit tests for mapping Dify CallResult onto SMTP bodies."""

from email_gateway import constants
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
    reply = build_outbound_from_workflow(
        result, static_ack=constants.STATIC_ACK_TEXT
    )
    assert reply.source == "workflow_outputs"
    assert reply.text == _WORKFLOW_REPLY
    assert reply.workflow_run_id == _WORKFLOW_RUN_ID


def test_build_outbound_from_workflow_outage_uses_static_ack() -> None:
    """Failed workflow maps to the static acknowledgement, not inbound text."""
    result = CallResult(
        ok=False,
        outputs=None,
        workflow_run_id=None,
    )
    reply = build_outbound_from_workflow(
        result, static_ack=constants.STATIC_ACK_TEXT
    )
    assert reply.source == "static_ack"
    assert reply.text == constants.STATIC_ACK_TEXT
