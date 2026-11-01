import json
from pathlib import Path

import pytest

from skiller.interfaces.cli import main as cli_main


def test_run_missing_runtime_config_returns_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_config_path = tmp_path / "missing-config.json"
    monkeypatch.setenv("SKILLER_RUNTIME_CONFIG_FILE", str(missing_config_path))

    exit_code = cli_main.main(["run", "any-flow"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "RUNTIME_INITIALIZATION_FAILED"
    assert str(missing_config_path) in payload["error"]["message"]
    assert captured.err == ""


def test_config_missing_runtime_config_returns_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_config_path = tmp_path / "missing-config.json"
    monkeypatch.setenv("SKILLER_RUNTIME_CONFIG_FILE", str(missing_config_path))

    exit_code = cli_main.main(["config"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "RUNTIME_CONFIG_ERROR"
    assert str(missing_config_path) in payload["error"]["message"]
    assert captured.err == ""


def test_run_invalid_external_yaml_returns_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "runtime.db"
    flow_path = tmp_path / "invalid.yaml"
    flow_path.write_text("name: [invalid", encoding="utf-8")
    monkeypatch.setenv("SKILLER_DB_PATH", str(database_path))

    exit_code = cli_main.main(["run", "--file", str(flow_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "RUN_CREATE_FAILED"
    assert "Invalid flow YAML" in payload["error"]["message"]
    assert captured.err == ""


def test_run_missing_external_flow_returns_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "runtime.db"
    missing_flow_path = tmp_path / "missing.yaml"
    monkeypatch.setenv("SKILLER_DB_PATH", str(database_path))

    exit_code = cli_main.main(["run", "--file", str(missing_flow_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "FLOW_NOT_FOUND"
    assert str(missing_flow_path) in payload["error"]["message"]
    assert captured.err == ""


@pytest.mark.parametrize("source", ["default", "json", "environment", "development"])
def test_config_reports_database_without_initializing_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: str,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SKILLER_DB_PATH", raising=False)
    monkeypatch.delenv("SKILLER_RUNTIME_CONFIG_FILE", raising=False)
    database = home / ".skiller/runtime/global.db"
    if source != "default":
        config_path = tmp_path / "custom.json"
        config_path.write_text(json.dumps({"runtime": {"db_path": "./json.db"}}))
        monkeypatch.setenv("SKILLER_RUNTIME_CONFIG_FILE", str(config_path))
        database = tmp_path / "json.db"
    if source == "environment":
        monkeypatch.setenv("SKILLER_DB_PATH", "./environment.db")
        database = tmp_path / "environment.db"
    if source == "development":
        (tmp_path / ".env.development").write_text("SKILLER_DB_PATH=./development.db\n")
        database = tmp_path / "development.db"
    before = set(tmp_path.rglob("*"))

    assert cli_main.main(["config"]) == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["runtime"]["db_path"] == str(database)
    assert captured.err == ""
    assert set(tmp_path.rglob("*")) == before
    assert not database.exists()
