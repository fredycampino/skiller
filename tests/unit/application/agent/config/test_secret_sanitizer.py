import pytest

from skiller.application.agent.config.secret_sanitizer import SecretSanitizer

pytestmark = pytest.mark.unit


def test_secret_sanitizer_redacts_secret_pairs_in_text() -> None:
    sanitizer = SecretSanitizer()

    result = sanitizer.sanitize_text(
        "token: abc123 password=secret authorization: Bearer x"
    )

    assert "token=***REDACTED***" in result
    assert "password=***REDACTED***" in result
    assert "authorization=***REDACTED***" in result
    assert "abc123" not in result
    assert "secret" not in result


def test_secret_sanitizer_detects_sensitive_keys() -> None:
    sanitizer = SecretSanitizer()

    assert sanitizer.is_sensitive_key("api_key")
    assert sanitizer.is_sensitive_key("auth-token")
    assert sanitizer.is_sensitive_key("password_value")
    assert sanitizer.is_sensitive_key("authorizationHeader")
    assert sanitizer.is_sensitive_key("my_secret")
    assert not sanitizer.is_sensitive_key("safe_name")
