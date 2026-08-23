"""Versioned Pydantic DTOs for ticket summaries and escalate-stale."""

from datetime import datetime

from pydantic import BaseModel, Field

from contracts.enums import TicketCategory, TicketStatus

CONTRACT_VERSION = "1"


class TicketSummary(BaseModel):
    """Scoped ticket row for employee list views."""

    ticket_id: str
    category: TicketCategory
    status: TicketStatus
    text: str
    updated_at: datetime


class EscalateStaleRequest(BaseModel):
    """Optional inactivity threshold in seconds."""

    older_than_seconds: int | None = Field(default=None, ge=0)


class EscalateStaleResponse(BaseModel):
    """Tickets moved from ``open`` to ``escalated`` in this call."""

    ticket_ids: list[str]
    count: int
