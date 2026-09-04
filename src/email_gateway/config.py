"""Email-gateway settings from environment (optional ``.env`` file)."""

from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from email_gateway import constants


class Settings(BaseSettings):
    """Process config from environment (or an explicit constructor)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    operator_email: str
    dify_workflow_url: str
    dify_email_helpdesk_api_key: str
    # Default 1 minute (requirements); tests override.
    email_poll_interval_seconds: int = 60
    # Blocking HTTP wait; not the SMTP connect budget.
    dify_timeout_seconds: float = 60.0
    # Prefix for citation URLs (knowledge_base/ Markdown).
    citation_url_base: str = ""
    static_ack_text: str = constants.STATIC_ACK_TEXT
    # Private HTTP listener (in-network; same bind as ticketing internals).
    host: str = "0.0.0.0"
    port: int = 8080

    @model_validator(mode="after")
    def reject_operator_matching_imap_user(self) -> Self:
        """Digest must not land in the polled IMAP inbox."""
        operator = self.operator_email.strip().casefold()
        intake = self.imap_user.strip().casefold()
        if operator == intake:
            raise ValueError("operator_email must not equal imap_user")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached Settings from the environment."""
    return Settings.model_validate({})


def build_authorization_header(raw_key: str) -> str:
    """Build ``Authorization`` without doubling an existing Bearer prefix."""
    stripped_token = raw_key.strip().strip("'").strip('"')
    # Studio keys may already include the Bearer scheme.
    if stripped_token.lower().startswith("bearer "):
        return stripped_token
    return f"Bearer {stripped_token}"
