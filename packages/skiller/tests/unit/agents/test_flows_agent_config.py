import json
from pathlib import Path

import yaml

from skiller.infrastructure.config.agent_config_schema import (
    DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS,
)


def test_flows_agent_uses_shell_and_files() -> None:
    agent_path = Path("packages/skiller/agents/flows/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    agent_step = next(step for step in agent["steps"] if "agent" in step)

    assert agent_step["agent"] == "flows_agent"
    assert agent_step["system"] == {"file": "./system.md"}
    assert agent_step["tools"] == [
        "shell",
        "files",
    ]
    assert agent_step["next"] == "ask_user"


def test_flows_local_agent_config_is_restricted() -> None:
    config_path = Path("packages/skiller/agents/flows/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["loop"] == {
        "max_turns": 50,
        "max_tool_calls": DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS,
    }

    shell_config = config["tools"]["shell"]
    assert shell_config["allowed_paths"] == ["."]
    assert shell_config["allowlist_enabled"] is True
    assert shell_config["allow_env_prefix"] is True
    assert shell_config["allowed_commands"] == [
        "pwd",
        "ls",
        "find",
        "rg",
        "grep",
        "head",
        "tail",
        "wc",
        "nl",
        "cat",
        "git",
        "pytest",
        "ruff",
        "python",
        "python3",
        "skiller",
        "date",
    ]


def test_flows_files_config_allows_workspace_read_write() -> None:
    config_path = Path("packages/skiller/agents/flows/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["tools"]["files"] == {
        "read": [
            ".",
            "~/.skiller/settings/",
        ],
        "write": [
            ".",
        ],
        "all": [],
    }


def test_flows_agent_has_explicit_exit_route() -> None:
    agent_path = Path("packages/skiller/agents/flows/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    wait_step = next(step for step in agent["steps"] if step.get("wait_input") == "ask_user")
    switch_step = next(step for step in agent["steps"] if step.get("switch") == "decide_exit")
    done_step = next(step for step in agent["steps"] if step.get("notify") == "done")

    assert wait_step["next"] == "decide_exit"
    assert switch_step["cases"] == {
        "exit": "done",
        "quit": "done",
        "bye": "done",
    }
    assert switch_step["default"] == "flows_agent"
    assert done_step["message"] == "Flows agent closed."


def test_flows_system_owns_agentic_flow_guidance() -> None:
    system_path = Path("packages/skiller/agents/flows/system.md")
    system = system_path.read_text(encoding="utf-8")

    assert "You are Flows" in system
    assert "Agentic Flows `.yaml`" in system
    assert "flows/<group>/<name>.yaml" in system
    assert "../../docs/flows/flow-schema.md" in system
    assert "../../docs/steps/agent.md" in system
    assert "AGENT_DB_PATH" in system


def test_flows_onboarding_points_to_flows_agent() -> None:
    intro_path = Path("packages/skiller/agents/onboarding/intro.yaml")
    intro = intro_path.read_text(encoding="utf-8")

    assert "/run flows" in intro
    assert "skiller run flows" in intro
    assert "builder" not in intro
