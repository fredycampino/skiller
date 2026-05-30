import json
from pathlib import Path


def test_mono_shell_config_is_restricted() -> None:
    config_path = Path("packages/skiller/agents/mono/agent.json")
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
        "git",
        "pytest",
        "ruff",
        "python",
        "python3",
        "echo",
        "sleep",
    ]
