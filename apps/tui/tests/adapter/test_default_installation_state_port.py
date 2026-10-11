from __future__ import annotations

import json
from pathlib import Path

import pytest

from stui.adapter.default_installation_state_port import DefaultInstallationStatePort

pytestmark = pytest.mark.unit


def test_default_installation_state_port_reads_missing_default_paths(
    tmp_path: Path,
) -> None:
    port = DefaultInstallationStatePort(
        home=tmp_path / "home",
        cwd=tmp_path / "workspace",
        environment={},
    )

    state = port.read()

    assert state.runtime_db_exists is False


def test_default_installation_state_port_detects_default_runtime_db(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "runtime.db").write_text("", encoding="utf-8")
    port = DefaultInstallationStatePort(
        home=tmp_path / "home",
        cwd=workspace,
        environment={},
    )

    state = port.read()

    assert state.runtime_db_exists is True


@pytest.mark.parametrize("runtime_db_exists", [False, True])
def test_default_installation_state_port_ignores_agent_profiles(
    tmp_path: Path,
    runtime_db_exists: bool,
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    settings_dir = home / ".skiller" / "settings"
    settings_dir.mkdir(parents=True)
    workspace.mkdir()
    (settings_dir / "agent.json").write_text("{}", encoding="utf-8")
    (workspace / "agent.json").write_text("{}", encoding="utf-8")
    external_profile = tmp_path / "profile.json"
    external_profile.write_text("{}", encoding="utf-8")
    (workspace / ".env.development").write_text(
        f"AGENT_AGENT_CONFIG_FILE={external_profile}\n", encoding="utf-8"
    )
    if runtime_db_exists:
        (workspace / "runtime.db").write_text("", encoding="utf-8")
    port = DefaultInstallationStatePort(
        home=home,
        cwd=workspace,
        environment={"AGENT_AGENT_CONFIG_FILE": str(external_profile)},
    )

    state = port.read()

    assert state.runtime_db_exists is runtime_db_exists


def test_default_installation_state_port_reads_configured_db_path(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    settings_dir = home / ".skiller" / "settings"
    configured_db = workspace / "state" / "runtime.db"
    settings_dir.mkdir(parents=True)
    configured_db.parent.mkdir(parents=True)
    configured_db.write_text("", encoding="utf-8")
    (settings_dir / "config.json").write_text(
        json.dumps({"runtime": {"db_path": "state/runtime.db"}}),
        encoding="utf-8",
    )
    port = DefaultInstallationStatePort(
        home=home,
        cwd=workspace,
        environment={},
    )

    state = port.read()

    assert state.runtime_db_exists is True


def test_default_installation_state_port_reads_runtime_config_from_environment(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    configured_db = workspace / "state" / "runtime.db"
    config_path = tmp_path / "runtime-config.json"
    workspace.mkdir()
    configured_db.parent.mkdir()
    configured_db.write_text("", encoding="utf-8")
    config_path.write_text(
        json.dumps({"runtime": {"db_path": "state/runtime.db"}}),
        encoding="utf-8",
    )
    port = DefaultInstallationStatePort(
        home=tmp_path / "home",
        cwd=workspace,
        environment={"AGENT_RUNTIME_CONFIG_FILE": str(config_path)},
    )

    state = port.read()

    assert state.runtime_db_exists is True
    assert port._runtime_db_path() == configured_db


def test_default_installation_state_port_reads_development_env_db_path(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    configured_db = workspace / "dev-runtime.db"
    workspace.mkdir()
    configured_db.write_text("", encoding="utf-8")
    (workspace / "runtime.db").write_text("", encoding="utf-8")
    (workspace / ".env.development").write_text(
        "AGENT_DB_PATH=dev-runtime.db\n",
        encoding="utf-8",
    )
    port = DefaultInstallationStatePort(
        home=home,
        cwd=workspace,
        environment={},
    )

    state = port.read()

    assert state.runtime_db_exists is True
    assert port._runtime_db_path() == configured_db


def test_default_installation_state_port_real_env_overrides_development_env_db_path(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    real_env_db = workspace / "real-env.db"
    workspace.mkdir()
    real_env_db.write_text("", encoding="utf-8")
    (workspace / ".env.development").write_text(
        "AGENT_DB_PATH=dev-runtime.db\n",
        encoding="utf-8",
    )
    port = DefaultInstallationStatePort(
        home=home,
        cwd=workspace,
        environment={"AGENT_DB_PATH": "real-env.db"},
    )

    state = port.read()

    assert state.runtime_db_exists is True
    assert port._runtime_db_path() == real_env_db
