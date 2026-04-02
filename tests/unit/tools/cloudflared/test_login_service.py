from __future__ import annotations

import os
from pathlib import Path

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.tools.cloudflared.login_service import CloudflaredLoginService


def _settings() -> Settings:
    return Settings(
        db_path="/tmp/test.db",
        log_level="INFO",
        webhooks_host="127.0.0.1",
        webhooks_port=8001,
    )


@pytest.fixture(autouse=True)
def isolate_login_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        CloudflaredLoginService,
        "_home_dir",
        lambda self: tmp_path,
    )


def test_start_returns_authenticated_when_login_already_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredLoginService(_settings())
    monkeypatch.setattr(service, "_is_authenticated", lambda: True)

    result = service.start()

    assert result.authenticated is True
    assert result.started is False
    assert result.running is False
    assert result.pid is None


def test_start_returns_existing_managed_login_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredLoginService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_login_state(1234)

    monkeypatch.setattr(service, "_is_authenticated", lambda: False)
    monkeypatch.setattr(service, "_is_expected_login_process", lambda pid: pid == 1234)

    result = service.start()

    assert result.authenticated is False
    assert result.started is False
    assert result.running is True
    assert result.pid == 1234


def test_start_launches_login_and_records_state(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredLoginService(_settings())
    recorded: dict[str, object] = {}

    monkeypatch.setattr(service, "_is_authenticated", lambda: False)

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs

        class _FakeProcess:
            pid = 9876
            returncode = None

            def poll(self):
                return None

        return _FakeProcess()

    monkeypatch.setattr("skiller.tools.cloudflared.login_service.subprocess.Popen", fake_popen)

    result = service.start()

    assert result.authenticated is False
    assert result.started is True
    assert result.running is True
    assert result.pid == 9876
    assert recorded["cmd"] == ["cloudflared", "tunnel", "login"]
    assert service._read_login_pid() == 9876


def test_status_clears_stale_managed_login_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredLoginService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_login_state(1234)

    monkeypatch.setattr(service, "_is_authenticated", lambda: False)
    monkeypatch.setattr(service, "_is_expected_login_process", lambda pid: False)

    result = service.status()

    assert result.authenticated is False
    assert result.running is False
    assert result.pid is None
    assert service._read_login_pid() is None


def test_stop_terminates_managed_login_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredLoginService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_login_state(1234)
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(service, "_is_authenticated", lambda: False)
    monkeypatch.setattr(service, "_is_expected_login_process", lambda pid: True)
    monkeypatch.setattr(service, "_wait_until_stopped", lambda pid: None)
    monkeypatch.setattr(
        "skiller.tools.cloudflared.login_service.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )

    result = service.stop()

    assert result.stopped is True
    assert result.running is False
    assert result.pid == 1234
    assert killed == [(1234, os.sys.modules["signal"].SIGTERM)]
    assert service._read_login_pid() is None


def test_stop_without_managed_login_returns_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredLoginService(_settings())
    monkeypatch.setattr(service, "_is_authenticated", lambda: False)

    result = service.stop()

    assert result.stopped is False
    assert result.running is False
    assert result.pid is None
