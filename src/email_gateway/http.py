"""Private HTTP route for operator digest SMTP."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from email_gateway import constants
from email_gateway.clients import mailbox
from email_gateway.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix=constants.API_PREFIX)


class DigestTicket(BaseModel):
    """Optional ticket fields for digest SMTP; omit missing keys."""

    ticket_id: str | None = None
    user_id: str | None = None
    category: str | None = None
    status: str | None = None
    text: str | None = None
    created_at: str | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def stringify_created_at(cls, value: object) -> str | None:
        """ISO-format datetimes so Dify JSON and ticketing agree."""
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)


class SendEmailRequest(BaseModel):
    """Trusted subject plus tickets (gateway formats the mail); no recipient."""

    subject: str = Field(min_length=1)
    body: str | None = None
    tickets: list[DigestTicket] | None = None
    ticket_id: str | None = None
    user_id: str | None = None
    category: str | None = None
    created_at: str | None = None
    text: str | None = None


class SendEmailResponse(BaseModel):
    """Whether SMTP accepted the message."""

    is_sent: bool


def _is_present_field(value: str | None) -> bool:
    """True when a digest field should be rendered."""
    return value is not None and value != ""


def _has_flat_ticket_fields(payload: SendEmailRequest) -> bool:
    """True when the live one-ticket dump set any structured field."""
    return any(
        _is_present_field(value)
        for value in (
            payload.ticket_id,
            payload.user_id,
            payload.category,
            payload.created_at,
            payload.text,
        )
    )


def _format_ticket_block(ticket: DigestTicket) -> str:
    """One bullet block; skip fields that were not sent."""
    fields = (
        ("ticket_id:", ticket.ticket_id),
        ("user_id:", ticket.user_id),
        ("category:", ticket.category),
        ("created_at:", ticket.created_at),
        ("text:", ticket.text),
    )
    lines = [
        f"{label} {value}"
        for label, value in fields
        if _is_present_field(value)
    ]
    if not lines:
        return ""
    first, *rest = lines
    block = [f"- {first}"]
    block.extend(f"  {line}" for line in rest)
    return "\n".join(block)


def _format_digest_body(tickets: list[DigestTicket]) -> str:
    """Plain-text digest from ticket fields."""
    blocks = [
        block for ticket in tickets if (block := _format_ticket_block(ticket))
    ]
    return "\n\n".join(blocks)


def _parse_tickets_from_json_body(body: str) -> list[DigestTicket] | None:
    """Treat ``body`` as a JSON ticket list (Dify array stuffed into body)."""
    try:
        parsed: Any = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not parsed:
        return None
    tickets: list[DigestTicket] = []
    for item in parsed:
        if not isinstance(item, dict):
            return None
        tickets.append(DigestTicket.model_validate(item))
    return tickets


def _resolve_smtp_body(payload: SendEmailRequest) -> str | None:
    """Prefer ``tickets``, then flat fields, then a JSON list in ``body``."""
    if payload.tickets:
        return _format_digest_body(payload.tickets)
    if _has_flat_ticket_fields(payload):
        return _format_digest_body(
            [
                DigestTicket(
                    ticket_id=payload.ticket_id,
                    user_id=payload.user_id,
                    category=payload.category,
                    created_at=payload.created_at,
                    text=payload.text,
                )
            ]
        )
    if payload.body:
        parsed_tickets = _parse_tickets_from_json_body(payload.body)
        if parsed_tickets is not None:
            return _format_digest_body(parsed_tickets)
        return payload.body
    return None


@router.post(constants.SEND_EMAIL_ROUTE, response_model=SendEmailResponse)
async def send_email(
    body: SendEmailRequest, request: Request
) -> SendEmailResponse:
    """SMTP a gateway-formatted digest to ``OPERATOR_EMAIL`` (no ``to``)."""
    settings: Settings = request.app.state.settings
    mailbox_client: mailbox.Client = request.app.state.mailbox
    smtp_body = _resolve_smtp_body(body)
    if smtp_body is None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="missing_digest",
        )
    is_sent = await asyncio.to_thread(
        mailbox_client.send_mail,
        to_addr=settings.operator_email,
        subject=body.subject,
        body=smtp_body,
    )
    if not is_sent:
        logger.error("digest_send", extra={"is_sent": False})
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=constants.FAIL_SMTP_SEND,
        )
    logger.info("digest_send", extra={"is_sent": True})
    return SendEmailResponse(is_sent=True)
