"""Deep ticketing domain: invariants live here; adapters stay thin.

Employee operations are scoped to the ``user_id`` argument (sender email,
MVP) on ``tickets.user_id``. Ticket/message ``text`` is masked at this
persistence seam. Untrusted create-ticket ``text`` and append-message
``text`` are stored as data and must not change authorization or routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contracts.enums import (
    DomainErrorCode,
    MessageRole,
    TicketCategory,
    TicketStatus,
)
from contracts.models import EscalateStaleResponse, TicketSummary
from privacy.masking import mask_text
from ticketing import constants
from ticketing.config import Settings
from ticketing.db import Message, Ticket, new_id, utcnow

_STATUS_BY_VALUE: dict[str, TicketStatus] = {
    status.value: status for status in TicketStatus
}


class DomainError(Exception):
    """Typed domain failure."""

    def __init__(self, code: DomainErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class CreateTicketResult:
    ticket_id: str
    status: TicketStatus
    category: TicketCategory


@dataclass
class AppendMessageResult:
    message_id: str
    ticket_id: str


class TicketingService:
    """Enforces scope, transitions, and masking for ticket operations."""

    def __init__(self, db_session: AsyncSession, settings: Settings) -> None:
        # Async ORM session for this unit of work (request/tool call).
        self.db_session = db_session
        self.settings = settings

    def _require_user_id(self, user_id: str) -> str:
        normalized = user_id.strip()
        if not normalized:
            raise DomainError(
                DomainErrorCode.FORBIDDEN, "missing or empty user_id"
            )
        return normalized

    async def _find_active_ticket(self, user_id: str) -> Ticket | None:
        """Newest non-``closed`` ticket for the employee scope, if any."""
        return await self.db_session.scalar(
            select(Ticket)
            .where(
                Ticket.user_id == user_id,
                Ticket.status != TicketStatus.CLOSED,
            )
            .order_by(Ticket.created_at.desc())
        )

    async def _require_ticket_for_scope(
        self, user_id: str, ticket_id: str
    ) -> Ticket:
        """Load ticket only when ``user_id`` matches (cross-employee deny)."""
        ticket = await self.db_session.get(Ticket, ticket_id)
        if ticket is None or ticket.user_id != user_id:
            raise DomainError(DomainErrorCode.NOT_FOUND, "ticket not in scope")
        return ticket

    async def create_ticket(
        self,
        *,
        user_id: str,
        category: TicketCategory,
        text: str,
    ) -> CreateTicketResult:
        """Create one ``open`` ticket with masked text. No message row.

        Rejects if this ``user_id`` already has a non-``closed`` ticket.
        ``tickets.text`` is set once. Chat history is ``append_message``.
        """
        user_id = self._require_user_id(user_id)
        active_ticket = await self._find_active_ticket(user_id)
        if active_ticket is not None:
            raise DomainError(
                DomainErrorCode.CONFLICT,
                "active ticket exists for this user_id",
            )

        ticket = Ticket(
            id=new_id(),
            user_id=user_id,
            category=category,
            status=TicketStatus.OPEN,
            text=mask_text(text),
        )
        self.db_session.add(ticket)
        return CreateTicketResult(
            ticket_id=ticket.id,
            status=TicketStatus.OPEN,
            category=category,
        )

    def _parse_list_statuses(
        self, statuses: list[str] | None
    ) -> list[TicketStatus]:
        """Resolve list filter; unknown strings are ``NOT_ELIGIBLE``."""
        if statuses is None:
            return list(constants.DEFAULT_LIST_STATUSES)
        parsed: list[TicketStatus] = []
        for raw in statuses:
            matched = _STATUS_BY_VALUE.get(raw)
            if matched is None:
                raise DomainError(
                    DomainErrorCode.NOT_ELIGIBLE,
                    "unknown ticket status",
                )
            parsed.append(matched)
        return parsed

    async def list_my_tickets(
        self,
        *,
        user_id: str,
        statuses: list[str] | None = None,
    ) -> list[TicketSummary]:
        """List tickets for ``user_id`` only.

        ``statuses`` omitted/``None`` defaults to ``open``, ``escalated``,
        and ``answered``. Empty ``statuses=[]`` returns no rows.
        """
        user_id = self._require_user_id(user_id)
        status_filter = self._parse_list_statuses(statuses)
        if not status_filter:
            return []
        tickets = (
            await self.db_session.scalars(
                select(Ticket)
                .where(
                    Ticket.user_id == user_id,
                    Ticket.status.in_(status_filter),
                )
                .order_by(Ticket.updated_at.desc())
            )
        ).all()
        return [
            TicketSummary(
                ticket_id=ticket.id,
                category=ticket.category,
                status=ticket.status,
                text=ticket.text,
                updated_at=ticket.updated_at,
            )
            for ticket in tickets
        ]

    async def append_message(
        self,
        *,
        user_id: str,
        ticket_id: str,
        text: str,
        role: MessageRole,
        model: str | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
    ) -> AppendMessageResult:
        """Record history and refresh activity time so escalate waits.

        Inserts one message on an existing ticket and sets
        ``ticket.updated_at``. Does not change ticket text or status. Required
        ``ticket_id`` must exist and match ``user_id`` or the call is
        ``NOT_FOUND``. Agent usage lands on agent rows only.
        """

        user_id = self._require_user_id(user_id)
        ticket = await self._require_ticket_for_scope(
            user_id, ticket_id.strip()
        )

        message = Message(
            id=new_id(),
            ticket_id=ticket.id,
            role=role,
            text=mask_text(text),
        )
        if role == MessageRole.AGENT:
            message.model = model
            message.tokens_in = tokens_in
            message.tokens_out = tokens_out
            message.latency_ms = latency_ms
        self.db_session.add(message)
        ticket.updated_at = utcnow()
        return AppendMessageResult(
            message_id=message.id,
            ticket_id=ticket.id,
        )

    async def escalate_stale(
        self,
        *,
        older_than_seconds: int | None = None,
    ) -> EscalateStaleResponse:
        """Set ``open`` tickets past the inactivity threshold to ``escalated``.

        Status-only: no extra message rows.
        """
        threshold = (
            older_than_seconds
            if older_than_seconds is not None
            else self.settings.escalation_seconds
        )
        cutoff = utcnow() - timedelta(seconds=threshold)
        stale_tickets = (
            await self.db_session.scalars(
                select(Ticket).where(
                    Ticket.status == TicketStatus.OPEN,
                    Ticket.updated_at < cutoff,
                )
            )
        ).all()

        now = utcnow()
        ticket_ids: list[str] = []
        for ticket in stale_tickets:
            ticket.status = TicketStatus.ESCALATED
            ticket.updated_at = now
            ticket_ids.append(ticket.id)

        return EscalateStaleResponse(
            ticket_ids=ticket_ids, count=len(ticket_ids)
        )
