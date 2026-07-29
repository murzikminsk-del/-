from app.observability.pii import redact_pii

def test_email_redacted():
    result = redact_pii("Мой email ivan@mail.ru")
    assert "ivan@mail.ru" not in result
    assert "[EMAIL]" in result

def test_phone_redacted():
    result = redact_pii("тел +7 (999) 123-45-67")
    assert "+7 (999) 123-45-67" not in result
    assert "[PHONE_RU]" in result

def test_card_redacted():
    result = redact_pii("карта 4111 1111 1111 1111")
    assert "4111 1111 1111 1111" not in result
    assert "[CARD]" in result

def test_combined_pii():
    text = "Мой email ivan@mail.ru, тел +7 (999) 123-45-67, карта 4111 1111 1111 1111"
    result = redact_pii(text)
    assert "ivan@mail.ru" not in result
    assert "+7 (999) 123-45-67" not in result
    assert "4111 1111 1111 1111" not in result
    assert "[EMAIL]" in result
    assert "[PHONE_RU]" in result
    assert "[CARD]" in result