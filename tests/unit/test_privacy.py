from privacy.masking import mask_text


def test_mask_email_phone_and_luhn_card() -> None:
    text = "Contact a@b.co or +1 (555) 123-4567; card 4111111111111111"
    masked = mask_text(text)
    assert "[EMAIL]" in masked
    assert "[PHONE]" in masked
    assert "[CARD]" in masked
    assert "a@b.co" not in masked
    assert "4111111111111111" not in masked


def test_non_luhn_digits_not_masked_as_card() -> None:
    # Last digit is a Luhn check digit; …1112 fails it, so not a card.
    text = "ref 4111111111111112"
    assert "4111111111111112" in mask_text(text)
