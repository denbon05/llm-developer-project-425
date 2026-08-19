"""GreenMail + fake Dify proofs for the Phase 4 email gateway."""

from __future__ import annotations

import json
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from http import HTTPStatus
from typing import Any

import httpx
import pytest

from email_gateway import constants
from email_gateway.config import Settings
from email_gateway.processor import Processor
from privacy import constants as privacy_constants

from .greenmail import (
    EMPLOYEE_EMAIL,
    EMPLOYEE_PASSWORD,
    SUPPORT_EMAIL,
    SUPPORT_PASSWORD,
    GreenMailEndpoints,
    deliver_message,
    list_unseen_uids,
    make_text_mail,
    wait_for_inbox_bodies,
    wait_for_unseen,
)
from .testdata import (
    DIFY_APP_KEY,
    INPUT_REQUEST_TEXT,
    INPUT_SUBJECT,
    INPUT_USER_EMAIL,
    PII_CARD,
    PII_EMAIL_IN_BODY,
    PII_EMAIL_IN_SUBJECT,
    PII_PHONE,
    RESPONSE_MODE_BLOCKING,
    START_INPUT_KEYS,
)

# One UNSEEN inbound → one blocking POST (happy path).
_ONE_WORKFLOW_CALL = 1
# First cycle skipped \\Seen; second cycle treats the same UID as new work.
_DUPLICATE_WINDOW_WORKFLOW_CALLS = 2
# Same mail SMTP-replied twice in the duplicate-window proof.
_DUPLICATE_WINDOW_SMTP_REPLIES = 2

# Bytes/filename that must not appear in Dify request_text.
_ATTACHMENT_BYTES = b"SECRET_ATTACHMENT_BYTES"
_ATTACHMENT_FILENAME = "secret.bin"

# Echoed inbound bodies that SMTP must (or must not) round-trip.
_VPN_BODY = "please enable vpn"
_RESTART_BODY = "still unseen"
_DUPLICATE_BODY = "duplicate window"
_OUTAGE_BODY = "please help"
_MALFORMED_BODY = "need an answer"
_CITE_BODY = "docs question"
_GREETING_BODY = "Hi there!"
_TOXIC_TERM = constants.TOXICITY_TERMS[0]
_TOXIC_BODY = f"you {_TOXIC_TERM}, fix the vpn"

# Workflow End text that must not be SMTP-sent when citations fail.
_REJECTED_WORKFLOW_REPLY = "should not send"
# URL outside citation_repo_base (testdata.CITATION_REPO_BASE).
_CITATION_OUTSIDE_BASE = "https://evil.example/kb/x.md"


class FakeDify:
    """httpx MockTransport for blocking ``POST …/v1/workflows/run``.

    Modes: echo (reply_text = request_text), http_error (HTTP 500),
    missing_reply (empty outputs), bad_citations (URL off repo base).
    """

    MODE_ECHO = "echo"
    MODE_HTTP_ERROR = "http_error"
    MODE_MISSING_REPLY = "missing_reply"
    MODE_BAD_CITATIONS = "bad_citations"

    mode: str
    requests: list[httpx.Request]

    def __init__(self, mode: str = MODE_ECHO) -> None:
        self.mode = mode
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.mode == self.MODE_HTTP_ERROR:
            return httpx.Response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                json={"message": "workflow down"},
            )
        payload = json.loads(request.content)
        inputs = payload.get("inputs", {})
        if self.mode == self.MODE_MISSING_REPLY:
            response_json = {
                "workflow_run_id": "wf-missing",
                "data": {"status": "succeeded", "outputs": {}},
            }
            return httpx.Response(HTTPStatus.OK, json=response_json)
        if self.mode == self.MODE_BAD_CITATIONS:
            response_json = {
                "workflow_run_id": "wf-cite",
                "data": {
                    "status": "succeeded",
                    "outputs": {
                        "reply_text": _REJECTED_WORKFLOW_REPLY,
                        "citations": [_CITATION_OUTSIDE_BASE],
                    },
                },
            }
            return httpx.Response(HTTPStatus.OK, json=response_json)
        echoed_text = inputs.get(INPUT_REQUEST_TEXT, "")
        response_json = {
            "workflow_run_id": "wf-echo",
            "data": {
                "status": "succeeded",
                "outputs": {"reply_text": echoed_text},
            },
        }
        return httpx.Response(HTTPStatus.OK, json=response_json)


