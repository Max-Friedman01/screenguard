from ai.detectors import find_sensitive_types, luhn_valid


def labels(text: str) -> set[str]:
    return {
        detection.label
        for detection in find_sensitive_types(text)
    }


def test_email():
    assert "email" in labels(
        "Contact asher@example.com today"
    )


def test_uk_phone():
    assert "phone" in labels(
        "Call 07123 456789"
    )


def test_card():
    assert "card" in labels(
        "Test card 4111 1111 1111 1111"
    )


def test_postcode():
    assert "postcode" in labels(
        "University M13 9PL"
    )


def test_sort_code():
    assert "bank" in labels(
        "Sort code 12-34-56"
    )


def test_account_number():
    assert "bank" in labels(
        "Account 12345678"
    )


def test_valid_luhn_number():
    assert luhn_valid(
        "4111 1111 1111 1111"
    )


def test_invalid_luhn_number():
    assert not luhn_valid(
        "4111 1111 1111 1112"
    )


def test_repeated_digits_are_rejected():
    assert not luhn_valid(
        "0000 0000 0000 0000"
    )


def test_safe_text():
    assert find_sensitive_types(
        "University helpdesk opens tomorrow"
    ) == []
