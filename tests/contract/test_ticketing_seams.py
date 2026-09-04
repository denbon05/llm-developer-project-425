"""Contract tests for ticketing HTTP and MCP seams.

Seams: MCP ``create-ticket`` / ``list-my-tickets`` / ``append-message``,
and private HTTP ``POST /v1/tickets/escalate-stale``. Tests call ``mcp_*``
directly (no MCP session). Helpers that write ORM fields poke statuses
and timestamps the LLM path never sets.
"""

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
from privacy import constants
from ticketing.db import Message, Ticket
from ticketing.mcp_server import (
    mcp_append_message,
    mcp_create_ticket,
    mcp_list_my_tickets,
)

# Escalate proofs: age tickets 2h, then cut off at 1h so they are stale.
_STALE_AGE = timedelta(hours=2)
_ESCALATE_AFTER_SECONDS = 3600

# Arbitrary agent usage; must persist on the agent row only.
_AGENT_TOKENS_IN = 10
_AGENT_TOKENS_OUT = 20
_AGENT_LATENCY_MS = 150

# Luhn-valid Visa test PAN (same sample as privacy unit tests).
_TEST_CARD_PAN = "4111111111111111"


async def _set_updated_at(
    ticketing_app: FastAPI, ticket_id: str, updated_at: datetime
) -> None:
    """Backdate ``tickets.updated_at`` (no MCP write for activity time)."""
    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.updated_at = updated_at
        await db_session.commit()
    finally:
        await db_session.close()


async def _set_created_at(
    ticketing_app: FastAPI, ticket_id: str, created_at: datetime
) -> None:
    """Backdate ``tickets.created_at`` (escalate cutoff; no MCP write)."""
    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.created_at = created_at
        await db_session.commit()
    finally:
        await db_session.close()


async def _set_status(
    ticketing_app: FastAPI, ticket_id: str, status: TicketStatus
) -> None:
    """Poke a status the LLM path does not write (answered/closed/tests)."""
    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, ticket_id)
        assert ticket is not None
        ticket.status = status
        await db_session.commit()
    finally:
        await db_session.close()


async def test_create_ticket_stores_masked_text_without_message(
    ticketing_app: FastAPI,
) -> None:
    """Create stores masked ``text``, no message row; list returns that text."""
    user_id = "employee1@example.test"
    created_ticket = await mcp_create_ticket(
        user_id=user_id,
        category=TicketCategory.BUG,
        text="VPN fails for me@corp.test",
    )
    assert "error" not in created_ticket
    assert created_ticket["category"] == TicketCategory.BUG
    assert created_ticket["status"] == TicketStatus.OPEN
    assert "message_ids" not in created_ticket

    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        ticket = await db_session.get(Ticket, created_ticket["ticket_id"])
        assert ticket is not None
        assert constants.PLACEHOLDER_EMAIL in ticket.text
        assert "me@corp.test" not in ticket.text
        messages = (
            await db_session.scalars(
                select(Message).where(Message.ticket_id == ticket.id)
            )
        ).all()
        assert messages == []  # create-ticket does not insert a message row
    finally:
        await db_session.close()

    listed = await mcp_list_my_tickets(user_id=user_id)
    # Default list: this sender has one open ticket.
    assert len(listed["tickets"]) == 1
    listed_row = listed["tickets"][0]
    assert listed_row["ticket_id"] == created_ticket["ticket_id"]
    assert "text" in listed_row
    assert constants.PLACEHOLDER_EMAIL in listed_row["text"]
    assert "me@corp.test" not in listed_row["text"]


@pytest.mark.usefixtures("ticketing_app")
async def test_scoped_list_hides_other_employee() -> None:
    """List returns only the calling ``user_id``'s ticket, including text."""
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
    # Scope: each caller sees only their own single ticket.
    assert len(listed_for_a["tickets"]) == 1
    row_a = listed_for_a["tickets"][0]
    assert row_a["category"] == TicketCategory.ACCESS
    assert row_a["text"] == "access request"
    listed_for_b = await mcp_list_my_tickets(user_id="b@example.test")
    assert len(listed_for_b["tickets"]) == 1
    row_b = listed_for_b["tickets"][0]
    assert row_b["category"] == TicketCategory.DOCS


