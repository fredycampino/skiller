from pathlib import Path

import yaml


def test_codex_auth_writes_config_only_after_credentials_validate() -> None:
    agent_path = Path("packages/skiller/agents/auths/codex.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
    steps = _steps_by_name(agent)

    assert steps["route_codex_credentials"]["cases"]["ready"] == "require_credentials"
    assert steps["exchange_authorization_code"]["next"] == "require_credentials"
    assert steps["require_credentials"]["next"] == "verify_credentials"
    assert steps["verify_credentials"]["next"] == "write_codex_config"
    assert steps["write_codex_config"]["next"] == "credentials_ready"


def test_minimax_auth_writes_config_before_validation_and_restores_on_failure() -> None:
    agent_path = Path("packages/skiller/agents/auths/minimax.yaml")
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
            Path("packages/skiller/agents/auths/minimax.yaml").read_text(encoding="utf-8")
        )
    )["check_minimax_config"]["command"]

    assert 'if [ -s "$secret_file" ]; then' in command
    assert 'if [ -s "$config_file" ] && [ -s "$secret_file" ]; then' not in command


def test_auth_provider_flows_emit_load_session_post_action() -> None:
    for flow in ("codex", "minimax", "bedrock"):
        agent = yaml.safe_load(
            Path(f"packages/skiller/agents/auths/{flow}.yaml").read_text(
                encoding="utf-8"
            )
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
        Path("packages/skiller/agents/auths/auth.yaml").read_text(encoding="utf-8")
    )
    steps = _steps_by_name(agent)

    assert agent["inputs"] == {"continue_id": "string"}
    for step_name in ("start_codex", "start_minimax", "start_bedrock"):
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
