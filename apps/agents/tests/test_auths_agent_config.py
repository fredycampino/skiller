import importlib.util
import json
from pathlib import Path
from types import ModuleType

import yaml


def test_codex_auth_writes_config_only_after_credentials_validate() -> None:
    agent_path = Path("apps/agents/auths/codex/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    steps = _steps_by_name(agent)

    assert steps["route_codex_credentials"]["cases"]["ready"] == "require_credentials"
    assert steps["exchange_authorization_code"]["next"] == "require_credentials"
    assert steps["require_credentials"]["next"] == "verify_credentials"
    assert steps["verify_credentials"]["next"] == "backup_codex_config"
    assert steps["backup_codex_config"]["next"] == "write_codex_config"
    assert steps["write_codex_config"]["next"] == "verify_codex"
    assert steps["verify_codex"]["next"] == "route_codex_validation"
    assert steps["route_codex_validation"]["cases"]["final"] == "commit_codex_config"
    assert steps["route_codex_validation"]["default"] == "restore_failed_codex_config"
    assert steps["commit_codex_config"]["next"] == "credentials_ready"
    assert steps["restore_failed_codex_config"]["next"] == "validation_error"


def test_codex_auth_check_does_not_delete_credentials_file() -> None:
    agent_path = Path("apps/agents/auths/codex/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    command = _steps_by_name(agent)["check_codex_credentials"]["command"]

    assert "cleanup-authorization" in command
    assert "openai-codex.pending.json" not in command
    assert "openai-codex.callback.json" not in command
    assert "openai-codex.server.json" not in command
    assert '"$credentials_file"' not in command


def test_codex_auth_updates_user_provider_catalog_and_global_selection() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/codex/agent.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)
    write_command = steps["write_codex_config"]["command"]
    commit_command = steps["commit_codex_config"]["command"]

    assert 'config_file="$settings_dir/providers.json"' in write_command
    assert 'provider.pop("model", None)' in write_command
    assert 'provider["credentials_file"] = credentials_file' in write_command
    assert 'llm["default_provider"]' not in write_command
    assert 'context["window_width_tokens"]' not in write_command
    assert 'config_file="$settings_dir/agent.json"' in commit_command
    assert 'llm["provider"] = provider.strip()' in commit_command
    assert 'llm["model"] = model.strip()' in commit_command
    assert 'local_config_file="{{flow.dir}}/agent.json"' in commit_command
    assert 'verify_codex' in steps


def test_codex_auth_helper_reads_credentials_path_from_user_provider_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_codex_auth_module()
    providers_path = tmp_path / ".skiller" / "settings" / "providers.json"
    credentials_path = tmp_path / ".skiller" / "secrets" / "codex.json"
    providers_path.parent.mkdir(parents=True)
    providers_path.write_text(
        '{"providers": {"codex": {"credentials_file": "'
        + str(credentials_path)
        + '"}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: tmp_path))

    assert module.default_credentials_file() == credentials_path


def test_codex_auth_temp_files_are_stored_outside_secrets(tmp_path, monkeypatch) -> None:
    codex_auth = _load_codex_auth_module()
    state_dir = tmp_path / "runtime" / "auth" / "codex"
    credentials_file = tmp_path / "secrets" / "openai-codex.json"
    monkeypatch.setenv("SKILLER_OPENAI_CODEX_AUTH_STATE_DIR", str(state_dir))

    assert codex_auth.pending_file(credentials_file) == state_dir / "openai-codex.pending.json"
    assert codex_auth.callback_file(credentials_file) == state_dir / "openai-codex.callback.json"
    assert codex_auth.server_file(credentials_file) == state_dir / "openai-codex.server.json"
    assert codex_auth.server_ready_file(credentials_file) == (
        state_dir / "openai-codex.callback-ready"
    )
    assert codex_auth.server_log_file(credentials_file) == state_dir / "openai-codex.callback.log"
    assert state_dir.stat().st_mode & 0o777 == 0o700
    assert state_dir != credentials_file.parent


def test_minimax_auth_writes_config_before_validation_and_restores_on_failure() -> None:
    agent_path = Path("apps/agents/auths/minimax/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    steps = _steps_by_name(agent)

    assert steps["route_minimax_config"]["cases"]["ready"] == "backup_minimax_config"
    assert steps["route_api_key_shape"]["cases"]["valid"] == "write_minimax_secret"
    assert steps["write_minimax_secret"]["next"] == "backup_minimax_config"
    assert steps["backup_minimax_config"]["next"] == "write_minimax_config"
    assert steps["write_minimax_config"]["next"] == "verify_minimax"
    assert steps["route_minimax_validation"]["cases"]["final"] == "commit_minimax_config"
    assert steps["route_minimax_validation"]["default"] == "restore_failed_minimax_config"
    assert steps["commit_minimax_config"]["next"] == "done"
    assert steps["restore_failed_minimax_config"]["next"] == "validation_error"


def test_minimax_auth_ready_check_uses_existing_secret_without_requiring_config() -> None:
    command = _steps_by_name(
        yaml.safe_load(
            Path("apps/agents/auths/minimax/agent.yaml").read_text(encoding="utf-8")
        )
    )["check_minimax_config"]["command"]

    assert 'if [ -s "$secret_file" ]; then' in command
    assert 'if [ -s "$config_file" ] && [ -s "$secret_file" ]; then' not in command


def test_minimax_auth_updates_user_provider_catalog() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/minimax/agent.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)
    write_command = steps["write_minimax_config"]["command"]

    assert 'config_file="$settings_dir/providers.json"' in write_command
    assert 'llm["default_provider"]' not in write_command
    assert 'context["window_width_tokens"]' not in write_command
    assert 'provider.pop("model", None)' in write_command
    assert 'provider["api_key_file"] = secret_file' in write_command


def test_minimax_auth_commits_global_agent_selection() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/minimax/agent.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)
    commit_command = steps["commit_minimax_config"]["command"]

    assert 'config_file="$settings_dir/agent.json"' in commit_command
    assert 'llm["provider"] = provider.strip()' in commit_command
    assert 'llm["model"] = model.strip()' in commit_command
    assert 'local_config_file="{{flow.dir}}/agent.json"' in commit_command


def test_minimax_auth_helper_reads_api_key_path_from_user_provider_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_minimax_auth_module()
    settings_dir = tmp_path / ".skiller" / "settings"
    providers_path = settings_dir / "providers.json"
    secret_path = tmp_path / ".skiller" / "secrets" / "minimax.key"
    providers_path.parent.mkdir(parents=True)
    providers_path.write_text(
        '{"providers": {"minimax": {"api_key_file": "'
        + str(secret_path)
        + '"}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: tmp_path))

    assert module.default_api_key_file() == secret_path


def test_moonshot_auth_updates_user_provider_catalog_and_global_selection() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/moonshot/agent.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)
    write_command = steps["write_moonshot_config"]["command"]
    commit_command = steps["commit_moonshot_config"]["command"]

    assert steps["write_moonshot_config"]["next"] == "verify_moonshot"
    assert steps["route_moonshot_validation"]["cases"]["final"] == (
        "commit_moonshot_config"
    )
    assert steps["route_moonshot_validation"]["default"] == (
        "restore_failed_moonshot_config"
    )
    assert 'config_file="$settings_dir/providers.json"' in write_command
    assert 'provider.pop("model", None)' in write_command
    assert 'provider["api_key_file"] = secret_file' in write_command
    assert 'llm["default_provider"]' not in write_command
    assert 'context["window_width_tokens"]' not in write_command
    assert 'config_file="$settings_dir/agent.json"' in commit_command
    assert 'llm["provider"] = provider.strip()' in commit_command
    assert 'llm["model"] = model.strip()' in commit_command
    assert 'local_config_file="{{flow.dir}}/agent.json"' in commit_command


def test_moonshot_auth_helper_reads_api_key_path_from_user_provider_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_moonshot_auth_module()
    providers_path = tmp_path / ".skiller" / "settings" / "providers.json"
    secret_path = tmp_path / ".skiller" / "secrets" / "moonshot.key"
    providers_path.parent.mkdir(parents=True)
    providers_path.write_text(
        '{"providers": {"moonshot": {"api_key_file": "'
        + str(secret_path)
        + '"}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: tmp_path))

    assert module.default_api_key_file() == secret_path


def test_bedrock_auth_updates_user_provider_catalog_and_global_selection() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/bedrock/agent.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)

    assert steps["route_bedrock_config"]["cases"]["ready"] == (
        "write_bedrock_config_existing"
    )
    assert steps["write_bedrock_config_existing"]["next"] == "verify_bedrock"
    assert steps["write_bedrock_config_skiller"]["next"] == "verify_bedrock"
    assert steps["write_bedrock_config_custom"]["next"] == "verify_bedrock"
    assert steps["route_bedrock_validation"]["cases"]["final"] == (
        "commit_bedrock_config"
    )
    assert steps["route_bedrock_validation"]["default"] == (
        "restore_failed_bedrock_config"
    )
    assert steps["commit_bedrock_config"]["next"] == "credentials_ready"

    for step_name in (
        "write_bedrock_config_existing",
        "write_bedrock_config_skiller",
        "write_bedrock_config_custom",
    ):
        command = steps[step_name]["command"]
        assert 'config_file="$settings_dir/providers.json"' in command
        assert 'provider.pop("model", None)' in command
        assert 'provider["profile"] = profile' in command
        assert 'llm["default_provider"]' not in command
        assert 'context["window_width_tokens"]' not in command
        assert "<<'PY'" in command

    assert steps["write_bedrock_config_custom"]["env"] == {
        "BEDROCK_PROFILE": '{{output_value("ask_custom_profile").payload.text}}'
    }

    commit_command = steps["commit_bedrock_config"]["command"]
    assert 'config_file="$settings_dir/agent.json"' in commit_command
    assert 'llm["provider"] = provider.strip()' in commit_command
    assert 'llm["model"] = model.strip()' in commit_command
    assert 'local_config_file="{{flow.dir}}/agent.json"' in commit_command


def test_bedrock_auth_helper_reads_profile_from_user_provider_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_bedrock_auth_module()
    providers_path = tmp_path / ".skiller" / "settings" / "providers.json"
    providers_path.parent.mkdir(parents=True)
    providers_path.write_text(
        '{"providers": {"bedrock": {"profile": "custom-profile"}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: tmp_path))

    assert module._configured_profile() == "custom-profile"


def test_lmstudio_auth_updates_user_catalog_and_verifies_with_agent() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/lmstudio/agent.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)

    assert steps["backup_lmstudio_config_existing"]["next"] == (
        "write_lmstudio_config_existing"
    )
    assert steps["write_lmstudio_config_existing"]["next"] == "verify_lmstudio"
    assert steps["write_lmstudio_config_custom"]["next"] == "verify_lmstudio"
    assert steps["route_lmstudio_validation"]["cases"]["final"] == (
        "commit_lmstudio_config"
    )
    assert steps["route_lmstudio_validation"]["default"] == (
        "restore_failed_lmstudio_config"
    )
    assert steps["commit_lmstudio_config"]["next"] == "done"
    assert "verify_lmstudio" in steps
    assert not Path("apps/agents/auths/lmstudio/agent.json").exists()


def test_lmstudio_auth_helper_writes_and_restores_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_lmstudio_auth_module()
    settings_dir = tmp_path / ".skiller" / "settings"
    providers_path = settings_dir / "providers.json"
    agent_path = settings_dir / "agent.json"
    settings_dir.mkdir(parents=True)
    providers_path.write_text(
        '{"providers": {"moonshot": {"timeout_seconds": 30}}}\n',
        encoding="utf-8",
    )
    agent_path.write_text(
        '{"llm": {"provider": "moonshot", "model": "kimi-k3"}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(module.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(
        module,
        "discover_models",
        lambda base_url: {
            "base_url": module.normalize_base_url(base_url),
            "model": "local-model",
            "models": [
                {
                    "model": "local-model",
                    "context_window_tokens": 65_536,
                }
            ],
        },
    )

    module.backup_configuration()
    module.configure("http://localhost:1234")

    providers = yaml.safe_load(providers_path.read_text(encoding="utf-8"))
    lmstudio = providers["providers"]["lmstudio"]
    assert lmstudio == {
        "base_url": "http://localhost:1234/v1",
        "models": [
            {
                "context_window_tokens": 65_536,
                "model": "local-model",
            }
        ],
        "timeout_seconds": 120,
    }
    selection = yaml.safe_load(agent_path.read_text(encoding="utf-8"))["llm"]
    assert selection == {"provider": "lmstudio", "model": "local-model"}

    module.restore_configuration()

    restored_providers = yaml.safe_load(providers_path.read_text(encoding="utf-8"))
    restored_agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    assert restored_providers == {
        "providers": {"moonshot": {"timeout_seconds": 30}}
    }
    assert restored_agent == {
        "llm": {"provider": "moonshot", "model": "kimi-k3"}
    }


def test_lmstudio_auth_uses_api_catalog_context_windows(
    monkeypatch,
) -> None:
    module = _load_lmstudio_auth_module()

    class ModelsResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: ModelsResponse(
            {
                "models": [
                    {
                        "type": "llm",
                        "key": "downloaded",
                        "max_context_length": 262_144,
                    },
                    {
                        "type": "llm",
                        "key": "loaded",
                        "max_context_length": 262_144,
                        "loaded_instances": [
                            {"config": {"context_length": 131_072}}
                        ],
                    },
                    {"type": "embedding", "key": "embedding"},
                ]
            }
        ),
    )
    monkeypatch.setattr(
        module,
        "_configured_context_windows",
        lambda: {"downloaded": 65_536},
    )

    discovered = module.discover_models("http://localhost:1234")

    assert discovered == {
        "base_url": "http://localhost:1234/v1",
        "model": "loaded",
        "models": [
            {"model": "downloaded", "context_window_tokens": 262_144},
            {"model": "loaded", "context_window_tokens": 131_072},
        ],
    }


