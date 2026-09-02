"""Unit tests for toxicity/injection/greeting canned SMTP bodies."""

from email_gateway import constants
from email_gateway.replies import StaticReplySource, match_static_reply

_GREETING_BODY = "Hi there!"
_GREETING_WITH_QUESTION = "Hello, I need VPN access"
_TOXIC_TERM = constants.TOXICITY_TERMS[0]
_TOXIC_IN_BODY = f"hi you {_TOXIC_TERM}"
# Must remain in constants.TOXICITY_TERMS (subject-only match).
_SHUT_UP = "shut up"
_VPN_QUESTION = "please enable vpn"
_DROP_TABLE = next(
    term
    for term in constants.INJECTION_PHRASE_TERMS
    if term.casefold() == "drop table"
)


def test_plain_greeting_matches() -> None:
    """Whole-message hello selects the greeting SMTP body."""
    reply = match_static_reply(subject="Hello", body=_GREETING_BODY)
    assert reply is not None
    assert reply.source is StaticReplySource.GREETING
    assert reply.text == constants.GREETING_REPLY_TEXT


def test_greeting_ignores_extra_whitespace() -> None:
    """Collapsed whitespace still matches a greeting-only message."""
    reply = match_static_reply(subject="", body="  good   morning  \n")
    assert reply is not None
    assert reply.source is StaticReplySource.GREETING


def test_question_after_hello_is_not_a_greeting() -> None:
    """Hello plus a real request is not a greeting-only match."""
    assert (
        match_static_reply(subject="Hello", body=_GREETING_WITH_QUESTION)
        is None
    )


def test_toxicity_beats_greeting() -> None:
    """Toxicity wins over greeting when both could apply."""
    reply = match_static_reply(subject="hi", body=_TOXIC_IN_BODY)
    assert reply is not None
    assert reply.source is StaticReplySource.TOXICITY
    assert reply.text == constants.STATIC_ACK_TEXT


def test_toxicity_in_subject_only() -> None:
    """A toxicity term in Subject only still selects the static ack."""
    reply = match_static_reply(subject=_SHUT_UP, body=_VPN_QUESTION)
    assert reply is not None
    assert reply.source is StaticReplySource.TOXICITY


def test_drop_table_in_subject_only() -> None:
    """DROP TABLE in Subject only still selects the static ack."""
    reply = match_static_reply(subject=_DROP_TABLE, body=_VPN_QUESTION)
    assert reply is not None
    assert reply.source is StaticReplySource.INJECTION
    assert reply.text == constants.STATIC_ACK_TEXT


def test_toxicity_beats_injection_phrase() -> None:
    """Toxicity wins over a cheap injection/SQL phrase when both match."""
    phrase = constants.INJECTION_PHRASE_TERMS[0]
    reply = match_static_reply(subject="hi", body=f"{_TOXIC_TERM} {phrase}")
    assert reply is not None
    assert reply.source is StaticReplySource.TOXICITY
    assert reply.text == constants.STATIC_ACK_TEXT


def test_injection_phrase_beats_greeting() -> None:
    """A cheap injection/SQL phrase wins over a greeting-only body."""
    phrase = constants.INJECTION_PHRASE_TERMS[0]
    reply = match_static_reply(subject=phrase, body=_GREETING_BODY)
    assert reply is not None
    assert reply.source is StaticReplySource.INJECTION
    assert reply.text == constants.STATIC_ACK_TEXT


def test_vpn_question_without_injection_phrase_is_not_static() -> None:
    """A real VPN question without intake phrases is not a canned reply."""
    assert match_static_reply(subject="VPN", body=_VPN_QUESTION) is None
