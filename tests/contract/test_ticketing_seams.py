"""Contract tests for ticketing HTTP and MCP seams."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contracts.enums import (
    DomainErrorCode,
    MessageRole,
    TicketCategory,
    TicketStatus,
)
from ticketing.db import Message, Ticket
from ticketing.mcp_server import (
    mcp_append_message,
    mcp_create_ticket,
    mcp_list_my_tickets,
)


async def _set_updated_at(
    ticketing_app: FastAPI, ticket_id: str, updated_at: datetime
) -> None:
    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.updated_at = updated_at
        await db_session.commit()
    finally:
        await db_session.close()


async def test_create_ticket_text_and_other_category(
    ticketing_app: FastAPI,
) -> None:
    user_id = "employee@example.test"
    created_ticket = await mcp_create_ticket(
        user_id=user_id,
        category=TicketCategory.OTHER,
        text="VPN fails for me@corp.test",
    )
    assert "error" not in created_ticket
    assert created_ticket["category"] == TicketCategory.OTHER
    assert created_ticket["status"] == TicketStatus.OPEN
    assert "message_ids" not in created_ticket

    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, created_ticket["ticket_id"])
        assert ticket is not None
        assert "[EMAIL]" in ticket.text
        assert "me@corp.test" not in ticket.text
        messages = (
            await db_session.scalars(
                select(Message).where(Message.ticket_id == ticket.id)
            )
        ).all()
        assert messages == []
    finally:
        await db_session.close()

    listed = await mcp_list_my_tickets(user_id=user_id)
    assert len(listed["tickets"]) == 1
    assert listed["tickets"][0]["ticket_id"] == created_ticket["ticket_id"]


@pytest.mark.usefixtures("ticketing_app")
async def test_scoped_list_hides_other_employee() -> None:
    await mcp_create_ticket(
        user_id="a@example.test",
        category=TicketCategory.ACCESS,
        text="access request",
    )
    await mcp_create_ticket(
        user_id="b@example.test",
        category=TicketCategory.DOCS,
        text="docs gap",
    )
    listed_for_a = await mcp_list_my_tickets(user_id="a@example.test")
    assert len(listed_for_a["tickets"]) == 1
    assert listed_for_a["tickets"][0]["category"] == TicketCategory.ACCESS


@pytest.mark.usefixtures("ticketing_app")
async def test_append_rejects_ticket_owned_by_other_user_id() -> None:
    created_for_owner = await mcp_create_ticket(
        user_id="owner@example.test",
        category=TicketCategory.ACCESS,
        text="access request",
    )
    denied = await mcp_append_message(
        user_id="other@example.test",
        ticket_id=created_for_owner["ticket_id"],
        text="not my ticket",
        role=MessageRole.USER,
    )
    assert denied["error"]["code"] == DomainErrorCode.NOT_FOUND


async def test_append_agent_with_usage_and_user_role(
    ticketing_app: FastAPI,
) -> None:
    user_id = "usage@example.test"
    created_ticket = await mcp_create_ticket(
        user_id=user_id,
        category=TicketCategory.FEATURE,
        text="widget request",
    )
    ticket_id = created_ticket["ticket_id"]

    before_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket_before = await before_session.get(Ticket, ticket_id)
        assert ticket_before is not None
        updated_at_before = ticket_before.updated_at
        text_before = ticket_before.text
        status_before = ticket_before.status
    finally:
        await before_session.close()

    first_user = await mcp_append_message(
        user_id=user_id,
        ticket_id=ticket_id,
        text="please add widget",
        role=MessageRole.USER,
    )
    assert "error" not in first_user

    agent_reply = await mcp_append_message(
        user_id=user_id,
        ticket_id=ticket_id,
        text="Use the catalog page.",
        role=MessageRole.AGENT,
        model="yandex-test",
        tokens_in=10,
        tokens_out=20,
        latency_ms=150,
    )
    assert "error" not in agent_reply
    assert agent_reply["ticket_id"] == ticket_id
    assert "status" not in agent_reply

    extra_user_message = await mcp_append_message(
        user_id=user_id,
        ticket_id=ticket_id,
        text="Thanks, still stuck",
        role=MessageRole.USER,
    )
    assert "error" not in extra_user_message
    assert extra_user_message["ticket_id"] == ticket_id

    after_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        rows = (
            await after_session.scalars(
                select(Message)
                .where(Message.ticket_id == ticket_id)
                .order_by(Message.created_at)
            )
        ).all()
        assert [row.role for row in rows] == [
            MessageRole.USER,
            MessageRole.AGENT,
            MessageRole.USER,
        ]
        agent_row = rows[1]
        assert agent_row.ticket_id == ticket_id
        assert agent_row.model == "yandex-test"
        assert agent_row.tokens_in == 10
        assert agent_row.tokens_out == 20
        assert agent_row.latency_ms == 150
        assert rows[2].model is None
        assert rows[2].ticket_id == ticket_id
        ticket_after = await after_session.get(Ticket, ticket_id)
        assert ticket_after is not None
        assert ticket_after.updated_at > updated_at_before
        assert ticket_after.text == text_before
        assert ticket_after.status == status_before
    finally:
        await after_session.close()


async def test_persistence_masks_pii_on_create(
    ticketing_app: FastAPI,
) -> None:
    user_id = "mask@example.test"
    created_ticket = await mcp_create_ticket(
        user_id=user_id,
        category=TicketCategory.BUG,
        text="Reach me at mask@example.test",
    )
    appended = await mcp_append_message(
        user_id=user_id,
        ticket_id=created_ticket["ticket_id"],
        text="card 4111111111111111",
        role=MessageRole.USER,
    )
    assert "error" not in appended
    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, created_ticket["ticket_id"])
        message = await db_session.get(Message, appended["message_id"])
        assert ticket is not None
        assert message is not None
        assert "mask@example.test" not in ticket.text
        assert "[EMAIL]" in ticket.text
        assert "4111111111111111" not in message.text
        assert "[CARD]" in message.text
    finally:
        await db_session.close()


async def test_append_delays_escalate_stale(
    ticketing_client: AsyncClient, ticketing_app: FastAPI
) -> None:
    aged_then_appended = await mcp_create_ticket(
        user_id="active-chat@example.test",
        category=TicketCategory.BUG,
        text="still talking",
    )
    aged_idle = await mcp_create_ticket(
        user_id="idle@example.test",
        category=TicketCategory.ACCESS,
        text="no later append",
    )
    aged = datetime.now(UTC) - timedelta(hours=2)
    await _set_updated_at(ticketing_app, aged_then_appended["ticket_id"], aged)
    await _set_updated_at(ticketing_app, aged_idle["ticket_id"], aged)

    appended = await mcp_append_message(
        user_id="active-chat@example.test",
        ticket_id=aged_then_appended["ticket_id"],
        text="still here",
        role=MessageRole.USER,
    )
    assert "error" not in appended

    response = await ticketing_client.post(
        "/v1/tickets/escalate-stale",
        json={"older_than_seconds": 3600},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ticket_ids"] == [aged_idle["ticket_id"]]
    assert payload["count"] == 1

    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        talking = await db_session.get(Ticket, aged_then_appended["ticket_id"])
        idle = await db_session.get(Ticket, aged_idle["ticket_id"])
        assert talking is not None
        assert idle is not None
        assert talking.status == TicketStatus.OPEN
        assert talking.text == "still talking"
        assert idle.status == TicketStatus.ESCALATED
    finally:
        await db_session.close()


async def test_escalate_stale_http_on_old_open_tickets(
    ticketing_client: AsyncClient, ticketing_app: FastAPI
) -> None:
    stale = await mcp_create_ticket(
        user_id="stale@example.test",
        category=TicketCategory.BUG,
        text="old open",
    )
    fresh = await mcp_create_ticket(
        user_id="fresh@example.test",
        category=TicketCategory.ACCESS,
        text="new open",
    )
    await _set_updated_at(
        ticketing_app,
        stale["ticket_id"],
        datetime.now(UTC) - timedelta(hours=2),
    )

    response = await ticketing_client.post(
        "/v1/tickets/escalate-stale",
        json={"older_than_seconds": 3600},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["count"] == 1
    assert payload["ticket_ids"] == [stale["ticket_id"]]

    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        stale_ticket = await db_session.get(Ticket, stale["ticket_id"])
        fresh_ticket = await db_session.get(Ticket, fresh["ticket_id"])
        assert stale_ticket is not None
        assert fresh_ticket is not None
        assert stale_ticket.status == TicketStatus.ESCALATED
        assert fresh_ticket.status == TicketStatus.OPEN
        stale_messages = (
            await db_session.scalars(
                select(Message).where(Message.ticket_id == stale["ticket_id"])
            )
        ).all()
        assert len(stale_messages) == 0
    finally:
        await db_session.close()
