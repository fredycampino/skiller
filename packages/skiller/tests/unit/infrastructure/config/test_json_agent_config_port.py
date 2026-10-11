import json
from pathlib import Path

import pytest

from skiller.application.tools.files.config import FilesToolRuntimeConfig
from skiller.application.tools.files.tool import FilesTool
from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.application.tools.shell.process_tool import ShellProcessTool
from skiller.domain.agent.config.agent_config_port import AgentConfigProviderSource
from skiller.domain.agent.config.model import AgentLLMSelection
from skiller.domain.agent.config.validation import AgentConfigValidationErrorCode
from skiller.infrastructure.config.agent_config_mapper import AgentConfigMapper
from skiller.infrastructure.config.json_agent_config_port import JsonAgentConfigPort

pytestmark = pytest.mark.unit


def test_json_agent_config_reads_strict_llm_selection(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    _write(config_path, _payload())

    config = _config_port(config_path).get_config(flow_dir=tmp_path)

    assert config.llm == AgentLLMSelection(provider="minimax", model="MiniMax-M3")
    assert config.context.window_width_tokens is None
    assert config.debug.log_streaming is False
    assert config.debug.log_request_file == "~/.skiller/logs/request/minimax/request.json"


def test_json_agent_config_enables_stream_logging_explicitly(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    _write(
        config_path,
        {
            "llm": {"provider": "codex", "model": "gpt-5.5"},
            "debug": {"log_streaming": True},
        },
    )

    config = _config_port(config_path).get_config(flow_dir=tmp_path)

    assert config.debug.log_streaming is True


def test_json_agent_config_ignores_legacy_default_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    payload = _payload()
    llm = payload["llm"]
    assert isinstance(llm, dict)
    llm["default_provider"] = "bedrock"
    _write(config_path, payload)

    config = _config_port(config_path).get_config(flow_dir=tmp_path)

    assert config.llm == AgentLLMSelection(provider="minimax", model="MiniMax-M3")


def test_json_agent_config_ignores_legacy_provider_contract(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    _write(
        config_path,
        {
            "llm": {
                "provider": "minimax",
                "model": "MiniMax-M3",
                "default_provider": "legacy-value",
            },
            "providers": {
                "minimax": {
                    "model": "MiniMax-M3",
                    "timeout_seconds": 30,
                }
            },
        },
    )

    config = _config_port(config_path).get_config(flow_dir=tmp_path)

    assert config.llm == AgentLLMSelection(provider="minimax", model="MiniMax-M3")


def test_json_agent_config_rejects_missing_model(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    _write(config_path, {"llm": {"provider": "minimax"}})

    validation = _config_port(config_path).validate_config(flow_dir=tmp_path)

    assert validation.ok is False
    assert validation.error == AgentConfigValidationErrorCode.INVALID_SCHEMA


def test_json_agent_config_uses_local_file_as_root_override(tmp_path: Path) -> None:
    global_path = tmp_path / "global" / "agent.json"
    local_path = tmp_path / "local" / "agent.json"
    _write(global_path, _payload())
    _write(local_path, {"llm": {"provider": "codex", "model": "gpt-5.5"}})

    config = _config_port(global_path).get_config(flow_dir=tmp_path, config_path=local_path)

    assert config.llm == AgentLLMSelection(provider="codex", model="gpt-5.5")


def test_json_agent_config_explicit_file_has_highest_priority(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    env_path = tmp_path / "env.json"
    _write(global_path, _payload())
    _write(env_path, {"llm": {"provider": "codex", "model": "gpt-5.4"}})

    config = _config_port(
        global_path,
        env={},
    ).get_config(flow_dir=tmp_path, config_path=env_path)

    assert config.llm == AgentLLMSelection(provider="codex", model="gpt-5.4")


def test_json_agent_config_lists_selection_source(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    _write(config_path, _payload())

    sources = _config_port(config_path).list_provider_sources()

    assert len(sources) == 1
    assert sources[0].provider == "minimax"
    assert sources[0].source == AgentConfigProviderSource.GLOBAL


def test_json_agent_config_sets_provider_and_model_together(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.json"
    _write(config_path, _payload())
    port = _config_port(config_path)

    port.set_model(provider="codex", model="gpt-5.5")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["llm"] == {"provider": "codex", "model": "gpt-5.5"}


def test_json_agent_config_updates_global_when_local_has_no_llm(tmp_path: Path) -> None:
    global_path = tmp_path / "global" / "agent.json"
    local_path = tmp_path / "local" / "agent.json"
    _write(global_path, _payload())
    _write(local_path, {"context": {"window_width_tokens": 100000}})
    port = _config_port(global_path)

    port.set_model(
        provider="codex",
        model="gpt-5.5",
        config_path=local_path,
    )

    global_payload = json.loads(global_path.read_text(encoding="utf-8"))
    local_payload = json.loads(local_path.read_text(encoding="utf-8"))
    assert global_payload["llm"] == {"provider": "codex", "model": "gpt-5.5"}
    assert "llm" not in local_payload


def test_json_agent_config_reports_missing_file(tmp_path: Path) -> None:
    validation = _config_port(tmp_path / "missing.json").validate_config(flow_dir=tmp_path)

    assert validation.ok is False
    assert validation.error == AgentConfigValidationErrorCode.CONFIG_NOT_FOUND


def _config_port(
    config_path: Path,
    *,
    env: dict[str, str] | None = None,
) -> JsonAgentConfigPort:
    resolved_env = env or {}
    return JsonAgentConfigPort(
        config_path_global=config_path,
        config_mapper=AgentConfigMapper(env=resolved_env),
        env=resolved_env,
    )


def _payload() -> dict[str, object]:
    return {
        "llm": {
            "provider": "minimax",
            "model": "MiniMax-M3",
        }
    }


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload)}\n", encoding="utf-8")


@pytest.mark.parametrize("source", ["global", "local", "explicit"])
def test_tools_paths_use_flow_directory_not_profile_directory(tmp_path, source) -> None:

    global_path = tmp_path / "settings" / "agent.json"
    profile = tmp_path / "profiles" / "agent.json"
    flow_dir = tmp_path / "flows"
    _write(global_path, _payload())
    tool_payload = {
        **_payload(),
        "tools": {
            "files": {"read": [".", "{{flow.dir}}", "data"]},
            "shell": {"allowed_paths": [".", "{{flow.dir}}", "data"]},
        },
    }
    _write(global_path if source == "global" else profile, tool_payload)
    env = {}
    port = JsonAgentConfigPort(
        config_path_global=global_path,
        config_mapper=AgentConfigMapper(env=env, tools=(FilesTool(), ShellProcessTool())),
        env=env,
    )
    selected = profile if source == "local" else None
    if source == "explicit":
        selected = port.resolve_config_path(flow_dir=flow_dir, file_reference=str(profile))
    config = port.get_config(flow_dir=flow_dir, config_path=selected)
    files = config.tools.get("files")
    shell = config.tools.get("shell")
    assert isinstance(files, FilesToolRuntimeConfig)
    assert isinstance(shell, ShellToolRuntimeConfig)
    assert files.read == (flow_dir, flow_dir, flow_dir / "data")
    assert flow_dir in shell.allowed_paths
    assert flow_dir / "data" in shell.allowed_paths
    assert profile.parent not in shell.allowed_paths
    assert global_path.parent not in shell.allowed_paths


def test_explicit_environment_profile_replaces_conventional_profile(tmp_path) -> None:
    global_path = tmp_path / "global.json"
    profile = tmp_path / "reviewer.json"
    _write(global_path, _payload())
    _write(tmp_path / "agent.json", {"llm": {"provider": "wrong", "model": "wrong"}})
    _write(profile, {"llm": {"provider": "codex", "model": "gpt-5.5"}})
    port = _config_port(global_path, env={"PROFILE_DIR": str(tmp_path)})
    selected = port.resolve_config_path(
        flow_dir=tmp_path, file_reference="${PROFILE_DIR}/reviewer.json"
    )
    config = port.get_config(flow_dir=tmp_path, config_path=selected)
    assert selected == profile
    assert config.llm.provider == "codex"
    port.set_model(provider="minimax", model="MiniMax-M3", config_path=selected)
    assert json.loads(profile.read_text())["llm"] == _payload()["llm"]
    assert json.loads((tmp_path / "agent.json").read_text())["llm"]["provider"] == "wrong"


def test_explicit_profile_without_llm_updates_global(tmp_path) -> None:
    global_path = tmp_path / "global.json"
    profile = tmp_path / "profile.json"
    _write(global_path, _payload())
    _write(profile, {"loop": {"max_turns": 4}})
    port = _config_port(global_path)
    selected = port.resolve_config_path(flow_dir=tmp_path, file_reference="./profile.json")
    port.set_model(provider="codex", model="gpt-5.5", config_path=selected)
    assert json.loads(global_path.read_text())["llm"]["provider"] == "codex"
    assert "llm" not in json.loads(profile.read_text())


@pytest.mark.parametrize("reference", ["$MISSING", "./missing.json"])
def test_explicit_invalid_selection_never_falls_back(tmp_path, reference) -> None:
    _write(tmp_path / "agent.json", _payload())
    port = _config_port(tmp_path / "agent.json")
    with pytest.raises((ValueError, FileNotFoundError)):
        port.resolve_config_path(flow_dir=tmp_path, file_reference=reference)


def test_missing_selected_file_after_resolution_does_not_fall_back(tmp_path) -> None:
    global_path = tmp_path / "global.json"
    profile = tmp_path / "profile.json"
    _write(global_path, _payload())
    _write(profile, _payload())
    port = _config_port(global_path)
    selected = port.resolve_config_path(flow_dir=tmp_path, file_reference="profile.json")
    profile.unlink()
    assert port.validate_config(flow_dir=tmp_path, config_path=selected).ok is False
    with pytest.raises(FileNotFoundError):
        port.set_model(provider="codex", model="gpt-5.5", config_path=selected)
