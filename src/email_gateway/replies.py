"""Canned SMTP bodies from subject/body regex. First matching rule wins."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from email_gateway import constants


class StaticReplySource(StrEnum):
    """Which intake rule produced the canned body."""

    TOXICITY = "toxicity"
    GREETING = "greeting"


@dataclass(frozen=True)
class StaticReply:
    """A canned SMTP body chosen from inbound subject and body."""

    source: StaticReplySource
    text: str


@dataclass(frozen=True)
class _Rule:
    """One intake check: if ``matches(subject, body)``, send ``text``."""

    source: StaticReplySource
    text: str
    matches: Callable[[str, str], bool]


def _compile_toxicity_re(terms: tuple[str, ...]) -> re.Pattern[str]:
    """Build an OR-pattern: whole words get ``\\b``; phrases do not."""
    parts: list[str] = []
    for term in terms:
        escaped = re.escape(term)
        # Multi-word terms: no \\b (spaces already bound the phrase).
        if " " in term:
            parts.append(escaped)
        else:
            parts.append(rf"\b{escaped}\b")
    return re.compile("|".join(parts), re.IGNORECASE)


_TOXICITY_RE = _compile_toxicity_re(constants.TOXICITY_TERMS)
# Whole remaining text only; a greeting plus a question is not a greeting.
_GREETING_RE = re.compile(
    r"^(?:"
    r"hi|hello|hey|yo|"
    r"good\s+(?:morning|afternoon|evening|day)"
    r")(?:\s+(?:there|team|all|folks))?"
    r"[\s!.,?]*$",
    re.IGNORECASE,
)


def _is_toxic(subject: str, body: str) -> bool:
    """True if any toxicity term appears in subject or body."""
    return _TOXICITY_RE.search(f"{subject}\n{body}") is not None


def _is_greeting(subject: str, body: str) -> bool:
    """True when the whole remaining text is only a greeting (no question)."""
    blob = " ".join((body or "").split()) or " ".join((subject or "").split())
    return bool(blob) and _GREETING_RE.fullmatch(blob) is not None


# First matching rule wins (toxicity before greeting).
_RULES: tuple[_Rule, ...] = (
    _Rule(StaticReplySource.TOXICITY, constants.STATIC_ACK_TEXT, _is_toxic),
    _Rule(
        StaticReplySource.GREETING, constants.GREETING_REPLY_TEXT, _is_greeting
    ),
)


def match_static_reply(*, subject: str, body: str) -> StaticReply | None:
    """First canned body whose rule matches ``subject`` and ``body``."""
    for rule in _RULES:
        if rule.matches(subject, body):
            return StaticReply(source=rule.source, text=rule.text)
    return None