async def test_list_default_hides_closed_includes_answered(
    ticketing_app: FastAPI,
) -> None:
    """Default statuses hide closed; answered and escalated still list.

    One ticket per sender (create rejects a second non-closed). Statuses
    ``answered`` / ``closed`` / ``escalated`` are poked: the LLM path does
    not write them (except escalate via HTTP).
    """
    closed_user = "closed-list@example.test"
    answered_user = "answered-list@example.test"
    escalated_user = "escalated-list@example.test"
    closed_ticket = await mcp_create_ticket(
        user_id=closed_user,
        category=TicketCategory.BUG,
        text="please close me",
    )
    answered_ticket = await mcp_create_ticket(
        user_id=answered_user,
        category=TicketCategory.DOCS,
        text="already answered",
    )
    escalated_ticket = await mcp_create_ticket(
        user_id=escalated_user,
        category=TicketCategory.ACCESS,
        text="needs a human later",
    )
    await _set_status(
        ticketing_app, closed_ticket["ticket_id"], TicketStatus.CLOSED
    )
    await _set_status(
        ticketing_app, answered_ticket["ticket_id"], TicketStatus.ANSWERED
    )
    await _set_status(
        ticketing_app, escalated_ticket["ticket_id"], TicketStatus.ESCALATED
    )

    # Default statuses omit closed → empty; explicit ["closed"] returns it.
    assert (await mcp_list_my_tickets(user_id=closed_user))["tickets"] == []
    listed_closed = await mcp_list_my_tickets(
        user_id=closed_user, statuses=["closed"]
    )
    assert len(listed_closed["tickets"]) == 1  # only the poked-closed row
    closed_row = listed_closed["tickets"][0]
    assert closed_row["ticket_id"] == closed_ticket["ticket_id"]
    assert closed_row["status"] == TicketStatus.CLOSED
    assert closed_row["text"] == "please close me"

    # Default includes answered (unused by LLM writer; still non-closed).
    listed_answered = await mcp_list_my_tickets(user_id=answered_user)
    assert len(listed_answered["tickets"]) == 1  # only the poked-answered row
    answered_row = listed_answered["tickets"][0]
    assert answered_row["ticket_id"] == answered_ticket["ticket_id"]
    assert answered_row["status"] == TicketStatus.ANSWERED

    # Default includes escalated (follow-up path still lists it).
    listed_escalated = await mcp_list_my_tickets(user_id=escalated_user)
    assert len(listed_escalated["tickets"]) == 1  # only the poked-escalated row
    escalated_row = listed_escalated["tickets"][0]
    assert escalated_row["ticket_id"] == escalated_ticket["ticket_id"]
    assert escalated_row["status"] == TicketStatus.ESCALATED


@pytest.mark.usefixtures("ticketing_app")
async def test_list_empty_statuses_returns_no_rows() -> None:
    """``statuses=[]`` is a strict empty filter, not the default set."""
    user_id = "empty-filter@example.test"
    await mcp_create_ticket(
        user_id=user_id,
        category=TicketCategory.DOCS,
        text="docs gap",
    )
    listed = await mcp_list_my_tickets(user_id=user_id, statuses=[])
    assert listed["tickets"] == []  # empty filter, not the default set


@pytest.mark.usefixtures("ticketing_app")
async def test_list_invalid_status_error_envelope() -> None:
    """Unknown status strings are ``NOT_ELIGIBLE``, not ignored."""
    listed = await mcp_list_my_tickets(
        user_id="invalid-status@example.test",
        statuses=["nope"],  # not a TicketStatus value
    )
    assert listed["error"]["code"] == DomainErrorCode.NOT_ELIGIBLE


@pytest.mark.usefixtures("ticketing_app")
async def test_create_invalid_category_error_envelope() -> None:
    """Unknown category strings are ``NOT_ELIGIBLE``, not a raw exception."""
    created = await mcp_create_ticket(
        user_id="invalid-category@example.test",
        category="nope",
        text="vpn down",
    )
    assert created["error"]["code"] == DomainErrorCode.NOT_ELIGIBLE


