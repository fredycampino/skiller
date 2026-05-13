from __future__ import annotations

import json

import pytest

from skiller.infrastructure.agent.config import resolve_agent_settings

pytestmark = pytest.mark.unit


def test_resolve_agent_settings_reads_agent_loop(tmp_path, monkeypatch) -> None:
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "agent": {
                    "loop": {
                        "max_turns": 12,
                        "max_tool_calls": 7,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    settings = resolve_agent_settings(agent_path)

    assert settings.loop_max_turns == 12
    assert settings.loop_max_tool_calls == 7


def test_resolve_agent_settings_env_overrides_agent_loop(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "agent": {
                    "loop": {
                        "max_turns": 12,
                        "max_tool_calls": 7,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_LOOP_MAX_TURNS", "20")
    monkeypatch.setenv("AGENT_LOOP_MAX_TOOL_CALLS", "3")

    settings = resolve_agent_settings(agent_path)

    assert settings.loop_max_turns == 20
    assert settings.loop_max_tool_calls == 3


def test_resolve_agent_settings_uses_defaults_when_file_missing(tmp_path) -> None:
    missing_path = tmp_path / "missing-agent.json"

    settings = resolve_agent_settings(missing_path)

    assert settings.loop_max_turns == 10
    assert settings.loop_max_tool_calls == 5


def test_resolve_agent_settings_rejects_invalid_agent_shape(tmp_path) -> None:
    agent_path = tmp_path / "agent.json"
    agent_path.write_text(json.dumps({"agent": "bad"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="field 'agent' must be a JSON object"):
        resolve_agent_settings(agent_path)