def _parse_workflow_request_payloads(
    fake_dify: FakeDify,
) -> list[dict[str, Any]]:
    """JSON bodies the gateway POSTed to the fake workflow run URL."""
    return [json.loads(request.content) for request in fake_dify.requests]


def _require_single_workflow_call(
    fake_dify: FakeDify,
) -> tuple[httpx.Request, dict[str, Any]]:
    """Require one blocking POST; return that request and its JSON body."""
    assert len(fake_dify.requests) == _ONE_WORKFLOW_CALL
    return fake_dify.requests[0], _parse_workflow_request_payloads(fake_dify)[0]


async def _run_one_poll_cycle(
    settings: Settings,
    fake_dify: FakeDify,
    *,
    should_mark_seen: bool = True,
) -> None:
    """One IMAP UNSEEN batch against ``fake_dify``; always close HTTP."""
    transport = httpx.MockTransport(fake_dify)
    http_client = httpx.AsyncClient(transport=transport)
    processor = Processor(settings, http_client=http_client)
    try:
        await processor.run_poll_cycle(should_mark_seen=should_mark_seen)
    finally:
        await processor.close()


@pytest.mark.asyncio
async def test_normalize_html_and_ignore_attachment(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """HTML is sanitized to text; attachment bytes never reach Dify inputs."""
    inbound = MIMEMultipart()
    inbound["From"] = EMPLOYEE_EMAIL
    inbound["To"] = SUPPORT_EMAIL
    inbound["Subject"] = "HTML help"
    html = (
        "<p>Need <b>VPN</b> access</p>"
        "<script>alert('x')</script>"
        "<style>body{color:red}</style>"
    )
    inbound.attach(MIMEText(html, "html"))
    attachment = MIMEApplication(_ATTACHMENT_BYTES, Name=_ATTACHMENT_FILENAME)
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=_ATTACHMENT_FILENAME,
    )
    inbound.attach(attachment)
    deliver_message(greenmail, inbound)
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    _, payload = _require_single_workflow_call(fake_dify)
    request_text = payload["inputs"][INPUT_REQUEST_TEXT]
    assert "VPN" in request_text
    assert "Need" in request_text
    assert _ATTACHMENT_BYTES.decode() not in request_text
    assert "alert" not in request_text
    assert "color:red" not in request_text


