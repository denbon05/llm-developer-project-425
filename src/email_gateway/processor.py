"""Poll UNSEEN mail, mask, maybe Dify, SMTP-reply, then optional ``\\Seen``."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from email_gateway.clients import dify, mailbox
from email_gateway.config import Settings
from email_gateway.replies import match_static_reply
from privacy.masking import mask_text

logger = logging.getLogger(__name__)

# ``OutboundReply.source`` when the body came from workflow End outputs.
_REPLY_WORKFLOW_OUTPUTS = "workflow_outputs"


@dataclass(frozen=True)
class OutboundReply:
    """SMTP body, which path produced it, and optional workflow run id."""

    source: str
    text: str
    workflow_run_id: str | None = None


def build_outbound_from_workflow(
    result: dify.CallResult,
) -> OutboundReply | None:
    """Map success to an ``OutboundReply``; otherwise ``None``."""
    if result.ok and result.outputs is not None:
        return OutboundReply(
            source=_REPLY_WORKFLOW_OUTPUTS,
            text=result.outputs.reply_text,
            workflow_run_id=result.workflow_run_id,
        )
    return None


def _copy_failure_fields(uid: str, result: dify.CallResult) -> dict[str, Any]:
    """Copy ``uid`` and ``CallResult`` failure fields into a dict."""
    return {
        "uid": uid,
        "fail_reason": result.fail_reason,
        "http_status": result.http_status,
        "outputs_error": result.outputs_error,
        "dify_error_code": result.dify_error_code,
        "workflow_status": result.workflow_status,
        "workflow_run_id": result.workflow_run_id,
        "exc_type": result.exc_type,
    }


class Processor:
    """One IMAP batch is ``run_poll_cycle``; ``poll_with_interval`` sleeps."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Wire Dify + mailbox; own the HTTP client unless one is injected."""
        self._settings = settings
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient()
        self._dify = dify.Client(settings, self._http)
        self._mailbox = mailbox.Client(settings)

    async def close(self) -> None:
        """Close the HTTP client only when this processor created it."""
        if self._owns_http:
            await self._http.aclose()

    async def run_poll_cycle(self, *, should_mark_seen: bool = True) -> int:
        """Handle the current UNSEEN batch; return how many messages ran."""
        inbound_messages = await asyncio.to_thread(self._mailbox.fetch_unseen)
        for message in inbound_messages:
            await self.handle_inbound_message(
                message, should_mark_seen=should_mark_seen
            )
        logger.info("poll_cycle", extra={"count": len(inbound_messages)})
        return len(inbound_messages)

    async def handle_inbound_message(
        self,
        message: mailbox.InboundMessage,
        *,
        should_mark_seen: bool = True,
    ) -> None:
        """Mask, optional Dify, SMTP; no send or ``\\Seen`` on Dify failure."""
        if not message.sender:
            logger.warning(
                "skip_no_sender",
                extra={"uid": message.uid, "skip_reason": "no_sender"},
            )
            return
        masked_subject = mask_text(message.subject)
        masked_body = mask_text(message.body)
        # Toxicity / hello: static SMTP body, no Dify.
        static_reply = match_static_reply(
            subject=masked_subject, body=masked_body
        )
        if static_reply is not None:
            outbound = OutboundReply(
                source=static_reply.source, text=static_reply.text
            )
        else:
            # Blocking Service API: wait for End outputs, not a stream.
            workflow_result = await self._dify.run_blocking_workflow(
                user_email=message.sender,
                subject=masked_subject,
                request_text=masked_body,
            )
            outbound = build_outbound_from_workflow(workflow_result)
            if outbound is None:
                logger.error(
                    "workflow_failed",
                    extra=_copy_failure_fields(message.uid, workflow_result),
                )
                return
        sent = await asyncio.to_thread(
            self._mailbox.send_reply,
            to_addr=message.sender,
            subject=message.subject,
            body=outbound.text,
        )
        seen = False
        if sent and should_mark_seen:
            try:
                # ``\Seen`` only after SMTP accepted the reply.
                await asyncio.to_thread(self._mailbox.mark_seen, message.uid)
                seen = True
            except Exception as exc:
                logger.exception(
                    "imap_seen_failed",
                    extra={
                        "uid": message.uid,
                        "reply_source": outbound.source,
                        "exc_type": type(exc).__name__,
                    },
                )
        logger.info(
            "inbound_done",
            extra={
                "uid": message.uid,
                "reply_source": outbound.source,
                "seen": seen,
                "workflow_run_id": outbound.workflow_run_id,
            },
        )

    async def poll_with_interval(self) -> None:
        """Run poll cycles forever, sleeping ``email_poll_interval_seconds``."""
        interval = self._settings.email_poll_interval_seconds
        try:
            while True:
                try:
                    await self.run_poll_cycle()
                except Exception as exc:
                    logger.exception(
                        "poll_cycle_failed",
                        extra={"exc_type": type(exc).__name__},
                    )
                await asyncio.sleep(interval)
        finally:
            await self.close()
