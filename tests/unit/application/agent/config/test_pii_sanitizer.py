import pytest

from skiller.application.agent.config.pii_sanitizer import PiiSanitizer

pytestmark = pytest.mark.unit


def test_pii_sanitizer_redacts_email() -> None:
    sanitizer = PiiSanitizer()

    result = sanitizer.sanitize_text("contact me at user.test+alerts@example.com")

    assert result == "contact me at ***REDACTED_EMAIL***"


def test_pii_sanitizer_redacts_phone_numbers() -> None:
    sanitizer = PiiSanitizer()

    result = sanitizer.sanitize_text("call +34 600 123 456 or 555-123-4567")

    assert "***REDACTED_PHONE***" in result
    assert "+34 600 123 456" not in result
    assert "555-123-4567" not in result
