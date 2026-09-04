"""Versioned domain contracts (no I/O)."""

from contracts.enums import (
    DomainErrorCode,
    MessageRole,
    TicketCategory,
    TicketStatus,
)
from contracts.models import (
    EscalatedTicket,
    EscalateStaleRequest,
    EscalateStaleResponse,
    TicketSummary,
)

__all__ = [
    "DomainErrorCode",
    "EscalatedTicket",
    "EscalateStaleRequest",
    "EscalateStaleResponse",
    "MessageRole",
    "TicketCategory",
    "TicketStatus",
    "TicketSummary",
]
