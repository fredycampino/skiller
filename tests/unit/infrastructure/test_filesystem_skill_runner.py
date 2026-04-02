from __future__ import annotations

import json

import pytest

from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner

pytestmark = pytest.mark.unit


class _FakeExecutionOutputStore:
    def __init__(self, payloads: dict[str, dict[str, object]] | None = None) -> None:
        self.payloads = payloads or {}

    def get_execution_output(self, body_ref: str) -> dict[str, object] | None:
        return self.payloads.get(body_ref)


def test_load_skill_internal_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "demo.yaml").write_text(
        "name: demo\nstart: demo_start\nsteps: []\n", encoding="utf-8"
    )

    runner = FilesystemSkillRunner(skills_dir=str(skills_dir))

    skill = runner.load_skill("internal", "demo")

    assert skill["name"] == "demo"
    assert skill["steps"] == []


def test_load_skill_file_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.yaml"
    skill_file.write_text("name: external\nstart: external_start\nsteps: []\n", encoding="utf-8")

    runner = FilesystemSkillRunner(skills_dir="skills")

    skill = runner.load_skill("file", str(skill_file))

    assert skill["name"] == "external"
    assert skill["steps"] == []


def test_load_skill_file_from_json(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.json"
    skill_file.write_text(
        json.dumps({"name": "external-json", "start": "external_start", "steps": []}),
        encoding="utf-8",
    )

    runner = FilesystemSkillRunner(skills_dir="skills")

    skill = runner.load_skill("file", str(skill_file))

    assert skill["name"] == "external-json"
    assert skill["steps"] == []


@pytest.mark.parametrize("skill_source,skill_ref", [("other", "demo"), ("file", "/tmp/demo.txt")])
def test_load_skill_rejects_invalid_source_or_extension(skill_source: str, skill_ref: str) -> None:
    runner = FilesystemSkillRunner(skills_dir="skills")

    with pytest.raises((ValueError, FileNotFoundError)):
        runner.load_skill(skill_source, skill_ref)


def test_render_step_preserves_type_for_full_template_value() -> None:
    runner = FilesystemSkillRunner(skills_dir="skills")

    rendered = runner.render_step(
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
                    "step_type": "llm_prompt",
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
    )

    assert rendered["values"]["copied_object"] == {
        "severity": "low",
        "tags": ["triage", "retry"],
    }
    assert rendered["values"]["copied_list"] == ["triage", "retry"]
    assert rendered["values"]["text"] == "severity=low"


def test_render_step_can_resolve_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_GITHUB_MCP_URL", "https://api.github.example/mcp")
    monkeypatch.setenv("AGENT_GITHUB_MCP_TOKEN", "secret-token")
    runner = FilesystemSkillRunner(skills_dir="skills")

    rendered = runner.render_step(
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
    )

    assert rendered["mcp"][0]["url"] == "https://api.github.example/mcp"
    assert rendered["mcp"][0]["headers"]["Authorization"] == "Bearer secret-token"


def test_render_step_can_resolve_output_value_from_persisted_output() -> None:
    runner = FilesystemSkillRunner(skills_dir="skills")

    rendered = runner.render_step(
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
    )

    assert rendered["message"] == "existing_tunnels=tunnel-a\ntunnel-b"
    assert rendered["stderr"] == "tunnel-a\ntunnel-b"


def test_render_step_can_resolve_output_value_from_body_ref() -> None:
    runner = FilesystemSkillRunner(
        skills_dir="skills",
        execution_output_store=_FakeExecutionOutputStore(
            {
                "execution_output:1": {
                    "value": {
                        "ok": True,
                        "exit_code": 0,
                        "stdout": "",
                        "stderr": "full-tunnel-list",
                    }
                }
            }
        ),
    )

    rendered = runner.render_step(
        {
            "message": '{{output_value("inspect_cloudflared").stderr}}',
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
                            "truncated": True,
                            "stderr": "preview...",
                        },
                        "body_ref": "execution_output:1",
                    },
                }
            }
        },
    )

    assert rendered["message"] == "full-tunnel-list"


def test_render_step_raises_clear_error_when_output_value_path_is_missing() -> None:
    runner = FilesystemSkillRunner(skills_dir="skills")

    with pytest.raises(ValueError, match="OUTPUT_VALUE_PATH_MISSING"):
        runner.render_step(
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
        )


def test_render_step_rejects_direct_output_value_access() -> None:
    runner = FilesystemSkillRunner(skills_dir="skills")

    with pytest.raises(ValueError, match="SKILL_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS"):
        runner.render_step(
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
        )
