import pytest

from skiller.infrastructure.config.os_environment_secret_port import OsEnvironmentSecretPort

pytestmark = pytest.mark.unit


def test_os_environment_secret_port_reads_a_named_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBHOOK_SECRET", "secret-value")

    assert OsEnvironmentSecretPort().get_secret("WEBHOOK_SECRET") == "secret-value"


def test_os_environment_secret_port_returns_none_for_a_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_WEBHOOK_SECRET", raising=False)

    assert OsEnvironmentSecretPort().get_secret("MISSING_WEBHOOK_SECRET") is None
