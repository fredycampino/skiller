from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.local.server.process_service import WebhookProcessService


def _settings() -> Settings:
    return Settings(
        db_path="/tmp/test.db",
        log_level="INFO",
        webhooks_host="127.0.0.1",
        webhooks_port=8001,
    )


@pytest.fixture(autouse=True)
def isolate_pid_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        WebhookProcessService,
        "_pid_file",
        lambda self: tmp_path / "skiller-webhooks.pid",
    )


def test_start_returns_existing_endpoint_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WebhookProcessService(_settings())

    monkeypatch.setattr(service, "_is_endpoint_ready", lambda endpoint: True)

    result = service.start()

    assert result.endpoint == "http://127.0.0.1:8001/health"
    assert result.pid is None
    assert result.started is False
    assert result.running is True
    assert result.managed is False


def test_start_clears_stale_managed_pid_when_endpoint_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WebhookProcessService(_settings())
    service._write_managed_pid(1234)

    monkeypatch.setattr(service, "_is_expected_server_process", lambda pid: False)
    monkeypatch.setattr(service, "_is_endpoint_ready", lambda endpoint: True)

    result = service.start()

    assert result.started is False
    assert result.running is True
    assert result.managed is False
    assert result.pid is None
    assert service._read_managed_pid() is None


def test_start_launches_process_and_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WebhookProcessService(_settings())
    recorded: dict[str, object] = {}

    monkeypatch.setattr(service, "_is_endpoint_ready", lambda endpoint: False)

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs

        class _FakeProcess:
            pid = 1234
            returncode = None

            def poll(self):
                return None

        return _FakeProcess()

    monkeypatch.setattr("skiller.local.server.process_service.subprocess.Popen", fake_popen)
    monkeypatch.setattr(service, "_wait_until_ready", lambda endpoint, process: None)

    result = service.start()

    assert result.endpoint == "http://127.0.0.1:8001/health"
    assert result.pid == 1234
    assert result.started is True
    assert result.running is True
    assert result.managed is True
    assert recorded["cmd"] == [sys.executable, "-m", "skiller.local.server"]
    assert service._read_managed_pid() == 1234


def test_wait_until_ready_raises_when_process_exits() -> None:
    service = WebhookProcessService(_settings())

    class _DeadProcess:
        returncode = 1

        def poll(self):
            return 1

    with pytest.raises(RuntimeError, match="exited with code 1"):
        service._wait_until_ready("http://127.0.0.1:8001/health", _DeadProcess())


def test_status_returns_running_and_managed_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WebhookProcessService(_settings())
    service._write_managed_pid(1234)

    monkeypatch.setattr(service, "_is_endpoint_ready", lambda endpoint: True)
    monkeypatch.setattr(service, "_is_expected_server_process", lambda pid: True)

    result = service.status()

    assert result.running is True
    assert result.managed is True
    assert result.pid == 1234


def test_stop_terminates_managed_process(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WebhookProcessService(_settings())
    service._write_managed_pid(1234)
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(service, "_is_expected_server_process", lambda pid: True)
    monkeypatch.setattr(service, "_wait_until_stopped", lambda endpoint, pid: None)
    monkeypatch.setattr(
        "skiller.local.server.process_service.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )

    result = service.stop()

    assert result.stopped is True
    assert result.running is False
    assert result.managed is True
    assert result.pid == 1234
    assert killed == [(1234, os.sys.modules["signal"].SIGTERM)]
    assert service._read_managed_pid() is None


def test_stop_clears_stale_or_reused_pid_without_killing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WebhookProcessService(_settings())
    service._write_managed_pid(1234)
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(service, "_is_expected_server_process", lambda pid: False)
    monkeypatch.setattr(service, "_is_endpoint_ready", lambda endpoint: True)
    monkeypatch.setattr(
        "skiller.local.server.process_service.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )

    result = service.stop()

    assert result.stopped is False
    assert result.running is True
    assert result.managed is False
    assert result.pid is None
    assert killed == []
    assert service._read_managed_pid() is None
