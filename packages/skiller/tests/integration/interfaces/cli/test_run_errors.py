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
    monkeypatch.setenv("AGENT_CONFIG_FILE", str(missing_config_path))

    exit_code = cli_main.main(["run", "any-flow"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "RUNTIME_INITIALIZATION_FAILED"
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
    monkeypatch.setenv("AGENT_DB_PATH", str(database_path))

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
    monkeypatch.setenv("AGENT_DB_PATH", str(database_path))

    exit_code = cli_main.main(["run", "--file", str(missing_flow_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["error"]["code"] == "FLOW_NOT_FOUND"
    assert str(missing_flow_path) in payload["error"]["message"]
    assert captured.err == ""
