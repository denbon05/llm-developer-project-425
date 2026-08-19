"""Poll UNSEEN mail, mask, maybe Dify, SMTP-reply, then optional ``\\Seen``."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from email_gateway.clients import dify, mailbox
from email_gateway.config import Settings
from email_gateway.logging_config import get_logger
from email_gateway.replies import match_static_reply
from privacy.masking import mask_text

logger = get_logger(__name__)

# Log / extra ``reply_source`` values (not SMTP body text).
_REPLY_WORKFLOW_OUTPUTS = "workflow_outputs"
_REPLY_STATIC_ACK = "static_ack"


@dataclass(frozen=True)
class OutboundReply:
    """SMTP body the processor will send, plus log extras."""

    source: str
    text: str
    workflow_run_id: str | None = None


def build_outbound_from_workflow(
    result: dify.CallResult, *, static_ack: str
) -> OutboundReply:
    """Map a blocking workflow result to an SMTP body."""
    if result.ok and result.outputs is not None:
        return OutboundReply(
            source=_REPLY_WORKFLOW_OUTPUTS,
            text=result.outputs.reply_text,
            workflow_run_id=result.workflow_run_id,
        )
    return OutboundReply(
        source=_REPLY_STATIC_ACK,
        text=static_ack,
        workflow_run_id=result.workflow_run_id,
    )


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
        """Mask, optional Dify, SMTP; ``\\Seen`` only after send succeeds."""
        if not message.sender:
            logger.warning(
                "skip_no_sender",
                extra={"uid": message.uid, "skip_reason": "no_sender"},
            )
            return
        masked_subject = mask_text(message.subject)
        masked_body = mask_text(message.body)
        static_reply = match_static_reply(
            subject=masked_subject, body=masked_body
        )
        if static_reply is not None:
            outbound = OutboundReply(
                source=static_reply.source, text=static_reply.text
            )
        else:
            # no static reply, proceed with real workflow call
            # Blocking Service API: wait for End outputs, not a stream.
            workflow_result = await self._dify.run_blocking_workflow(
                user_email=message.sender,
                subject=masked_subject,
                request_text=masked_body,
            )
            outbound = build_outbound_from_workflow(
                workflow_result,
                static_ack=self._settings.static_ack_text,
            )
        sent = await asyncio.to_thread(
            self._mailbox.send_reply,
            to_addr=message.sender,
            subject=message.subject,
            body=outbound.text,
        )
        seen = False
        if sent and should_mark_seen:
            try:
                # mark as seen only after successful send
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
