import json
from pathlib import Path

import yaml


def test_ci_agent_uses_shell_and_files() -> None:
    agent_path = Path("packages/skiller/agents/ci/agent.yaml")
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    agent_step = next(step for step in agent["steps"] if "agent" in step)

    assert agent_step["tools"] == [
        "shell",
        "files",
    ]


def test_ci_shell_config_is_restricted() -> None:
    config_path = Path("packages/skiller/agents/ci/agent.json")
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
        "head",
        "tail",
        "wc",
        "nl",
        "cat",
        "git",
        "ruff",
        "pytest",
        "uv",
        "python",
        "python3",
        "skiller",
        "date",
    ]


def test_ci_files_config_allows_repo_read_write() -> None:
    config_path = Path("packages/skiller/agents/ci/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    files_config = config["tools"]["files"]

    assert files_config == {
        "read": [
            ".",
            "~/.skiller/settings/",
        ],
        "write": [
            ".",
        ],
        "all": [],
    }
