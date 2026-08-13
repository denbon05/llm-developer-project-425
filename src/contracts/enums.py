"""Canonical ticket/message vocabulary."""

from enum import StrEnum


class MessageRole(StrEnum):
    """``user`` (employee) or ``agent`` (LLM chat line)."""

    USER = "user"
    AGENT = "agent"


class TicketCategory(StrEnum):
    """Help-desk category; ``other`` is legitimate but uncategorized."""

    BUG = "bug"
    ACCESS = "access"
    DOCS = "docs"
    FEATURE = "feature"
    OTHER = "other"


class TicketStatus(StrEnum):
    """Ticket lifecycle status."""

    OPEN = "open"
    ESCALATED = "escalated"
    ANSWERED = "answered"
    CLOSED = "closed"


class DomainErrorCode(StrEnum):
    """Stable domain failure codes."""

    FORBIDDEN = "forbidden"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INVALID_TRANSITION = "invalid_transition"
    NOT_ELIGIBLE = "not_eligible"
    INTERNAL = "internal"
