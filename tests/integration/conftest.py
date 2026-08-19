"""GreenMail container fixtures for email-gateway tests (no ticketing DB)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from http import HTTPStatus

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from email_gateway import constants
from email_gateway.config import Settings

from .greenmail import (
    EMPLOYEE_EMAIL,
    EMPLOYEE_PASSWORD,
    GREENMAIL_API_PORT,
    GREENMAIL_IMAP_PORT,
    GREENMAIL_OPTS,
    GREENMAIL_SMTP_PORT,
    SUPPORT_EMAIL,
    SUPPORT_PASSWORD,
    GreenMailEndpoints,
    purge_inbox,
)
from .testdata import (
    CITATION_REPO_BASE,
    DIFY_APP_KEY,
    DIFY_TIMEOUT_SECONDS,
    DIFY_WORKFLOW_URL,
    POLL_INTERVAL_SECONDS,
)

# Image start can pull/boot slowly on a cold Docker.
_GREENMAIL_STARTUP_TIMEOUT = timedelta(seconds=120)


# One container for sequential tests; isolate by purging inboxes, not
# per-test Docker.
@pytest.fixture(scope="module")
def greenmail() -> Iterator[GreenMailEndpoints]:
    """One GreenMail container for the module; host ports are mapped."""
    container = (
        DockerContainer("greenmail/standalone:2.1.11")
        .with_env("GREENMAIL_OPTS", GREENMAIL_OPTS)
        .with_exposed_ports(
            GREENMAIL_SMTP_PORT,
            GREENMAIL_IMAP_PORT,
            GREENMAIL_API_PORT,
        )
        .waiting_for(
            HttpWaitStrategy(
                GREENMAIL_API_PORT,
                "/api/service/readiness",
            )
            .for_status_code(HTTPStatus.OK)
            .with_startup_timeout(_GREENMAIL_STARTUP_TIMEOUT)
        )
    )
    with container as running:
        host = running.get_container_host_ip()
        yield GreenMailEndpoints(
            host=host,
            smtp_port=int(running.get_exposed_port(GREENMAIL_SMTP_PORT)),
            imap_port=int(running.get_exposed_port(GREENMAIL_IMAP_PORT)),
        )


@pytest.fixture
def gateway_settings(greenmail: GreenMailEndpoints) -> Settings:
    """Gateway settings aimed at this test's GreenMail; Dify URL is unused."""
    return Settings(
        imap_host=greenmail.host,
        imap_port=greenmail.imap_port,
        imap_user=SUPPORT_EMAIL,
        imap_password=SUPPORT_PASSWORD,
        smtp_host=greenmail.host,
        smtp_port=greenmail.smtp_port,
        smtp_user=SUPPORT_EMAIL,
        smtp_password=SUPPORT_PASSWORD,
        dify_workflow_url=DIFY_WORKFLOW_URL,
        dify_email_helpdesk_api_key=DIFY_APP_KEY,
        email_poll_interval_seconds=POLL_INTERVAL_SECONDS,
        dify_timeout_seconds=DIFY_TIMEOUT_SECONDS,
        citation_repo_base=CITATION_REPO_BASE,
        static_ack_text=constants.STATIC_ACK_TEXT,
    )


@pytest.fixture(autouse=True)
def empty_mailboxes(greenmail: GreenMailEndpoints) -> Iterator[None]:
    """EXPUNGE support and employee INBOXes before and after each test."""
    purge_inbox(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)
    purge_inbox(greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
    yield
    purge_inbox(greenmail, SUPPORT_EMAIL, SUPPORT_PASSWORD)
    purge_inbox(greenmail, EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)
