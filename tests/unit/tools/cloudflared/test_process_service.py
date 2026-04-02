from __future__ import annotations

import os
from pathlib import Path

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.tools.cloudflared.process_service import CloudflaredProcessService


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
        CloudflaredProcessService,
        "_state_dir",
        lambda self: tmp_path,
    )
    monkeypatch.setattr(
        CloudflaredProcessService,
        "_pid_file",
        lambda self: tmp_path / "skiller-cloudflared.json",
    )
    monkeypatch.setattr(
        CloudflaredProcessService,
        "_config_path",
        lambda self: tmp_path / "skillerwh-config.yml",
    )


def test_start_returns_existing_managed_process(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredProcessService(_settings())
    service._write_managed_pid(1234)

    monkeypatch.setattr(service, "_is_managed_process", lambda **kwargs: True)

    result = service.start()

    assert result.origin_url == "http://127.0.0.1:8001"
    assert result.pid == 1234
    assert result.started is False
    assert result.running is True
    assert result.managed is True


def test_start_returns_existing_external_process_without_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredProcessService(_settings())

    monkeypatch.setattr(service, "_find_matching_pid", lambda **kwargs: 4321)

    def fail_popen(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("subprocess.Popen should not be called")

    monkeypatch.setattr("skiller.tools.cloudflared.process_service.subprocess.Popen", fail_popen)

    result = service.start()

    assert result.pid == 4321
    assert result.started is False
    assert result.running is True
    assert result.managed is False


def test_start_launches_process_and_records_managed_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredProcessService(_settings())
    recorded: dict[str, object] = {}

    monkeypatch.setattr(service, "_find_matching_pid", lambda **kwargs: None)
    monkeypatch.setattr(service, "_find_tunnel_id", lambda: "uuid-1")
    monkeypatch.setattr(
        service,
        "_credentials_path_for",
        lambda tunnel_ref: Path("/tmp") / f"{tunnel_ref}.json",
    )
    monkeypatch.setattr(service, "_fetch_tunnel_token", lambda tunnel_ref: "token-123")

    def fake_popen(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs

        class _FakeProcess:
            pid = 9876
            returncode = None

            def poll(self):
                return None

        return _FakeProcess()

    monkeypatch.setattr("skiller.tools.cloudflared.process_service.subprocess.Popen", fake_popen)
    monkeypatch.setattr(service, "_wait_until_started", lambda pid, process, **kwargs: None)

    result = service.start()

    assert result.pid == 9876
    assert result.started is True
    assert result.running is True
    assert result.managed is True
    assert recorded["cmd"] == [
        "cloudflared",
        "tunnel",
        "--url",
        "http://127.0.0.1:8001",
        "run",
        "--token",
        "token-123",
    ]
    assert service._read_managed_pid() == 9876


def test_build_run_command_prefers_config_with_local_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = CloudflaredProcessService(_settings())
    config_path = tmp_path / "skillerwh-config.yml"
    config_path.write_text("tunnel: uuid-1\n", encoding="utf-8")
    credentials_path = tmp_path / "uuid-1.json"
    credentials_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(service, "_find_tunnel_id", lambda: "uuid-1")
    monkeypatch.setattr(service, "_config_path", lambda: config_path)
    monkeypatch.setattr(service, "_credentials_path_for", lambda tunnel_ref: credentials_path)

    command = service._build_run_command(origin_url="http://127.0.0.1:8001")

    assert command == [
        "cloudflared",
        "tunnel",
        "--config",
        str(config_path),
        "run",
    ]


def test_build_run_command_uses_config_with_token_when_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = CloudflaredProcessService(_settings())
    config_path = tmp_path / "skillerwh-config.yml"
    config_path.write_text("tunnel: uuid-1\n", encoding="utf-8")

    monkeypatch.setattr(service, "_find_tunnel_id", lambda: "uuid-1")
    monkeypatch.setattr(service, "_config_path", lambda: config_path)
    monkeypatch.setattr(
        service,
        "_credentials_path_for",
        lambda tunnel_ref: Path("/tmp/does-not-exist.json"),
    )
    monkeypatch.setattr(service, "_fetch_tunnel_token", lambda tunnel_ref: "token-123")

    command = service._build_run_command(origin_url="http://127.0.0.1:8001")

    assert command == [
        "cloudflared",
        "tunnel",
        "--config",
        str(config_path),
        "run",
        "--token",
        "token-123",
    ]


def test_build_run_command_falls_back_to_url_mode_without_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredProcessService(_settings())

    monkeypatch.setattr(service, "_find_tunnel_id", lambda: "uuid-1")
    monkeypatch.setattr(
        service,
        "_config_path",
        lambda: Path("/tmp/missing-skillerwh-config.yml"),
    )
    monkeypatch.setattr(
        service,
        "_credentials_path_for",
        lambda tunnel_ref: Path("/tmp/does-not-exist.json"),
    )
    monkeypatch.setattr(service, "_fetch_tunnel_token", lambda tunnel_ref: "token-123")

    command = service._build_run_command(origin_url="http://127.0.0.1:8001")

    assert command == [
        "cloudflared",
        "tunnel",
        "--url",
        "http://127.0.0.1:8001",
        "run",
        "--token",
        "token-123",
    ]


def test_status_clears_stale_managed_pid_and_reports_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredProcessService(_settings())
    service._write_managed_pid(1234)

    monkeypatch.setattr(service, "_is_managed_process", lambda **kwargs: False)
    monkeypatch.setattr(service, "_find_matching_pid", lambda **kwargs: None)

    result = service.status()

    assert result.running is False
    assert result.managed is False
    assert result.pid is None
    assert service._read_managed_pid() is None


def test_stop_terminates_managed_process(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredProcessService(_settings())
    service._write_managed_pid(1234)
    killed: list[tuple[int, int]] = []

    monkeypatch.setattr(service, "_is_managed_process", lambda **kwargs: True)
    monkeypatch.setattr(service, "_wait_until_stopped", lambda pid, **kwargs: None)
    monkeypatch.setattr(
        "skiller.tools.cloudflared.process_service.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )

    result = service.stop()

    assert result.stopped is True
    assert result.running is False
    assert result.managed is True
    assert result.pid == 1234
    assert killed == [(1234, os.sys.modules["signal"].SIGTERM)]
    assert service._read_managed_pid() is None


def test_stop_does_not_kill_external_process(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredProcessService(_settings())

    monkeypatch.setattr(service, "_find_matching_pid", lambda **kwargs: 2222)

    result = service.stop()

    assert result.pid == 2222
    assert result.running is True
    assert result.stopped is False
    assert result.managed is False


def test_matches_managed_command_accepts_token_mode() -> None:
    service = CloudflaredProcessService(_settings())

    assert service._matches_managed_command(
        args="cloudflared tunnel --url http://127.0.0.1:8001 run --token secret-token",
        origin_url="http://127.0.0.1:8001",
    )


def test_matches_managed_command_accepts_config_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredProcessService(_settings())
    config_path = tmp_path / "skillerwh-config.yml"
    monkeypatch.setattr(service, "_config_path", lambda: config_path)

    assert service._matches_managed_command(
        args=f"cloudflared tunnel --config {config_path} run --token secret-token",
        origin_url="http://127.0.0.1:8001",
    )


def test_matches_external_command_requires_tunnel_name() -> None:
    service = CloudflaredProcessService(_settings())

    assert not service._matches_external_command(
        args="cloudflared tunnel --url http://127.0.0.1:8001 run --token secret-token",
        origin_url="http://127.0.0.1:8001",
    )
