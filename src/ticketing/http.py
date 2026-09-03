"""HTTP routes for scheduled stale-ticket escalation."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from contracts.enums import DomainErrorCode
from contracts.models import EscalateStaleRequest, EscalateStaleResponse
from ticketing.logging_config import get_logger
from ticketing.service import DomainError, TicketingService

logger = get_logger(__name__)

router = APIRouter(prefix="/v1")

# Adapter-only: HTTP status for each domain code (domain stays protocol-free).
_DOMAIN_HTTP_STATUS: dict[DomainErrorCode, int] = {
    DomainErrorCode.FORBIDDEN: 403,
    DomainErrorCode.UNAUTHORIZED: 401,
    DomainErrorCode.NOT_FOUND: 404,
    DomainErrorCode.CONFLICT: 409,
    DomainErrorCode.INVALID_TRANSITION: 409,
    DomainErrorCode.NOT_ELIGIBLE: 409,
    DomainErrorCode.INTERNAL: 500,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Map ``DomainError`` once for all private HTTP routes."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        _request: Request, exc: DomainError
    ) -> JSONResponse:
        status = _DOMAIN_HTTP_STATUS.get(exc.code, 400)
        return JSONResponse(
            status_code=status,
            content={
                "detail": {"code": exc.code, "message": exc.message},
            },
        )


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Open one ORM session per request; commit on success, else roll back."""
    factory = request.app.state.db_session_factory
    db_session = factory()
    try:
        yield db_session
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()


def get_service(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> TicketingService:
    """Build the domain service with request-scoped ORM session and settings."""
    return TicketingService(
        db_session=db_session, settings=request.app.state.settings
    )


@router.post("/tickets/escalate-stale", response_model=EscalateStaleResponse)
async def escalate_stale(
    body: EscalateStaleRequest | None = None,
    service: TicketingService = Depends(get_service),
) -> EscalateStaleResponse:
    """Escalate ``open`` tickets older than the create-age threshold.

    JSON ``older_than_seconds`` is optional; omitted uses
    ``Settings.escalation_seconds``. Status-only — no message rows.
    """
    threshold = body.older_than_seconds if body is not None else None
    effective_threshold = (
        threshold
        if threshold is not None
        else service.settings.escalation_seconds
    )
    logger.info(
        "escalate-stale started older_than_seconds=%s",
        effective_threshold,
    )
    result = await service.escalate_stale(older_than_seconds=threshold)
    logger.info(
        "escalate-stale finished count=%s ticket_ids=%s",
        result.count,
        result.ticket_ids,
    )
    return result
