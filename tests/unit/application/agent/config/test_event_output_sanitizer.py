import pytest

from skiller.application.agent.config.event_output_sanitizer import (
    AgentEventOutputPolicy,
    AgentEventOutputSanitizer,
)

pytestmark = pytest.mark.unit


def test_agent_event_output_sanitizer_redacts_sensitive_keys_and_text() -> None:
    sanitizer = AgentEventOutputSanitizer()

    args = sanitizer.sanitize_args(
        {
            "command": "curl -H 'Authorization: Bearer abc123'",
            "api_key": "sk-live-secret",
            "nested": {"password": "1234", "token_value": "abcd"},
        }
    )

    assert args["api_key"] == "***REDACTED***"
    assert args["nested"]["password"] == "***REDACTED***"
    assert args["nested"]["token_value"] == "***REDACTED***"
    assert "Authorization=***REDACTED***" in args["command"]


def test_agent_event_output_sanitizer_truncates_text_arrays_and_json() -> None:
    sanitizer = AgentEventOutputSanitizer(
        AgentEventOutputPolicy(max_text_chars=20, max_json_chars=80, max_array_items=2)
    )

    output = sanitizer.sanitize_output(
        {
            "text": "abcdefghijklmnopqrstuvwxyz",
            "value": {
                "logs": ["line1", "line2", "line3"],
                "payload": {"k": "v" * 50},
            },
            "body_ref": None,
        }
    )

    assert output["text"].endswith("...")
    assert len(output["text"]) <= 23
    assert output["value"]["logs"] == ["line1", "line2"]
    assert output["value"]["payload"]["k"].endswith("...")


def test_agent_event_output_sanitizer_redacts_pii_in_text_and_value() -> None:
    sanitizer = AgentEventOutputSanitizer()

    output = sanitizer.sanitize_output(
        {
            "text": "email user@example.com phone +34 600 123 456",
            "value": {
                "message": "send to dev.team@example.org",
                "notes": ["call 555-123-4567"],
            },
            "body_ref": None,
        }
    )

    assert output["text"] == "email ***REDACTED_EMAIL*** phone ***REDACTED_PHONE***"
    assert output["value"]["message"] == "send to ***REDACTED_EMAIL***"
    assert output["value"]["notes"] == ["call ***REDACTED_PHONE***"]


def test_agent_event_output_sanitizer_respects_disable_flags() -> None:
    sanitizer = AgentEventOutputSanitizer(
        AgentEventOutputPolicy(
            truncate_enabled=False,
            pii_enabled=False,
            secrets_enabled=False,
            max_text_chars=10,
            max_json_chars=20,
            max_array_items=1,
        )
    )

    output = sanitizer.sanitize_output(
        {
            "text": "email user@example.com token: abc123",
            "value": {
                "api_key": "sk-live-secret",
                "logs": ["line1", "line2", "line3"],
                "payload": {"k": "v" * 100},
            },
            "body_ref": None,
        }
    )

    assert output["text"] == "email user@example.com token: abc123"
    assert output["value"]["api_key"] == "sk-live-secret"
    assert output["value"]["logs"] == ["line1", "line2", "line3"]
    assert output["value"]["payload"]["k"] == "v" * 100
