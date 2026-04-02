from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from skiller.infrastructure.config.settings import Settings
from skiller.tools.cloudflared.ensure_service import CloudflaredEnsureService


def _settings() -> Settings:
    return Settings(
        db_path="/tmp/test.db",
        log_level="INFO",
        webhooks_host="127.0.0.1",
        webhooks_port=8001,
    )


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        CloudflaredEnsureService,
        "_home_dir",
        lambda self: tmp_path,
    )


def test_ensure_requires_domain() -> None:
    service = CloudflaredEnsureService(_settings())

    with pytest.raises(ValueError, match="domain is required"):
        service.ensure(domain=" ")


def test_ensure_requires_authenticated_login(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredEnsureService(_settings())

    class _FakeLoginService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def status(self):
            return type("Status", (), {"authenticated": False})()

    monkeypatch.setattr(
        "skiller.tools.cloudflared.ensure_service.CloudflaredLoginService",
        _FakeLoginService,
    )

    with pytest.raises(RuntimeError, match="login is required"):
        service.ensure(domain="campino.me")


def test_ensure_returns_existing_tunnel_with_existing_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredEnsureService(_settings())

    class _FakeLoginService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def status(self):
            return type("Status", (), {"authenticated": True})()

    monkeypatch.setattr(
        "skiller.tools.cloudflared.ensure_service.CloudflaredLoginService",
        _FakeLoginService,
    )
    monkeypatch.setattr(
        service,
        "_list_tunnels",
        lambda: [{"id": "uuid-1", "name": "skillerwh"}],
    )
    monkeypatch.setattr(
        service,
        "_ensure_dns_route",
        lambda **kwargs: "already_exists",
    )
    monkeypatch.setattr(
        service,
        "_write_tunnel_config",
        lambda **kwargs: service._config_path(),
    )

    result = service.ensure(domain="campino.me")

    assert result.authenticated is True
    assert result.tunnel_name == "skillerwh"
    assert result.tunnel_id == "uuid-1"
    assert result.hostname == "skillerwh.campino.me"
    assert result.created is False
    assert result.dns_status == "already_exists"
    assert result.config_path.endswith(".cloudflared/skillerwh-config.yml")


def test_ensure_creates_missing_tunnel(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredEnsureService(_settings())

    class _FakeLoginService:
        def __init__(self, settings) -> None:  # noqa: ANN001
            self.settings = settings

        def status(self):
            return type("Status", (), {"authenticated": True})()

    monkeypatch.setattr(
        "skiller.tools.cloudflared.ensure_service.CloudflaredLoginService",
        _FakeLoginService,
    )
    monkeypatch.setattr(service, "_find_tunnel", lambda: None)
    monkeypatch.setattr(
        service,
        "_create_tunnel",
        lambda: {"id": "uuid-2", "name": "skillerwh"},
    )
    monkeypatch.setattr(service, "_ensure_dns_route", lambda **kwargs: "created")
    monkeypatch.setattr(
        service,
        "_write_tunnel_config",
        lambda **kwargs: service._config_path(),
    )

    result = service.ensure(domain="campino.me")

    assert result.created is True
    assert result.tunnel_id == "uuid-2"
    assert result.dns_status == "created"
    assert result.config_path.endswith(".cloudflared/skillerwh-config.yml")


def test_write_tunnel_config_includes_credentials_when_present(tmp_path: Path) -> None:
    service = CloudflaredEnsureService(_settings())

    credentials_path = tmp_path / ".cloudflared" / "uuid-1.json"
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    credentials_path.write_text("{}", encoding="utf-8")

    config_path = service._write_tunnel_config(
        tunnel_id="uuid-1",
        hostname="skillerwh.campino.me",
    )

    raw = config_path.read_text(encoding="utf-8")
    assert "tunnel: uuid-1" in raw
    assert f"credentials-file: {credentials_path}" in raw
    assert "hostname: skillerwh.campino.me" in raw
    assert "service: http://127.0.0.1:8001" in raw


def test_write_tunnel_config_omits_credentials_when_missing() -> None:
    service = CloudflaredEnsureService(_settings())

    config_path = service._write_tunnel_config(
        tunnel_id="uuid-1",
        hostname="skillerwh.campino.me",
    )

    raw = config_path.read_text(encoding="utf-8")
    assert "tunnel: uuid-1" in raw
    assert "credentials-file:" not in raw
    assert "hostname: skillerwh.campino.me" in raw


def test_create_tunnel_falls_back_to_uuid_in_output(monkeypatch: pytest.MonkeyPatch) -> None:
    service = CloudflaredEnsureService(_settings())

    monkeypatch.setattr(service, "_find_tunnel", lambda: None)

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        _ = kwargs
        assert cmd == ["cloudflared", "tunnel", "create", "skillerwh"]
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Created tunnel skillerwh with id 11111111-1111-1111-1111-111111111111",
            stderr="",
        )

    monkeypatch.setattr("skiller.tools.cloudflared.ensure_service.subprocess.run", fake_run)

    result = service._create_tunnel()

    assert result == {"id": "11111111-1111-1111-1111-111111111111", "name": "skillerwh"}


def test_ensure_dns_route_treats_already_exists_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredEnsureService(_settings())
    monkeypatch.setattr(
        service,
        "_validate_existing_dns_route",
        lambda **kwargs: "already_exists",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        _ = kwargs
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout="",
            stderr="Record already exists",
        )

    monkeypatch.setattr("skiller.tools.cloudflared.ensure_service.subprocess.run", fake_run)

    result = service._ensure_dns_route(
        tunnel_id="uuid-1",
        hostname="skillerwh.campino.me",
    )

    assert result == "already_exists"


def test_ensure_dns_route_returns_unvalidated_when_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredEnsureService(_settings())
    monkeypatch.setattr(
        service,
        "_validate_existing_dns_route",
        lambda **kwargs: "already_exists_unvalidated",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        _ = kwargs
        return subprocess.CompletedProcess(
            cmd,
            1,
            stdout="",
            stderr="Record already exists",
        )

    monkeypatch.setattr("skiller.tools.cloudflared.ensure_service.subprocess.run", fake_run)

    result = service._ensure_dns_route(
        tunnel_id="uuid-1",
        hostname="skillerwh.campino.me",
    )

    assert result == "already_exists_unvalidated"


def test_validate_existing_dns_route_rejects_wrong_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredEnsureService(_settings())
    monkeypatch.setattr(
        service,
        "_lookup_cname_targets",
        lambda hostname: ["other-tunnel.cfargotunnel.com."],
    )

    with pytest.raises(RuntimeError, match="points to other-tunnel.cfargotunnel.com."):
        service._validate_existing_dns_route(
            tunnel_id="uuid-1",
            hostname="skillerwh.campino.me",
        )


def test_validate_existing_dns_route_accepts_expected_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = CloudflaredEnsureService(_settings())
    monkeypatch.setattr(
        service,
        "_lookup_cname_targets",
        lambda hostname: ["uuid-1.cfargotunnel.com."],
    )

    result = service._validate_existing_dns_route(
        tunnel_id="uuid-1",
        hostname="skillerwh.campino.me",
    )

    assert result == "already_exists"
