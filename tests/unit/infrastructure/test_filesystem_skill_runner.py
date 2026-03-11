from __future__ import annotations

import json

import pytest

from skiller.infrastructure.skills.filesystem_skill_runner import FilesystemSkillRunner


pytestmark = pytest.mark.unit


def test_load_skill_internal_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "demo.yaml").write_text("name: demo\nsteps: []\n", encoding="utf-8")

    runner = FilesystemSkillRunner(skills_dir=str(skills_dir))

    skill = runner.load_skill("internal", "demo")

    assert skill["name"] == "demo"
    assert skill["steps"] == []


def test_load_skill_file_from_yaml(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.yaml"
    skill_file.write_text("name: external\nsteps: []\n", encoding="utf-8")

    runner = FilesystemSkillRunner(skills_dir="skills")

    skill = runner.load_skill("file", str(skill_file))

    assert skill["name"] == "external"
    assert skill["steps"] == []


def test_load_skill_file_from_json(tmp_path) -> None:  # noqa: ANN001
    skill_file = tmp_path / "external.json"
    skill_file.write_text(json.dumps({"name": "external-json", "steps": []}), encoding="utf-8")

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
            "id": "prepare",
            "type": "assign",
            "values": {
                "copied_object": "{{results.analysis}}",
                "copied_list": "{{results.analysis.tags}}",
                "text": "severity={{results.analysis.severity}}",
            },
        },
        {
            "results": {
                "analysis": {
                    "severity": "low",
                    "tags": ["triage", "retry"],
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
