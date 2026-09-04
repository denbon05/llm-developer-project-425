"""Blocking Dify Service API (``POST …/v1/workflows/run``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import httpx

from email_gateway.config import Settings, build_authorization_header
from email_gateway.outputs import OutputsError, ValidatedOutputs, parse_outputs

# Dify error ``code`` tokens are short identifiers, never mail content.
_DIFY_ERROR_CODE_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_WORKFLOW_STATUS_VALUES = frozenset(
    {"succeeded", "failed", "stopped", "running"}
)


@dataclass(frozen=True)
class CallResult:
    """One blocking workflow call.

    - ``outputs`` — set only when End fields passed validation.
    - ``workflow_run_id`` — ``None`` when Dify omitted it or we have no body.
    - ``fail_reason`` — stable class of failure; ``None`` on success.
    - ``exc_type`` — exception class name when a client-side parse/transport
      error occurred; ``None`` otherwise.
    """

    ok: bool
    outputs: ValidatedOutputs | None
    workflow_run_id: str | None
    fail_reason: str | None = None
    http_status: int | None = None
    outputs_error: str | None = None
    dify_error_code: str | None = None
    workflow_status: str | None = None
    exc_type: str | None = None


class Client:
    """POST blocking run; map HTTP/JSON outcomes onto ``CallResult``."""

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
        blockquote: str,
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
                "blockquote": blockquote,
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
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=None,
                fail_reason="http_error",
                exc_type=type(exc).__name__,
            )
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            error_code = _safe_dify_error_code(_json_object(response))
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=None,
                fail_reason="http_status",
                http_status=response.status_code,
                dify_error_code=error_code,
            )
        # Body: 2xx must still be JSON before we look at End outputs.
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=None,
                fail_reason="bad_json",
                http_status=response.status_code,
                exc_type=type(exc).__name__,
            )
        run_id = _read_workflow_run_id(payload)
        workflow_status = _read_workflow_status(payload)
        # Contract: HTTP+JSON succeeded; End outputs may still be unusable.
        try:
            outputs = parse_outputs(
                payload,
                citation_url_base=self._settings.citation_url_base,
            )
        except OutputsError as exc:
            return CallResult(
                ok=False,
                outputs=None,
                workflow_run_id=run_id,
                fail_reason="outputs_invalid",
                outputs_error=str(exc),
                workflow_status=workflow_status,
                exc_type=type(exc).__name__,
            )
        return CallResult(
            ok=True,
            outputs=outputs,
            workflow_run_id=run_id,
            workflow_status=workflow_status,
        )


def _json_object(response: httpx.Response) -> dict[str, Any] | None:
    """Parse a JSON object body; ``None`` if missing or not an object."""
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_dify_error_code(payload: dict[str, Any] | None) -> str | None:
    """Return Dify ``code`` only when it is a short opaque token."""
    if payload is None:
        return None
    code = payload.get("code")
    if isinstance(code, str) and _DIFY_ERROR_CODE_RE.fullmatch(code):
        return code
    return None


def _read_workflow_status(payload: dict[str, Any]) -> str | None:
    """Known ``data.status`` tokens only (never free-form error text)."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    if isinstance(status, str) and status in _WORKFLOW_STATUS_VALUES:
        return status
    return None


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