@pytest.mark.asyncio
async def test_mask_before_dify_and_blocking_contract(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """PII is masked before Dify; Start fields and blocking mode are set."""
    inbound_body = (
        f"Call me at {PII_PHONE} or {PII_EMAIL_IN_BODY}; "
        f"card {PII_CARD} please."
    )
    deliver_message(
        greenmail,
        make_text_mail(
            subject=f"Reach {PII_EMAIL_IN_SUBJECT}",
            body=inbound_body,
        ),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    request, payload = _require_single_workflow_call(fake_dify)
    assert request.headers["Authorization"] == DIFY_APP_KEY
    assert payload["response_mode"] == RESPONSE_MODE_BLOCKING
    assert payload["user"] == EMPLOYEE_EMAIL
    inputs = payload["inputs"]
    assert inputs[INPUT_USER_EMAIL] == EMPLOYEE_EMAIL
    assert set(inputs) == START_INPUT_KEYS
    combined = inputs[INPUT_SUBJECT] + inputs[INPUT_REQUEST_TEXT]
    assert PII_EMAIL_IN_BODY not in combined
    assert PII_EMAIL_IN_SUBJECT not in combined
    assert PII_CARD not in combined
    assert PII_PHONE not in combined
    assert privacy_constants.PLACEHOLDER_EMAIL in combined
    assert privacy_constants.PLACEHOLDER_PHONE in combined
    assert privacy_constants.PLACEHOLDER_CARD in combined


@pytest.mark.asyncio
async def test_smtp_reply_uses_reply_text_then_seen(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Echoed reply_text is SMTP-sent; support INBOX then has no UNSEEN."""
    deliver_message(
        greenmail,
        make_text_mail(subject="VPN", body=_VPN_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(_VPN_BODY in item for item in reply_bodies)
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD) == []


@pytest.mark.asyncio
async def test_restart_picks_up_leftover_unseen(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Mail left UNSEEN (as after a crash) is processed on the next cycle."""
    deliver_message(
        greenmail,
        make_text_mail(subject="after restart", body=_RESTART_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(_RESTART_BODY in item for item in reply_bodies)
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD) == []


@pytest.mark.asyncio
async def test_duplicate_window_when_seen_skipped(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Without ``\\Seen``, a second cycle treats the same mail as new work."""
    deliver_message(
        greenmail,
        make_text_mail(subject="dup", body=_DUPLICATE_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(
        gateway_settings, fake_dify, should_mark_seen=False
    )
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    assert len(fake_dify.requests) == _DUPLICATE_WINDOW_WORKFLOW_CALLS
    reply_bodies = wait_for_inbox_bodies(
        greenmail,
        EMPLOYEE_EMAIL,
        EMPLOYEE_PASSWORD,
        min_count=_DUPLICATE_WINDOW_SMTP_REPLIES,
    )
    matches = [item for item in reply_bodies if _DUPLICATE_BODY in item]
    assert len(matches) == _DUPLICATE_WINDOW_SMTP_REPLIES


@pytest.mark.asyncio
async def test_dify_http_failure_sends_static_ack(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """HTTP 500 SMTP-sends the static ack, not inbound text; then ``\\Seen``."""
    deliver_message(
        greenmail,
        make_text_mail(subject="outage", body=_OUTAGE_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify(mode=FakeDify.MODE_HTTP_ERROR)
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(constants.STATIC_ACK_TEXT in item for item in reply_bodies)
    assert all(_OUTAGE_BODY not in item for item in reply_bodies)
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD) == []


@pytest.mark.asyncio
async def test_missing_reply_text_sends_static_ack(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Missing End reply_text is not fail-open: static ack only."""
    deliver_message(
        greenmail,
        make_text_mail(subject="malformed", body=_MALFORMED_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify(mode=FakeDify.MODE_MISSING_REPLY)
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(constants.STATIC_ACK_TEXT in item for item in reply_bodies)
    assert all(_MALFORMED_BODY not in item for item in reply_bodies)


@pytest.mark.asyncio
async def test_citation_outside_base_sends_static_ack(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Citation outside the repo base is rejected; workflow text is not sent."""
    deliver_message(
        greenmail,
        make_text_mail(subject="cite", body=_CITE_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify(mode=FakeDify.MODE_BAD_CITATIONS)
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(constants.STATIC_ACK_TEXT in item for item in reply_bodies)
    assert all(_REJECTED_WORKFLOW_REPLY not in item for item in reply_bodies)


@pytest.mark.asyncio
async def test_plain_greeting_does_not_call_dify(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Whole-message hello SMTP-sends the greeting text and skips Dify."""
    deliver_message(
        greenmail,
        make_text_mail(subject="Hello", body=_GREETING_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    assert fake_dify.requests == []
    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(constants.GREETING_REPLY_TEXT in item for item in reply_bodies)
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD) == []


@pytest.mark.asyncio
async def test_toxic_mail_does_not_call_dify(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Toxicity SMTP-sends the static ack and skips Dify."""
    deliver_message(
        greenmail,
        make_text_mail(subject="help", body=_TOXIC_BODY),
    )
    wait_for_unseen(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)

    fake_dify = FakeDify()
    await _run_one_poll_cycle(gateway_settings, fake_dify)

    assert fake_dify.requests == []
    reply_bodies = wait_for_inbox_bodies(
        greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD
    )
    assert any(constants.STATIC_ACK_TEXT in item for item in reply_bodies)
    assert all(_TOXIC_TERM not in item for item in reply_bodies)
    assert list_unseen_uids(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD) == []
