import json
from pathlib import Path

import yaml


def test_mono_agent_has_named_agent_id() -> None:
    agent_path = Path("packages/skiller/agents/mono/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    agent_step = next(step for step in agent["steps"] if "agent" in step)

    assert agent_step["agent"] == "mono_agent"
    assert agent_step["system"] == {"file": "./system.md"}


def test_mono_system_requires_architecture_review() -> None:
    system_path = Path("packages/skiller/agents/mono/system.md")
    system = system_path.read_text(encoding="utf-8")

    assert "packages/skiller/docs/architecture/dev-rules.md" in system
    assert "packages/skiller/docs/architecture/architecture.md" in system
    assert "packages/skiller/docs/architecture/code-style.md" in system
    assert "packages/skiller/docs/architecture/naming-style.md" in system
    assert "architecture violations" in system
    assert "dead code" in system
    assert "tests that do not prove useful behavior" in system


def test_mono_shell_config_is_restricted() -> None:
    config_path = Path("packages/skiller/agents/mono/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    shell_config = config["tools"]["shell"]

    assert shell_config["allowed_paths"] == [".", "./.venv/bin/skiller"]
    assert shell_config["allowlist_enabled"] is True
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
        "git",
        "pytest",
        "ruff",
        "python",
        "python3",
        "echo",
        "sleep",
        "skiller",
    ]