def test_lmstudio_auth_uses_lm_api_token_for_model_catalog(monkeypatch) -> None:
    module = _load_lmstudio_auth_module()
    monkeypatch.setenv("LM_API_TOKEN", "local-token")

    headers = module._lmstudio_api_headers()

    assert headers == {"Authorization": "Bearer local-token"}


def test_auth_provider_flows_emit_load_session_post_action() -> None:
    for flow in ("codex", "minimax", "moonshot", "bedrock", "lmstudio"):
        flow_path = Path(f"apps/agents/auths/{flow}/agent.yaml")
        agent = yaml.safe_load(
            flow_path.read_text(encoding="utf-8")
        )

        assert agent["inputs"] == {"continue_id": "string"}
        assert agent["on_success"] == {
            "cleanup": True,
            "action": {
                "type": "post",
                "label": "Auth success",
                "arg": "load_session",
                "params": "run_id={{inputs.continue_id}}",
                "auto": True,
            },
        }
        assert agent["on_error"] == {"cleanup": True}


def test_auth_menu_forwards_continue_id_to_provider_flows() -> None:
    agent = yaml.safe_load(
        Path("apps/agents/auths/auth.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)

    assert agent["inputs"] == {"continue_id": "string"}
    for step_name in (
        "start_codex",
        "start_minimax",
        "start_bedrock",
        "start_lmstudio",
        "start_moonshot",
    ):
        assert steps[step_name]["action"]["params"] == (
            "--arg continue_id={{inputs.continue_id}}"
        )


def _steps_by_name(agent: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for step in agent["steps"]:
        assert isinstance(step, dict)
        name = (
            step.get("shell")
            or step.get("switch")
            or step.get("notify")
            or step.get("wait_input")
            or step.get("agent")
        )
        assert isinstance(name, str)
        result[name] = step
    return result


def _load_codex_auth_module() -> ModuleType:
    module_path = Path("apps/agents/auths/codex/codex_auth.py")
    spec = importlib.util.spec_from_file_location("codex_auth", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_minimax_auth_module() -> ModuleType:
    module_path = Path("apps/agents/auths/minimax/minimax_auth.py")
    spec = importlib.util.spec_from_file_location("minimax_auth", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_moonshot_auth_module() -> ModuleType:
    module_path = Path("apps/agents/auths/moonshot/moonshot_auth.py")
    spec = importlib.util.spec_from_file_location("moonshot_auth", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_bedrock_auth_module() -> ModuleType:
    module_path = Path("apps/agents/auths/bedrock/bedrock_auth.py")
    spec = importlib.util.spec_from_file_location("bedrock_auth", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_lmstudio_auth_module() -> ModuleType:
    module_path = Path("apps/agents/auths/lmstudio/lmstudio_auth.py")
    spec = importlib.util.spec_from_file_location("lmstudio_auth", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
