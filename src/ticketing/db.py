"""ORM models for tickets and messages.

Enums are VARCHAR-backed (``native_enum=False``). Text columns store
one-way-masked content. Employee scope is ``tickets.user_id`` (MVP
synthetic sender email) — not production identity authentication.
A message always belongs to a ticket.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from contracts.enums import MessageRole, TicketCategory, TicketStatus
from ticketing import constants


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


def _string_enum(enum_cls: type[StrEnum], *, length: int = 32) -> Enum:
    """Build an ``Enum`` type for ``enum_cls`` (member ``.value``s)."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda members: [m.value for m in members],
    )


class Base(DeclarativeBase):
    # Shared MetaData registry for all models.
    # create_all / Alembic see every table in one place.
    pass


class Ticket(Base):
    """Independently tracked help-desk work item for one user scope."""

    __tablename__ = constants.TABLE_TICKETS

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id
    )
    user_id: Mapped[str] = mapped_column(
        String(320),
        index=True,
        comment="Synthetic sender email (MVP employee scope key)",
    )
    category: Mapped[TicketCategory] = mapped_column(
        _string_enum(TicketCategory)
    )
    status: Mapped[TicketStatus] = mapped_column(
        _string_enum(TicketStatus), index=True
    )
    text: Mapped[str] = mapped_column(
        Text,
        comment="Ticket text",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    messages: Mapped[list[Message]] = relationship(back_populates="ticket")


class Message(Base):
    """Immutable contribution belonging to a ticket."""

    __tablename__ = constants.TABLE_MESSAGES

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(f"{constants.TABLE_TICKETS}.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(_string_enum(MessageRole))
    text: Mapped[str] = mapped_column(
        Text, comment="Message text after PII masking"
    )
    model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Model that produced the reply (when role=agent)",
    )
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    ticket: Mapped[Ticket] = relationship(
        back_populates=constants.TABLE_MESSAGES
    )


def make_engine(database_url: str) -> AsyncEngine:
    # psycopg3 async driver via postgresql+psycopg:// (greenlet required).
    return create_async_engine(database_url, pool_pre_ping=True)


def make_session_factory(
    database_url: str,
) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = make_engine(database_url)
    return (
        async_sessionmaker(bind=engine, expire_on_commit=False),
        engine,
    )
