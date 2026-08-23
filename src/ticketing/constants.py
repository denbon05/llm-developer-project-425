"""Ticketing table names and other shared constants."""

from contracts.enums import TicketStatus

TABLE_TICKETS = "tickets"
TABLE_MESSAGES = "messages"

DEFAULT_LIST_STATUSES: tuple[TicketStatus, ...] = (
    TicketStatus.OPEN,
    TicketStatus.ESCALATED,
    TicketStatus.ANSWERED,
)
"""Statuses for an in-process ticket (any status except ``closed``)."""
