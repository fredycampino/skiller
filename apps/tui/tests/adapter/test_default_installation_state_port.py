from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from stui.adapter.cli_invoker import CliInvoker
from stui.adapter.default_installation_state_port import DefaultInstallationStatePort
from stui.port.installation_state_port import InstallationErrorKind

pytestmark = pytest.mark.unit


class FakeInvoker:
    def __init__(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> None:
        self.result = subprocess.CompletedProcess(["config"], returncode, stdout, stderr)
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        return self.result


@pytest.mark.parametrize("exists", [False, True])
def test_detects_database_reported_by_runtime(tmp_path: Path, exists: bool) -> None:
    database = tmp_path / "global.db"
    if exists:
        database.touch()
    invoker = FakeInvoker(json.dumps({"runtime": {"db_path": str(database)}}))
    port = DefaultInstallationStatePort(invoker=invoker)

    result = port.read()

    assert result.runtime_db_exists is exists
    assert result.error is None
    assert invoker.calls == [("config",)]


@pytest.mark.parametrize(
    "stdout",
    [
        "not json",
        "[]",
        "{}",
        '{"runtime": null}',
        '{"runtime": {"db_path": null}}',
        '{"runtime": {"db_path": ""}}',
        '{"runtime": {"db_path": "relative.db"}}',
    ],
)
def test_rejects_invalid_response(stdout: str) -> None:
    result = DefaultInstallationStatePort(invoker=FakeInvoker(stdout)).read()

    assert result.error is not None
    assert result.error.kind == InstallationErrorKind.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("stdout", "stderr", "message"),
    [
        ('{"error": {"message": "Invalid configuration"}}', "", "Invalid configuration"),
        ("", "process failed", "process failed"),
        ("", "", "Runtime config command failed"),
    ],
)
def test_reports_command_failure(stdout: str, stderr: str, message: str) -> None:
    invoker = FakeInvoker(stdout, returncode=1, stderr=stderr)

    result = DefaultInstallationStatePort(invoker=invoker).read()

    assert result.error is not None
    assert result.error.kind == InstallationErrorKind.COMMAND_FAILED
    assert result.error.message == message


def test_reports_process_launch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(self: CliInvoker, *args: str) -> subprocess.CompletedProcess[str]:
        raise OSError("Cannot launch runtime")

    monkeypatch.setattr(CliInvoker, "run", fail)

    result = DefaultInstallationStatePort(invoker=CliInvoker()).read()

    assert result.error is not None
    assert result.error.kind == InstallationErrorKind.COMMAND_FAILED
    assert result.error.message == "Cannot launch runtime"


@pytest.mark.integration
@pytest.mark.parametrize("exists", [False, True])
def test_real_cli_uses_global_database_from_two_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exists: bool,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("SKILLER_DB_PATH", raising=False)
    monkeypatch.delenv("SKILLER_RUNTIME_CONFIG_FILE", raising=False)
    database = home / ".skiller/runtime/global.db"
    if exists:
        database.parent.mkdir(parents=True)
        database.touch()
    workspaces = [tmp_path / "first", tmp_path / "second"]
    for workspace in workspaces:
        workspace.mkdir()
    before = set(tmp_path.rglob("*"))

    for workspace in workspaces:
        monkeypatch.chdir(workspace)
        result = DefaultInstallationStatePort(invoker=CliInvoker()).read()
        assert result.error is None
        assert result.runtime_db_exists is exists

    assert set(tmp_path.rglob("*")) == before
