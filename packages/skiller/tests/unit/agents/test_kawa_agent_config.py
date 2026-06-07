import json
from pathlib import Path

import yaml


def test_kawa_agent_uses_shell_and_files() -> None:
    agent_path = Path("packages/skiller/agents/kawa/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    agent_step = next(step for step in agent["steps"] if "agent" in step)

    assert agent_step["agent"] == "kawa_agent"
    assert agent_step["tools"] == [
        "shell",
        "files",
    ]


def test_kawa_agent_owns_runtime_prompt_catalog() -> None:
    system_path = Path("packages/skiller/agents/kawa/system.md")
    system = system_path.read_text(encoding="utf-8")

    assert "packages/skiller/tests/prompts" in system
    assert "A-shell-allowed-paths.md" in system
    assert "E-max-turns.md" in system


def test_kawa_runtime_limits_match_prompt_contracts() -> None:
    config_path = Path("packages/skiller/agents/kawa/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["loop"] == {
        "max_turns": 10,
        "max_tool_calls": 5,
    }


def test_kawa_shell_config_supports_prompt_commands() -> None:
    config_path = Path("packages/skiller/agents/kawa/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    shell_config = config["tools"]["shell"]

    assert shell_config["allowed_paths"] == ["."]
    assert shell_config["allowlist_enabled"] is True
    assert shell_config["allowed_commands"] == [
        "pwd",
        "ls",
        "find",
        "rg",
        "grep",
        "sed",
        "head",
        "tail",
        "sort",
        "wc",
        "nl",
        "cat",
        "git",
        "pytest",
        "ruff",
        "python",
        "python3",
        "skiller",
        "sleep",
        "echo",
        "date",
        "curl",
    ]
