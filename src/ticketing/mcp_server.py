"""MCP adapter: create-ticket, list-my-tickets, append-message.

``user_id`` (sender email, MVP) is a tool argument. Create-ticket ``text``
is the ticket field; append-message ``text`` is the chat line. Both are
untrusted data.

``mcp_*`` functions own the adapter logic. ``@mcp.tool`` wrappers expose
the same arguments (including ``user_id``). Contract tests call ``mcp_*``
directly without an MCP HTTP session.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.enums import DomainErrorCode, MessageRole, TicketCategory
from ticketing.config import Settings
from ticketing.service import DomainError, TicketingService

mcp = MCPServer("ticketing")


@dataclass
class McpRuntime:
    """Process-wide MCP wiring: settings plus a DB session opener."""

    settings: Settings
    make_db_session: async_sessionmaker[AsyncSession]


_runtime: McpRuntime | None = None


def configure_mcp_runtime(
    settings: Settings,
    make_db_session: async_sessionmaker[AsyncSession],
) -> None:
    """Bind settings and DB session opener for all MCP tool calls."""
    global _runtime
    _runtime = McpRuntime(settings, make_db_session)


def _runtime_or_raise() -> McpRuntime:
    """Return configured runtime, or fail if lifespan never bound it."""
    if _runtime is None:
        raise RuntimeError("MCP runtime not configured")
    return _runtime


def _tool_error(code: DomainErrorCode, message: str) -> dict:
    """Stable MCP error envelope using the shared domain code vocabulary."""
    return {"error": {"code": code, "message": message}}


async def _run(
    fn: Callable[[TicketingService], Awaitable[Any]],
) -> Any:
    """Open a DB session, run ``fn``, commit on success, else roll back.

    ``DomainError`` becomes the MCP error envelope; other exceptions propagate
    after rollback.
    """
    rt = _runtime_or_raise()
    db_session = rt.make_db_session()
    try:
        service = TicketingService(db_session, rt.settings)
        result = await fn(service)
        await db_session.commit()
        return result
    except DomainError as exc:
        await db_session.rollback()
        return _tool_error(exc.code, exc.message)
    except Exception:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()


async def mcp_create_ticket(
    *,
    user_id: str,
    category: str,
    text: str,
) -> dict:
    """Create one scoped ``open`` ticket (explicit ``user_id``)."""

    async def op(service: TicketingService):
        result = await service.create_ticket(
            user_id=user_id,
            category=TicketCategory(category),
            text=text,
        )
        return {
            "ticket_id": result.ticket_id,
            "status": result.status,
            "category": result.category,
        }

    return await _run(op)


async def mcp_list_my_tickets(*, user_id: str) -> dict:
    """List tickets for ``user_id`` only."""

    async def op(service: TicketingService):
        tickets = await service.list_my_tickets(user_id=user_id)
        return {
            "tickets": [
                {
                    "ticket_id": ticket.ticket_id,
                    "category": ticket.category,
                    "status": ticket.status,
                    "updated_at": ticket.updated_at.isoformat(),
                }
                for ticket in tickets
            ]
        }

    return await _run(op)


async def mcp_append_message(
    *,
    user_id: str,
    ticket_id: str,
    text: str,
    role: str,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
) -> dict:
    """Insert one user or agent message on an existing ticket."""

    async def op(service: TicketingService):
        result = await service.append_message(
            user_id=user_id,
            ticket_id=ticket_id,
            text=text,
            role=MessageRole(role),
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
        )
        return {
            "message_id": result.message_id,
            "ticket_id": result.ticket_id,
        }

    return await _run(op)


@mcp.tool(name="create-ticket")
async def create_ticket(
    user_id: str,
    category: str,
    text: str,
) -> dict:
    """Create one scoped ticket; ``user_id`` is sender email."""
    return await mcp_create_ticket(
        user_id=user_id,
        category=category,
        text=text,
    )


@mcp.tool(name="list-my-tickets")
async def list_my_tickets(user_id: str) -> dict:
    """List tickets for the ``user_id`` tool argument only."""
    return await mcp_list_my_tickets(user_id=user_id)


@mcp.tool(name="append-message")
async def append_message(
    user_id: str,
    ticket_id: str,
    text: str,
    role: str,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    latency_ms: int | None = None,
) -> dict:
    """Insert one message (``role`` user/agent) on an existing ticket."""
    return await mcp_append_message(
        user_id=user_id,
        ticket_id=ticket_id,
        text=text,
        role=role,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
    )
