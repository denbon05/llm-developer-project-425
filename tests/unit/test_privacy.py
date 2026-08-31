"""Unit tests for one-way email/phone/card masking."""

from privacy import constants
from privacy.masking import mask_text


def test_mask_email_phone_and_luhn_card() -> None:
    """Email, phone-like values, and Luhn cards become placeholders."""
    text = "Contact a@b.co or +33 1 23 45 67 89; card 4111111111111111"
    masked = mask_text(text)
    assert constants.PLACEHOLDER_EMAIL in masked
    assert "+** *** ** ** 89" in masked
    assert constants.PLACEHOLDER_CARD in masked
    assert "a@b.co" not in masked
    assert "4111111111111111" not in masked


def test_non_luhn_digits_not_masked_as_card() -> None:
    """Digits that fail Luhn stay in the text (not treated as a card)."""
    # Last digit is a Luhn check digit; …1112 fails it, so not a card.
    text = "ref 4111111111111112"
    assert "4111111111111112" in mask_text(text)
