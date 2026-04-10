from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.tools.whatsapp.pair_service import WhatsAppPairService


def _settings() -> Settings:
    return Settings(
        db_path="/tmp/test.db",
        log_level="INFO",
        webhooks_host="127.0.0.1",
        webhooks_port=8001,
    )


@pytest.fixture(autouse=True)
def isolate_pair_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        WhatsAppPairService,
        "_home_dir",
        lambda self: tmp_path,
    )


def test_start_returns_paired_when_session_already_exists() -> None:
    service = WhatsAppPairService(_settings())
    service._session_dir().mkdir(parents=True, exist_ok=True)
    (service._session_dir() / "creds.json").write_text("{}", encoding="utf-8")

    result = service.start()

    assert result.paired is True
    assert result.started is False
    assert result.running is False
    assert result.pid is None
    assert result.state == "paired"
    assert result.qr_count == 0


def test_start_returns_existing_managed_pair_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppPairService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_pair_state(1234)

    monkeypatch.setattr(service, "_is_paired", lambda: False)
    monkeypatch.setattr(service, "_is_expected_pair_process", lambda pid: pid == 1234)

    result = service.start()

    assert result.paired is False
    assert result.started is False
    assert result.running is True
    assert result.pid == 1234
    assert result.state == "waiting_for_scan"


def test_start_runs_pair_foreground_and_returns_paired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppPairService(_settings())

    monkeypatch.setattr(service, "_is_paired", lambda: False)
    monkeypatch.setattr(service, "_ensure_bridge_requirements", lambda: None)
    monkeypatch.setattr(
        service,
        "_runtime_qr_count",
        lambda: 2,
    )
    monkeypatch.setattr(
        service,
        "_run_pair_process_foreground",
        lambda *, timeout_seconds: (9876, True),
    )

    result = service.start()

    assert result.paired is True
    assert result.started is True
    assert result.running is False
    assert result.pid == 9876
    assert result.state == "paired"
    assert result.qr_count == 2


def test_start_cancels_pair_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppPairService(_settings())
    stopped: list[int] = []

    monkeypatch.setattr(service, "_is_paired", lambda: False)
    monkeypatch.setattr(service, "_ensure_bridge_requirements", lambda: None)
    monkeypatch.setattr(
        "skiller.tools.whatsapp.pair_service.subprocess.Popen",
        lambda *args, **kwargs: type(
            "_FakeProcess",
            (),
            {
                "pid": 4321,
                "returncode": None,
                "stdout": object(),
            },
        )(),
    )
    monkeypatch.setattr(
        service,
        "_stream_process_output",
        lambda **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(service, "_stop_process_group", lambda pid: stopped.append(pid))

    with pytest.raises(RuntimeError, match="WhatsApp pairing cancelled by user"):
        service.start()

    assert stopped == [4321]
    assert service._read_pair_pid() is None


def test_status_clears_stale_managed_pair_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = WhatsAppPairService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_pair_state(1234)

    monkeypatch.setattr(service, "_is_paired", lambda: False)
    monkeypatch.setattr(service, "_is_expected_pair_process", lambda pid: False)

    result = service.status()

    assert result.paired is False
    assert result.running is False
    assert result.pid is None
    assert result.state == "stopped"
    assert service._read_pair_pid() is None


def test_status_reports_runtime_state_for_active_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppPairService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_pair_state(1234)
    service._runtime_state_file().write_text(
        json.dumps(
            {
                "state": "waiting_for_scan",
                "qr_count": 3,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "_is_paired", lambda: False)
    monkeypatch.setattr(service, "_is_expected_pair_process", lambda pid: True)

    result = service.status()

    assert result.state == "waiting_for_scan"
    assert result.qr_count == 3


def test_stop_terminates_managed_pair_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppPairService(_settings())
    service._state_dir().mkdir(parents=True, exist_ok=True)
    service._write_pair_state(1234)
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(service, "_is_paired", lambda: False)
    monkeypatch.setattr(service, "_is_expected_pair_process", lambda pid: True)
    monkeypatch.setattr(
        service,
        "_stop_process_group",
        lambda pid: killed.append((pid, os.sys.modules["signal"].SIGTERM)),
    )

    result = service.stop()

    assert result.stopped is True
    assert result.running is False
    assert result.pid == 1234
    assert result.state == "stopped"
    assert killed == [(1234, os.sys.modules["signal"].SIGTERM)]
    assert service._read_pair_pid() is None


def test_stop_process_group_falls_back_to_sigkill(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppPairService(_settings())
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        service,
        "_terminate_process_group",
        lambda pid: calls.append(("term", pid)),
    )
    monkeypatch.setattr(
        service,
        "_kill_process_group",
        lambda pid: calls.append(("kill", pid)),
    )

    state = {"count": 0}

    def fake_wait(pid: int) -> None:
        state["count"] += 1
        if state["count"] == 1:
            raise RuntimeError(f"whatsapp pair process did not stop cleanly: pid={pid}")

    monkeypatch.setattr(service, "_wait_until_stopped", fake_wait)

    service._stop_process_group(9999)

    assert calls == [("term", 9999), ("kill", 9999)]


def test_stop_without_managed_pair_returns_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    service = WhatsAppPairService(_settings())
    monkeypatch.setattr(service, "_is_paired", lambda: False)

    result = service.stop()

    assert result.stopped is False
    assert result.running is False
    assert result.pid is None
    assert result.state == "stopped"