@pytest.mark.usefixtures("ticketing_app")
async def test_append_rejects_ticket_owned_by_other_user_id() -> None:
    """Append on another employee's ticket is ``NOT_FOUND`` (not leak)."""
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
    """User then agent then user; usage lands on agent; text/status stay."""
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
        tokens_in=_AGENT_TOKENS_IN,
        tokens_out=_AGENT_TOKENS_OUT,
        latency_ms=_AGENT_LATENCY_MS,
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
        # Append order: user, agent, extra user.
        assert [row.role for row in rows] == [
            MessageRole.USER,
            MessageRole.AGENT,
            MessageRole.USER,
        ]
        agent_row = rows[1]  # second append is the agent line
        assert agent_row.ticket_id == ticket_id
        assert agent_row.model == "yandex-test"
        assert agent_row.tokens_in == _AGENT_TOKENS_IN
        assert agent_row.tokens_out == _AGENT_TOKENS_OUT
        assert agent_row.latency_ms == _AGENT_LATENCY_MS
        extra_user_row = rows[2]  # third append; user rows store no usage
        assert extra_user_row.model is None
        assert extra_user_row.ticket_id == ticket_id
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
    """Create and append mask email and Luhn card before durable store."""
    user_id = "mask@example.test"
    created_ticket = await mcp_create_ticket(
        user_id=user_id,
        category=TicketCategory.BUG,
        text="Reach me at mask@example.test",
    )
    appended = await mcp_append_message(
        user_id=user_id,
        ticket_id=created_ticket["ticket_id"],
        text=f"card {_TEST_CARD_PAN}",
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
        assert constants.PLACEHOLDER_EMAIL in ticket.text
        assert _TEST_CARD_PAN not in message.text
        assert constants.PLACEHOLDER_CARD in message.text
    finally:
        await db_session.close()


async def test_append_does_not_delay_escalate_stale(
    ticketing_client: AsyncClient, ticketing_app: FastAPI
) -> None:
    """Append does not keep an old-created open ticket from escalating."""
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
    aged = datetime.now(UTC) - _STALE_AGE
    await _set_created_at(ticketing_app, aged_then_appended["ticket_id"], aged)
    await _set_created_at(ticketing_app, aged_idle["ticket_id"], aged)

    appended = await mcp_append_message(
        user_id="active-chat@example.test",
        ticket_id=aged_then_appended["ticket_id"],
        text="still here",
        role=MessageRole.USER,
    )
    assert "error" not in appended

    response = await ticketing_client.post(
        "/v1/tickets/escalate-stale",
        json={"older_than_seconds": _ESCALATE_AFTER_SECONDS},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["count"] == 2
    tickets_by_id = {row["ticket_id"]: row for row in payload["tickets"]}
    assert set(tickets_by_id) == {
        aged_then_appended["ticket_id"],
        aged_idle["ticket_id"],
    }
    talking_row = tickets_by_id[aged_then_appended["ticket_id"]]
    assert talking_row["user_id"] == "active-chat@example.test"
    assert talking_row["category"] == TicketCategory.BUG
    assert talking_row["status"] == TicketStatus.ESCALATED
    assert talking_row["text"] == "still talking"
    idle_row = tickets_by_id[aged_idle["ticket_id"]]
    assert idle_row["user_id"] == "idle@example.test"
    assert idle_row["category"] == TicketCategory.ACCESS
    assert idle_row["status"] == TicketStatus.ESCALATED
    assert idle_row["text"] == "no later append"

    db_session: AsyncSession = ticketing_app.state.db_session_factory()
    try:
        talking = await db_session.get(Ticket, aged_then_appended["ticket_id"])
        idle = await db_session.get(Ticket, aged_idle["ticket_id"])
        assert talking is not None
        assert idle is not None
        assert talking.status == TicketStatus.ESCALATED
        assert talking.text == "still talking"
        assert idle.status == TicketStatus.ESCALATED
    finally:
        await db_session.close()


async def test_escalate_stale_http_on_old_open_tickets(
    ticketing_client: AsyncClient, ticketing_app: FastAPI
) -> None:
    """Status-only: stale created_at open → escalated, no messages."""
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
    aged = datetime.now(UTC) - _STALE_AGE
    await _set_created_at(ticketing_app, stale["ticket_id"], aged)
    # Old updated_at alone must not escalate a recently created ticket.
    await _set_updated_at(ticketing_app, fresh["ticket_id"], aged)

    response = await ticketing_client.post(
        "/v1/tickets/escalate-stale",
        json={"older_than_seconds": _ESCALATE_AFTER_SECONDS},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    # Fresh created_at is under the cutoff even if updated_at is old.
    assert payload["count"] == 1
    assert len(payload["tickets"]) == 1
    stale_row = payload["tickets"][0]
    assert stale_row["ticket_id"] == stale["ticket_id"]
    assert stale_row["user_id"] == "stale@example.test"
    assert stale_row["category"] == TicketCategory.BUG
    assert stale_row["status"] == TicketStatus.ESCALATED
    assert stale_row["text"] == "old open"

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
        assert len(stale_messages) == 0  # escalate is status-only
    finally:
        await db_session.close()
