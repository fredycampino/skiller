from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from skiller.infrastructure.skills import filesystem_runner_port
from skiller.infrastructure.skills.filesystem_runner_port import FilesystemRunnerPort

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _FlowReference:
    source: str
    ref: str


def _build_render_runner(tmp_path) -> tuple[FilesystemRunnerPort, _FlowReference]:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: check\nsteps: []\n",
        encoding="utf-8",
    )
    return FilesystemRunnerPort(flows_dir=agents_dir), _FlowReference(
        source="internal",
        ref="demo",
    )


def test_default_internal_catalog_uses_repo_apps_agents(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:  # noqa: ANN001
    repo_dir = tmp_path / "repo"
    module_file = (
        repo_dir
        / "packages"
        / "skiller"
        / "src"
        / "skiller"
        / "infrastructure"
        / "skills"
        / "filesystem_runner_port.py"
    )
    module_file.parent.mkdir(parents=True)
    module_file.write_text("", encoding="utf-8")
    apps_agents_dir = repo_dir / "apps" / "agents"
    apps_agents_dir.mkdir(parents=True)

    monkeypatch.setattr(filesystem_runner_port, "__file__", str(module_file))

    assert filesystem_runner_port._find_default_internal_flow_catalog_dir() == apps_agents_dir


def test_default_internal_catalog_uses_installed_apps_agents_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:  # noqa: ANN001
    site_packages_dir = tmp_path / "site-packages"
    module_file = (
        site_packages_dir
        / "skiller"
        / "infrastructure"
        / "skills"
        / "filesystem_runner_port.py"
    )
    module_file.parent.mkdir(parents=True)
    module_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(filesystem_runner_port, "__file__", str(module_file))

    assert filesystem_runner_port._find_default_internal_flow_catalog_dir() == (
        site_packages_dir / "apps" / "agents"
    )


def test_load_skill_internal_from_yaml(tmp_path) -> None:  # noqa: ANN001
    flows_dir = tmp_path / "skills"
    flows_dir.mkdir()
    (flows_dir / "demo.yaml").write_text(
        "name: demo\nstart: demo_start\nsteps: []\n", encoding="utf-8"
    )

    runner = FilesystemRunnerPort(flows_dir=flows_dir)

    skill = runner.load("internal", "demo")

    assert skill["name"] == "demo"
    assert skill["steps"] == []


def test_load_skill_internal_from_agent_directory_layout(tmp_path) -> None:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: demo_start\nsteps: []\n", encoding="utf-8"
    )

    runner = FilesystemRunnerPort(flows_dir=agents_dir)

    skill = runner.load("internal", "demo")

    assert skill["name"] == "demo"
    assert skill["steps"] == []


def test_load_skill_file_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.yaml"
    skill_file.write_text("name: external\nstart: external_start\nsteps: []\n", encoding="utf-8")

    runner = FilesystemRunnerPort(flows_dir=Path("skills"))

    skill = runner.load("file", str(skill_file))

    assert skill["name"] == "external"
    assert skill["steps"] == []


def test_load_skill_file_from_json(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.json"
    skill_file.write_text(
        json.dumps({"name": "external-json", "start": "external_start", "steps": []}),
        encoding="utf-8",
    )

    runner = FilesystemRunnerPort(flows_dir=Path("skills"))

    skill = runner.load("file", str(skill_file))

    assert skill["name"] == "external-json"
    assert skill["steps"] == []


def test_read_file_from_internal_agent_directory(tmp_path) -> None:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: support_agent\nsteps: []\n",
        encoding="utf-8",
    )
    (agent_dir / "system.md").write_text("System prompt\n", encoding="utf-8")
    runner = FilesystemRunnerPort(flows_dir=agents_dir)

    content = runner.read_file("internal", "demo", "./system.md")

    assert content == "System prompt\n"


def test_resolve_file_path_from_internal_agent_directory(tmp_path) -> None:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: support_agent\nsteps: []\n",
        encoding="utf-8",
    )
    runner = FilesystemRunnerPort(flows_dir=agents_dir)

    path = runner.resolve_file_path("internal", "demo", "agent.json")

    assert path == agent_dir / "agent.json"


def test_read_file_rejects_escape_from_flow_directory(tmp_path) -> None:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: support_agent\nsteps: []\n",
        encoding="utf-8",
    )
    (agents_dir / "secret.md").write_text("secret", encoding="utf-8")
    runner = FilesystemRunnerPort(flows_dir=agents_dir)

    with pytest.raises(ValueError, match="escapes flow directory"):
        runner.read_file("internal", "demo", "../secret.md")


