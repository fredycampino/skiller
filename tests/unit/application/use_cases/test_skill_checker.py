import pytest

from skiller.application.use_cases.skill_checker import SkillCheckerUseCase, SkillCheckStatus

pytestmark = pytest.mark.unit


class _FakeSkillRunner:
    def __init__(self, raw_skill: object) -> None:
        self.raw_skill = raw_skill
        self.calls: list[tuple[str, str]] = []

    def load_skill(self, skill_source: str, skill_ref: str) -> object:
        self.calls.append((skill_source, skill_ref))
        return self.raw_skill


def test_skill_checker_accepts_valid_skill() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "cloudflared",
                "start": "inspect_cloudflared",
                "steps": [
                    {
                        "shell": "inspect_cloudflared",
                        "command": "cloudflared tunnel list --output json",
                        "next": "summarize_tunnels",
                    },
                    {
                        "notify": "summarize_tunnels",
                        "message": '{{output_value("inspect_cloudflared").stderr}}',
                    },
                ],
            }
        )
    )
    result = use_case.execute("cloudflared", skill_source="internal")

    assert result.status == SkillCheckStatus.VALID
    assert result.errors == []


def test_skill_checker_reports_global_errors() -> None:
    use_case = SkillCheckerUseCase(skill_runner=_FakeSkillRunner({}))
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "SKILL_NAME_MISSING",
        "SKILL_START_MISSING",
        "SKILL_STEPS_MISSING",
    ]


def test_skill_checker_rejects_steps_that_are_not_a_list() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "cloudflared",
                "start": "show_message",
                "steps": {},
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["SKILL_STEPS_INVALID"]


def test_skill_checker_rejects_direct_output_value_access() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {"shell": "inspect", "command": "printf ok"},
                    {
                        "notify": "show_message",
                        "message": "{{step_executions.inspect.output.value.stdout}}",
                    },
                ],
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "SKILL_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS"
    ]


def test_skill_checker_rejects_direct_body_ref_access() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {"shell": "inspect", "command": "printf ok"},
                    {
                        "notify": "show_message",
                        "message": "{{step_executions.inspect.output.body_ref}}",
                    },
                ],
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "SKILL_OUTPUT_VALUE_BODY_REF_DIRECT_ACCESS"
    ]


def test_skill_checker_rejects_current_step_output_reference() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": '{{output_value("show_message").message}}',
                    }
                ],
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["SKILL_OUTPUT_VALUE_FORWARD_REFERENCE"]


def test_skill_checker_rejects_forward_output_value_reference() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": '{{output_value("inspect").stdout}}',
                    },
                    {"shell": "inspect", "command": "printf ok"},
                ],
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["SKILL_OUTPUT_VALUE_FORWARD_REFERENCE"]


def test_skill_checker_rejects_unknown_next_target() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {
                        "notify": "show_message",
                        "message": "ok",
                        "next": "missing",
                    }
                ],
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["SKILL_STEP_NEXT_NOT_FOUND"]


def test_skill_checker_rejects_unsupported_helper() -> None:
    use_case = SkillCheckerUseCase(
        skill_runner=_FakeSkillRunner(
            {
                "name": "demo",
                "start": "show_message",
                "steps": [
                    {"shell": "inspect", "command": "printf ok"},
                    {
                        "notify": "show_message",
                        "message": '{{output("inspect").stdout}}',
                    },
                ],
            }
        )
    )
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == [
        "SKILL_OUTPUT_VALUE_UNSUPPORTED_HELPER"
    ]


def test_skill_checker_rejects_non_object_payload() -> None:
    use_case = SkillCheckerUseCase(skill_runner=_FakeSkillRunner(["bad"]))
    result = use_case.execute("demo", skill_source="internal")

    assert result.status == SkillCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["SKILL_FORMAT_INVALID"]
