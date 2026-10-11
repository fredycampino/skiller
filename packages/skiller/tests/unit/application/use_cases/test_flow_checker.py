from pathlib import Path

import pytest

from skiller.application.use_cases.flow.flow_check_model import FlowCheckStatus
from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper

pytestmark = pytest.mark.unit


class _FakeFlowPort:
    def __init__(self, raw_flow: object) -> None:
        self.raw_flow = raw_flow
        self.calls: list[Path] = []
        self.mapper = FlowYamlMapper()

    def get_yaml_flow(self, flow_path: Path):
        self.calls.append(flow_path)
        return self.mapper.to_flow(self.raw_flow)


def test_flow_checker_accepts_valid_flow_and_uses_flow_port() -> None:
    port = _FakeFlowPort(
        {
            "name": "diagnostics",
            "start": "inspect_shell",
            "steps": [
                {
                    "shell": "inspect_shell",
                    "command": 'python3 -c "print(42)"',
                    "next": "summarize_output",
                },
                {
                    "notify": "summarize_output",
                    "message": '{{output_value("inspect_shell").stderr}}',
                },
            ],
        }
    )

    flow_path = Path("/flows/diagnostics.yaml")
    result = FlowCheckerUseCase(flow_port=port).execute(flow_path)

    assert port.calls == [flow_path]
    assert result.status == FlowCheckStatus.VALID
    assert result.errors == []


def test_flow_checker_returns_shape_errors_without_collecting_steps() -> None:
    result = FlowCheckerUseCase(flow_port=_FakeFlowPort(["bad"])).execute(Path("/flows/demo.yaml"))

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_FORMAT_INVALID"]


@pytest.mark.parametrize(
    "config",
    [None, {}, {"file": ""}, {"file": 1}, {"file": "{{env.PROFILE}}"}, {"file": "x", "extra": 1}],
)
def test_flow_checker_rejects_invalid_agent_config(config) -> None:
    port = _FakeFlowPort(
        {
            "name": "config-test",
            "start": "a",
            "steps": [{"agent": "a", "system": "Review", "task": "Review", "config": config}],
        }
    )
    result = FlowCheckerUseCase(port).execute(Path("/flows/a.yaml"))
    assert any(error.code == "FLOW_AGENT_CONFIG_INVALID" for error in result.errors)


def test_flow_checker_accepts_env_reference_without_reading_environment() -> None:
    port = _FakeFlowPort(
        {
            "name": "config-test",
            "start": "a",
            "steps": [
                {
                    "agent": "a",
                    "system": "Review",
                    "task": "Review",
                    "config": {"file": "${UNCONFIGURED_PROFILE_DIR}/reviewer.json"},
                }
            ],
        }
    )
    assert FlowCheckerUseCase(port).execute(Path("/flows/a.yaml")).status == FlowCheckStatus.VALID


@pytest.mark.parametrize(
    "system",
    [
        {"file": "${}"},
        {"file": "{{env.PROMPT}}"},
        {"file": ""},
        {"file": 1},
        {"file": "x", "extra": 1},
    ],
)
def test_flow_checker_rejects_invalid_system_reference(system) -> None:
    port = _FakeFlowPort(
        {
            "name": "system-test",
            "start": "a",
            "steps": [{"agent": "a", "system": system, "task": "Review"}],
        }
    )
    result = FlowCheckerUseCase(port).execute(Path("/flows/a.yaml"))
    assert any(error.code == "FLOW_AGENT_SYSTEM_INVALID" for error in result.errors)


def test_flow_checker_accepts_external_system_reference_without_environment() -> None:
    port = _FakeFlowPort(
        {
            "name": "system-test",
            "start": "a",
            "steps": [
                {
                    "agent": "a",
                    "system": {"file": "${UNSET_PROMPT_DIR}/prompt.md"},
                    "task": "Review",
                }
            ],
        }
    )
    assert FlowCheckerUseCase(port).execute(Path("/flows/a.yaml")).status == FlowCheckStatus.VALID


@pytest.mark.parametrize(
    "instructions", [None, "response-style", [""], [1], ["${}"], ["{{env.INSTRUCTION_FILE}}"]]
)
def test_flow_checker_rejects_invalid_instruction_references(instructions) -> None:
    port = _FakeFlowPort(
        {
            "name": "instructions-test",
            "start": "a",
            "steps": [
                {"agent": "a", "system": "Review", "task": "Review", "instructions": instructions}
            ],
        }
    )
    result = FlowCheckerUseCase(port).execute(Path("/flows/a.yaml"))
    assert any(error.code == "FLOW_AGENT_INSTRUCTIONS_INVALID" for error in result.errors)


def test_flow_checker_accepts_instruction_paths_without_environment() -> None:
    port = _FakeFlowPort(
        {
            "name": "instructions-test",
            "start": "a",
            "steps": [
                {
                    "agent": "a",
                    "system": "Review",
                    "task": "Review",
                    "instructions": ["response-style", "rules.md", "${UNSET_DIR}/${UNSET_NAME}.md"],
                }
            ],
        }
    )
    assert FlowCheckerUseCase(port).execute(Path("/flows/a.yaml")).status == FlowCheckStatus.VALID