def test_read_file_from_file_source_directory(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.yaml"
    skill_file.write_text(
        "name: external\nstart: support_agent\nsteps: []\n",
        encoding="utf-8",
    )
    (tmp_path / "system.md").write_text("External system\n", encoding="utf-8")
    runner = FilesystemRunnerPort(flows_dir=Path("skills"))

    content = runner.read_file("file", str(skill_file), "system.md")

    assert content == "External system\n"


@pytest.mark.parametrize(("source", "ref"), [("other", "demo"), ("file", "/tmp/demo.txt")])
def test_load_rejects_invalid_source_or_extension(source: str, ref: str) -> None:
    runner = FilesystemRunnerPort(flows_dir=Path("skills"))

    with pytest.raises((ValueError, FileNotFoundError)):
        runner.load(source, ref)


def test_render_step_preserves_type_for_full_template_value(tmp_path) -> None:  # noqa: ANN001
    runner, flow = _build_render_runner(tmp_path)

    rendered = runner.render(
        {
            "values": {
                "copied_object": '{{output_value("analysis").data}}',
                "copied_list": '{{output_value("analysis").data.tags}}',
                "text": 'severity={{output_value("analysis").data.severity}}',
            },
        },
        {
            "step_executions": {
                "analysis": {
                    "step_type": "agent",
                    "input": {},
                    "evaluation": {},
                    "output": {
                        "text": "ok",
                        "value": {
                            "data": {
                                "severity": "low",
                                "tags": ["triage", "retry"],
                            }
                        },
                        "body_ref": None,
                    },
                }
            }
        },
        flow=flow,
    )

    assert rendered["values"]["copied_object"] == {
        "severity": "low",
        "tags": ["triage", "retry"],
    }
    assert rendered["values"]["copied_list"] == ["triage", "retry"]
    assert rendered["values"]["text"] == "severity=low"



def test_render_step_can_resolve_env_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:  # noqa: ANN001
    monkeypatch.setenv("AGENT_GITHUB_MCP_URL", "https://api.github.example/mcp")
    monkeypatch.setenv("AGENT_GITHUB_MCP_TOKEN", "secret-token")
    runner, flow = _build_render_runner(tmp_path)

    rendered = runner.render(
        {
            "mcp": [
                {
                    "name": "github",
                    "transport": "streamable-http",
                    "url": "{{env.AGENT_GITHUB_MCP_URL}}",
                    "headers": {
                        "Authorization": "Bearer {{env.AGENT_GITHUB_MCP_TOKEN}}",
                    },
                }
            ]
        },
        {"inputs": {}, "step_executions": {}},
        flow=flow,
    )

    assert rendered["mcp"][0]["url"] == "https://api.github.example/mcp"
    assert rendered["mcp"][0]["headers"]["Authorization"] == "Bearer secret-token"


def test_render_step_can_resolve_internal_flow_directory(tmp_path) -> None:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "auths" / "minimax"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: auths/minimax\nstart: check_minimax_config\nsteps: []\n",
        encoding="utf-8",
    )
    runner = FilesystemRunnerPort(flows_dir=agents_dir)

    rendered = runner.render(
        {
            "command": 'python3 "{{flow.dir}}/minimax_auth.py" api-key-file',
        },
        {"inputs": {}, "step_executions": {}},
        flow=_FlowReference(source="internal", ref="auths/minimax"),
    )

    assert rendered["command"] == f'python3 "{agent_dir}/minimax_auth.py" api-key-file'


def test_render_step_can_resolve_file_flow_directory(tmp_path) -> None:  # noqa: ANN001
    flow_file = tmp_path / "external.yaml"
    flow_file.write_text(
        "name: external\nstart: check\nsteps: []\n",
        encoding="utf-8",
    )
    runner = FilesystemRunnerPort(flows_dir=Path("skills"))

    rendered = runner.render(
        {
            "command": 'python3 "{{flow.dir}}/helper.py" check',
        },
        {"inputs": {}, "step_executions": {}},
        flow=_FlowReference(source="file", ref=str(flow_file)),
    )

    assert rendered["command"] == f'python3 "{tmp_path}/helper.py" check'


def test_render_step_can_resolve_output_value_from_persisted_output(tmp_path) -> None:  # noqa: ANN001
    runner, flow = _build_render_runner(tmp_path)

    rendered = runner.render(
        {
            "message": 'existing_output={{output_value("inspect_shell").stderr}}',
            "stderr": '{{output_value("inspect_shell").stderr}}',
        },
        {
            "step_executions": {
                "inspect_shell": {
                    "step_type": "shell",
                    "input": {},
                    "evaluation": {},
                    "output": {
                        "text": "ready",
                        "value": {
                            "ok": True,
                            "exit_code": 0,
                            "stdout": "",
                            "stderr": "line-a\nline-b",
                        },
                        "body_ref": None,
                    },
                }
            }
        },
        flow=flow,
    )

    assert rendered["message"] == "existing_output=line-a\nline-b"
    assert rendered["stderr"] == "line-a\nline-b"


def test_render_step_raises_clear_error_when_output_value_path_is_missing(tmp_path) -> None:  # noqa: ANN001
    runner, flow = _build_render_runner(tmp_path)

    with pytest.raises(ValueError, match="OUTPUT_VALUE_PATH_MISSING"):
        runner.render(
            {
                "message": '{{output_value("inspect_shell").missing_field}}',
            },
            {
                "step_executions": {
                    "inspect_shell": {
                        "step_type": "shell",
                        "input": {},
                        "evaluation": {},
                        "output": {
                            "text": "ready",
                            "value": {"stderr": "ok"},
                            "body_ref": None,
                        },
                    }
                }
            },
            flow=flow,
        )


def test_render_step_rejects_direct_output_value_access(tmp_path) -> None:  # noqa: ANN001
    runner, flow = _build_render_runner(tmp_path)

    with pytest.raises(ValueError, match="FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS"):
        runner.render(
            {
                "message": "{{step_executions.inspect_shell.output.value.stderr}}",
            },
            {
                "step_executions": {
                    "inspect_shell": {
                        "step_type": "shell",
                        "input": {},
                        "evaluation": {},
                        "output": {
                            "text": "ready",
                            "value": {"stderr": "ok"},
                            "body_ref": None,
                        },
                    }
                }
            },
            flow=flow,
        )
