"""Versioned domain contracts (no I/O)."""

from contracts.enums import (
    DomainErrorCode,
    MessageRole,
    TicketCategory,
    TicketStatus,
)
from contracts.models import (
    EscalateStaleRequest,
    EscalateStaleResponse,
    TicketSummary,
)

__all__ = [
    "DomainErrorCode",
    "EscalateStaleRequest",
    "EscalateStaleResponse",
    "MessageRole",
    "TicketCategory",
    "TicketStatus",
    "TicketSummary",
]
