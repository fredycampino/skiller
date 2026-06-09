from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _FlowReference:
    source: str
    ref: str


def _build_render_runner(tmp_path) -> tuple[FilesystemSkillRunner, _FlowReference]:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: check\nsteps: []\n",
        encoding="utf-8",
    )
    return FilesystemSkillRunner(skills_dir=str(agents_dir)), _FlowReference(
        source="internal",
        ref="demo",
    )


def test_load_skill_internal_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "demo.yaml").write_text(
        "name: demo\nstart: demo_start\nsteps: []\n", encoding="utf-8"
    )

    runner = FilesystemSkillRunner(skills_dir=str(skills_dir))

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

    runner = FilesystemSkillRunner(skills_dir=str(agents_dir))

    skill = runner.load("internal", "demo")

    assert skill["name"] == "demo"
    assert skill["steps"] == []


def test_load_skill_file_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.yaml"
    skill_file.write_text("name: external\nstart: external_start\nsteps: []\n", encoding="utf-8")

    runner = FilesystemSkillRunner(skills_dir="skills")

    skill = runner.load("file", str(skill_file))

    assert skill["name"] == "external"
    assert skill["steps"] == []


def test_load_skill_file_from_json(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.json"
    skill_file.write_text(
        json.dumps({"name": "external-json", "start": "external_start", "steps": []}),
        encoding="utf-8",
    )

    runner = FilesystemSkillRunner(skills_dir="skills")

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
    runner = FilesystemSkillRunner(skills_dir=str(agents_dir))

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
    runner = FilesystemSkillRunner(skills_dir=str(agents_dir))

    path = runner.resolve_file_path("internal", "demo", "agent.json")

    assert path == agent_dir / "agent.json"


def test_read_file_rejects_escape_from_skill_directory(tmp_path) -> None:  # noqa: ANN001
    agents_dir = tmp_path / "agents"
    agent_dir = agents_dir / "demo"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yaml").write_text(
        "name: demo\nstart: support_agent\nsteps: []\n",
        encoding="utf-8",
    )
    (agents_dir / "secret.md").write_text("secret", encoding="utf-8")
    runner = FilesystemSkillRunner(skills_dir=str(agents_dir))

    with pytest.raises(ValueError, match="escapes skill directory"):
        runner.read_file("internal", "demo", "../secret.md")


def test_read_file_from_file_source_directory(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.yaml"
    skill_file.write_text(
        "name: external\nstart: support_agent\nsteps: []\n",
        encoding="utf-8",
    )
    (tmp_path / "system.md").write_text("External system\n", encoding="utf-8")
    runner = FilesystemSkillRunner(skills_dir="skills")

    content = runner.read_file("file", str(skill_file), "system.md")

    assert content == "External system\n"


@pytest.mark.parametrize(("source", "ref"), [("other", "demo"), ("file", "/tmp/demo.txt")])
def test_load_rejects_invalid_source_or_extension(source: str, ref: str) -> None:
    runner = FilesystemSkillRunner(skills_dir="skills")

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
    runner = FilesystemSkillRunner(skills_dir=str(agents_dir))

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
    runner = FilesystemSkillRunner(skills_dir="skills")

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
            "message": 'existing_tunnels={{output_value("inspect_cloudflared").stderr}}',
            "stderr": '{{output_value("inspect_cloudflared").stderr}}',
        },
        {
            "step_executions": {
                "inspect_cloudflared": {
                    "step_type": "shell",
                    "input": {},
                    "evaluation": {},
                    "output": {
                        "text": "ready",
                        "value": {
                            "ok": True,
                            "exit_code": 0,
                            "stdout": "",
                            "stderr": "tunnel-a\ntunnel-b",
                        },
                        "body_ref": None,
                    },
                }
            }
        },
        flow=flow,
    )

    assert rendered["message"] == "existing_tunnels=tunnel-a\ntunnel-b"
    assert rendered["stderr"] == "tunnel-a\ntunnel-b"


def test_render_step_raises_clear_error_when_output_value_path_is_missing(tmp_path) -> None:  # noqa: ANN001
    runner, flow = _build_render_runner(tmp_path)

    with pytest.raises(ValueError, match="OUTPUT_VALUE_PATH_MISSING"):
        runner.render(
            {
                "message": '{{output_value("inspect_cloudflared").missing_field}}',
            },
            {
                "step_executions": {
                    "inspect_cloudflared": {
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
                "message": "{{step_executions.inspect_cloudflared.output.value.stderr}}",
            },
            {
                "step_executions": {
                    "inspect_cloudflared": {
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
