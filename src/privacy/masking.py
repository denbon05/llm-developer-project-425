"""One-way PII masking for pre-model and persistence seams.

Replaces matches with ``constants.PLACEHOLDER_*`` tokens; not reversible
encrypt/decrypt. Ticket/message text must be masked before durable business
fields; raw transport mail is outside this invariant.
"""

from __future__ import annotations

import re

from privacy import constants

# ISO/IEC 7812 primary account number (PAN) digit length.
_CARD_DIGITS_MIN = 13
_CARD_DIGITS_MAX = 19

# Digit count for phone-like matches after stripping separators (E.164-ish).
_PHONE_DIGITS_MIN = 10
_PHONE_DIGITS_MAX = 15

# Luhn: every second digit from the right is doubled; reduce 10–18 to one digit.
_LUHN_DOUBLE_THRESHOLD = 9
_LUHN_CHECK_MODULUS = 10

_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
)
# Phone-like: optional +, digit groups with separators totaling 10–15 digits.
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{8,18}\d)(?!\w)",
)
_CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")


def _luhn_ok(digits: str) -> bool:
    """Return True if ``digits`` is a Luhn-valid PAN-length number.

    Walks digits right-to-left: odd positions (1-based from the right) are
    doubled, then reduced (``n > 9`` → ``n - 9``). Valid when the sum is
    divisible by 10.
    """
    if not _CARD_DIGITS_MIN <= len(digits) <= _CARD_DIGITS_MAX:
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        # Positions 1, 3, 5… from the right (0-based odd indices after reverse).
        if i % 2 == 1:
            n *= 2
            if n > _LUHN_DOUBLE_THRESHOLD:
                n -= _LUHN_DOUBLE_THRESHOLD
        total += n
    return total % _LUHN_CHECK_MODULUS == 0


def _mask_card(match: re.Match[str]) -> str:
    """Replace a Luhn-valid card candidate with the card placeholder."""
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if _luhn_ok(digits):
        return constants.PLACEHOLDER_CARD
    return raw


def _mask_phone(match: re.Match[str]) -> str:
    """Replace a phone-like digit run with the phone placeholder."""
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if _PHONE_DIGITS_MIN <= len(digits) <= _PHONE_DIGITS_MAX:
        return constants.PLACEHOLDER_PHONE
    return raw


def mask_text(text: str) -> str:
    """Mask required PII classes (one-way placeholders).

    Order is emails, then Luhn-valid cards, then phone-like values so card
    digit runs are not misclassified as phones and addresses stay intact.
    """
    masked = _EMAIL_RE.sub(constants.PLACEHOLDER_EMAIL, text)
    masked = _CARD_CANDIDATE_RE.sub(_mask_card, masked)
    masked = _PHONE_RE.sub(_mask_phone, masked)
    return masked
