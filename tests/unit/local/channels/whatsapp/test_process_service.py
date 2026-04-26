from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.local.channels.whatsapp.process_service import WhatsAppProcessService


def _settings() -> Settings:
    return Settings(
        db_path="/tmp/test.db",
        log_level="INFO",
        webhooks_host="127.0.0.1",
        webhooks_port=8001,
        whatsapp_bridge_host="127.0.0.1",
        whatsapp_bridge_port=8002,
    )


@pytest.fixture(autouse=True)
def isolate_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        WhatsAppProcessService,
        "_state_dir",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        WhatsAppProcessService,
        "_pid_file",
        lambda self: tmp_path / "managed-8002.json",
    )


def test_start_requires_paired_session(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppProcessService(_settings())
    monkeypatch.setattr(service, "_ensure_bridge_requirements", lambda: None)
    monkeypatch.setattr(service, "_is_paired", lambda: False)

    with pytest.raises(RuntimeError, match="WhatsApp session is not paired"):
        service.start()


def test_start_returns_existing_managed_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppProcessService(_settings())
    service._write_managed_state(1234)
    fake_webhooks = lambda settings: SimpleNamespace(  # noqa: E731
        start=lambda: None,
        status=lambda: SimpleNamespace(running=True),
    )

    monkeypatch.setattr(service, "_ensure_bridge_requirements", lambda: None)
    monkeypatch.setattr(service, "_is_paired", lambda: True)
    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.WebhookProcessService",
        fake_webhooks,
    )
    monkeypatch.setattr(service, "_write_channel_token", lambda: None)
    monkeypatch.setattr(service, "_is_expected_service_process", lambda pid: True)
    monkeypatch.setattr(
        service,
        "_read_health",
        lambda: {
            "status": "connected",
            "qrCount": 0,
            "queueLength": 2,
        },
    )

    result = service.start()

    assert result.pid == 1234
    assert result.started is False
    assert result.running is True
    assert result.managed is True
    assert result.state == "connected"
    assert result.queue_length == 2


def test_start_launches_service_for_existing_external_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppProcessService(_settings())
    recorded: dict[str, object] = {}
    fake_webhooks = lambda settings: SimpleNamespace(  # noqa: E731
        start=lambda: None,
        status=lambda: SimpleNamespace(running=True),
    )

    monkeypatch.setattr(service, "_ensure_bridge_requirements", lambda: None)
    monkeypatch.setattr(service, "_is_paired", lambda: True)
    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.WebhookProcessService",
        fake_webhooks,
    )
    monkeypatch.setattr(service, "_write_channel_token", lambda: None)
    monkeypatch.setattr(service, "_read_channel_token", lambda: "token-1")
    monkeypatch.setattr(
        service,
        "_read_health",
        lambda: {
            "status": "connected",
            "qrCount": 0,
            "queueLength": 1,
        },
    )

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs

        class _FakeProcess:
            pid = 9877
            returncode = None

            def poll(self):
                return None

        return _FakeProcess()

    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(service, "_wait_until_ready", lambda endpoint, process: None)

    result = service.start()

    assert result.started is True
    assert result.running is True
    assert result.managed is True
    assert result.pid == 9877
    assert result.queue_length == 1


def test_start_launches_bridge_and_records_managed_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppProcessService(_settings())
    recorded: dict[str, object] = {}
    fake_webhooks = lambda settings: SimpleNamespace(  # noqa: E731
        start=lambda: None,
        status=lambda: SimpleNamespace(running=True),
    )

    monkeypatch.setattr(service, "_ensure_bridge_requirements", lambda: None)
    monkeypatch.setattr(service, "_is_paired", lambda: True)
    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.WebhookProcessService",
        fake_webhooks,
    )
    monkeypatch.setattr(service, "_write_channel_token", lambda: None)
    monkeypatch.setattr(service, "_read_channel_token", lambda: "token-1")
    monkeypatch.setattr(service, "_read_health", lambda: None)

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs

        class _FakeProcess:
            pid = 9876
            returncode = None

            def poll(self):
                return None

        return _FakeProcess()

    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.subprocess.Popen",
        fake_popen,
    )
    monkeypatch.setattr(service, "_wait_until_ready", lambda endpoint, process: None)
    monkeypatch.setattr(
        service,
        "_read_health",
        lambda: {
            "status": "connected",
            "qrCount": 0,
            "queueLength": 0,
        },
    )

    result = service.start()

    assert result.pid == 9876
    assert result.started is True
    assert result.running is True
    assert result.managed is True
    assert recorded["cmd"] == [
        "node",
        str(service._bridge_script()),
        "--session",
        str(service._session_dir()),
        "--runtime-state-file",
        str(service._runtime_state_file()),
        "--port",
        "8002",
        "--channel-target-base",
        "http://127.0.0.1:8001/channels/whatsapp",
        "--channel-token",
        "token-1",
    ]
    assert service._read_managed_state() == {
        "pid": 9876,
        "endpoint": "http://127.0.0.1:8002/health",
        "session_path": str(service._session_dir()),
    }


def test_status_clears_stale_managed_pid_and_reports_external_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppProcessService(_settings())
    service._write_managed_state(1234)

    monkeypatch.setattr(service, "_is_expected_service_process", lambda pid: False)
    monkeypatch.setattr(service, "_is_paired", lambda: True)
    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.WebhookProcessService",
        lambda settings: SimpleNamespace(status=lambda: SimpleNamespace(running=True)),
    )
    monkeypatch.setattr(
        service,
        "_read_health",
        lambda: {
            "status": "connected",
            "qrCount": 0,
            "queueLength": 3,
        },
    )

    result = service.status()

    assert result.running is True
    assert result.managed is False
    assert result.pid is None
    assert result.queue_length == 3
    assert service._read_managed_state() is None


def test_stop_terminates_managed_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppProcessService(_settings())
    service._write_managed_state(1234)
    stopped: list[int] = []

    monkeypatch.setattr(service, "_is_expected_service_process", lambda pid: True)
    monkeypatch.setattr(service, "_is_paired", lambda: True)
    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.WebhookProcessService",
        lambda settings: SimpleNamespace(status=lambda: SimpleNamespace(running=False)),
    )
    monkeypatch.setattr(service, "_stop_process_group", lambda pid: stopped.append(pid))
    monkeypatch.setattr(service, "_wait_until_stopped", lambda endpoint, pid: None)

    result = service.stop()

    assert result.stopped is True
    assert result.running is False
    assert result.managed is True
    assert result.pid == 1234
    assert stopped == [1234]
    assert service._read_managed_state() is None


def test_stop_does_not_kill_external_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppProcessService(_settings())

    monkeypatch.setattr(service, "_is_paired", lambda: True)
    monkeypatch.setattr(
        "skiller.local.channels.whatsapp.process_service.WebhookProcessService",
        lambda settings: SimpleNamespace(status=lambda: SimpleNamespace(running=True)),
    )
    monkeypatch.setattr(
        service,
        "_read_health",
        lambda: {
            "status": "connected",
            "qrCount": 0,
            "queueLength": 4,
        },
    )

    result = service.stop()

    assert result.running is True
    assert result.stopped is False
    assert result.managed is False
    assert result.queue_length == 4
