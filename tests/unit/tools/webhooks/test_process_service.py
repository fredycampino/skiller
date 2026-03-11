from __future__ import annotations

import sys

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.tools.webhooks.process_service import WebhookProcessService


def _settings() -> Settings:
    return Settings(
        db_path="/tmp/test.db",
        log_level="INFO",
        webhooks_host="127.0.0.1",
        webhooks_port=8001,
    )


def test_start_returns_existing_endpoint_when_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WebhookProcessService(_settings())

    monkeypatch.setattr(service, "_is_endpoint_ready", lambda endpoint: True)

    result = service.start()

    assert result.endpoint == "http://127.0.0.1:8001/health"
    assert result.pid is None
    assert result.started is False


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

    monkeypatch.setattr("skiller.tools.webhooks.process_service.subprocess.Popen", fake_popen)
    monkeypatch.setattr(service, "_wait_until_ready", lambda endpoint, process: None)

    result = service.start()

    assert result.endpoint == "http://127.0.0.1:8001/health"
    assert result.pid == 1234
    assert result.started is True
    assert recorded["cmd"] == [sys.executable, "-m", "skiller.tools.webhooks"]


def test_wait_until_ready_raises_when_process_exits() -> None:
    service = WebhookProcessService(_settings())

    class _DeadProcess:
        returncode = 1

        def poll(self):
            return 1

    with pytest.raises(RuntimeError, match="exited with code 1"):
        service._wait_until_ready("http://127.0.0.1:8001/health", _DeadProcess())
