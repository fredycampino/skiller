import json
from pathlib import Path

import pytest
import yaml

from skiller.application.tools.files import FilesAction, FilesTool, FilesToolRequest
from skiller.infrastructure.config.agent_config_schema import (
    DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS,
)


def test_flows_agent_uses_shell_and_files() -> None:
    agent_path = Path("apps/agents/flows/flows.yaml")
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
    config_path = Path("apps/agents/flows/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["loop"] == {
        "max_turns": 50,
        "max_tool_calls": DEFAULT_AGENT_LOOP_MAX_TOOL_CALLS,
    }

    shell_config = config["tools"]["shell"]
    assert shell_config["allowed_paths"] == [
        "{{flow.dir}}",
        "{{runtime.cwd}}",
        "{{runtime.venv}}",
    ]
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
    config_path = Path("apps/agents/flows/agent.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["tools"]["files"] == {
        "read": [
            "{{flow.dir}}",
            "{{runtime.cwd}}",
            "~/.skiller/settings/",
        ],
        "write": [
            "{{runtime.cwd}}",
        ],
        "all": [],
    }


def test_flows_files_config_resolves_workspace_when_flow_is_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = Path("apps/agents/flows/agent.json")
    agent_config = json.loads(config_path.read_text(encoding="utf-8"))
    installed_flow_dir = tmp_path / "venv" / "site-packages" / "apps" / "agents" / "flows"
    workspace = tmp_path / "workspace"
    installed_flow_dir.mkdir(parents=True)
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    tool = FilesTool()
    files_config = tool.to_runtime_config(
        agent_config["tools"]["files"],
        base_path=installed_flow_dir,
    )

    assert files_config.read[:2] == (installed_flow_dir, workspace)
    assert files_config.write == (workspace,)

    workspace_write = tool.policy(
        config=files_config,
        request=FilesToolRequest(
            action=FilesAction.WRITE,
            path="todo/issue.md",
            write_text="issue",
        ),
    )
    installed_write = tool.policy(
        config=files_config,
        request=FilesToolRequest(
            action=FilesAction.WRITE,
            path=str(installed_flow_dir / "agent.json"),
            write_text="changed",
        ),
    )

    assert workspace_write.ok is True
    assert workspace_write.request is not None
    assert workspace_write.request.effective_path == str(workspace / "todo" / "issue.md")
    assert installed_write.ok is False


def test_flows_agent_has_explicit_exit_route() -> None:
    agent_path = Path("apps/agents/flows/flows.yaml")
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
