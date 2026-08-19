"""Blocking Dify Service API (``POST …/v1/workflows/run``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from email_gateway import constants
from email_gateway.config import Settings, build_authorization_header
from email_gateway.logging_config import get_logger
from email_gateway.outputs import OutputsError, ValidatedOutputs, parse_outputs

logger = get_logger(__name__)


@dataclass(frozen=True)
class CallResult:
    """One blocking workflow call.

    - ``outputs`` — set only when End fields passed validation.
    - ``workflow_run_id`` — ``None`` when Dify omitted it or we have no body.
    """

    ok: bool
    outputs: ValidatedOutputs | None
    workflow_run_id: str | None


class Client:
    """POST blocking run; never logs request/response content."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
    ) -> None:
        """Use the shared httpx client (processor owns its lifetime)."""
        self._settings = settings
        self._http = http_client

    async def run_blocking_workflow(
        self,
        *,
        user_email: str,
        subject: str,
        request_text: str,
    ) -> CallResult:
        """POST Start fields; wait for End outputs or a transport/HTTP miss."""
        headers = {
            "Authorization": build_authorization_header(
                self._settings.dify_email_helpdesk_api_key
            ),
            "Content-Type": "application/json",
        }
        body = {
            "inputs": {
                "user_email": user_email,
                "subject": subject,
                "request_text": request_text,
            },
            # blocking: HTTP returns only after the workflow End node.
            "response_mode": "blocking",
            "user": user_email,
        }
        # Transport: no response object if connect/timeout/reset fails.
        try:
            response = await self._http.post(
                self._settings.dify_workflow_url,
                json=body,
                headers=headers,
                timeout=self._settings.dify_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            logger.exception(
                "dify_http_error",
                extra={"exc_type": type(exc).__name__},
            )
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=None,
            )
        if response.status_code >= constants.HTTP_ERROR_STATUS_MIN:
            logger.warning(
                "dify_http_status",
                extra={"http_status": response.status_code},
            )
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=None,
            )
        # Body: 2xx must still be JSON before we look at End outputs.
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            logger.exception(
                "dify_bad_json",
                extra={
                    "http_status": response.status_code,
                    "exc_type": type(exc).__name__,
                },
            )
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=None,
            )
        run_id = _read_workflow_run_id(payload)
        # Contract: HTTP+JSON succeeded; End outputs may still be unusable.
        try:
            outputs = parse_outputs(
                payload,
                citation_repo_base=self._settings.citation_repo_base,
            )
        except OutputsError as exc:
            logger.exception(
                "dify_outputs_invalid",
                extra={
                    "workflow_run_id": run_id,
                    "exc_type": type(exc).__name__,
                },
            )
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=run_id,
            )
        logger.info(
            "dify_run_ok",
            extra={"workflow_run_id": run_id},
        )
        return CallResult(
            ok=True,
            outputs=outputs,
            workflow_run_id=run_id,
        )


def _read_workflow_run_id(payload: dict[str, Any]) -> str | None:
    """Opaque id from the JSON root, else from ``data`` (Dify uses both)."""
    root_run_id = payload.get("workflow_run_id")
    if isinstance(root_run_id, str) and root_run_id:
        return root_run_id
    data = payload.get("data")
    if isinstance(data, dict):
        nested_run_id = data.get("id") or data.get("workflow_run_id")
        if isinstance(nested_run_id, str) and nested_run_id:
            return nested_run_id
    return None
