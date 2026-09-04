"""GreenMail proofs for gateway digest HTTP (no IMAP poll loop)."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import ASGITransport, AsyncClient

from email_gateway import constants
from email_gateway.config import Settings
from email_gateway.main import create_app

from .greenmail import (
    OPERATOR_EMAIL,
    OPERATOR_PASSWORD,
    GreenMailEndpoints,
    list_inbox_bodies,
    list_inbox_messages,
    wait_for_inbox_bodies,
)

_DIGEST_SUBJECT = "Escalation digest"
_USER_ID = "employee1@example.test"
_TICKET_ID_ONE = "11111111-1111-1111-1111-111111111111"
_TICKET_ID_TWO = "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_send_email_rejects_empty_body_without_smtp(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Empty body with no tickets is 422 and does not SMTP."""
    app = create_app(gateway_settings)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as http_client:
        response = await http_client.post(
            constants.SEND_EMAIL_PATH,
            json={"subject": _DIGEST_SUBJECT, "body": ""},
        )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert list_inbox_bodies(greenmail, OPERATOR_EMAIL, OPERATOR_PASSWORD) == []


@pytest.mark.asyncio
async def test_send_email_formats_tickets_array_to_operator(
    greenmail: GreenMailEndpoints,
    gateway_settings: Settings,
) -> None:
    """Non-empty tickets list SMTP-sends a formatted digest to OPERATOR_EMAIL."""
    app = create_app(gateway_settings)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as http_client:
        response = await http_client.post(
            constants.SEND_EMAIL_PATH,
            json={
                "subject": _DIGEST_SUBJECT,
                "tickets": [
                    {
                        "ticket_id": _TICKET_ID_ONE,
                        "user_id": _USER_ID,
                        "category": "feature",
                    },
                    {
                        "ticket_id": _TICKET_ID_TWO,
                        "user_id": _USER_ID,
                        "category": "docs",
                    },
                ],
            },
        )
    assert response.status_code == HTTPStatus.OK, response.text
    mail = "\n".join(
        wait_for_inbox_bodies(greenmail, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    )
    assert _TICKET_ID_ONE in mail
    assert _TICKET_ID_TWO in mail
    messages = list_inbox_messages(greenmail, OPERATOR_EMAIL, OPERATOR_PASSWORD)
    subjects = [str(parsed.get("Subject") or "") for parsed in messages]
    assert _DIGEST_SUBJECT in subjects
    assert all(not item.lower().startswith("re:") for item in subjects)
