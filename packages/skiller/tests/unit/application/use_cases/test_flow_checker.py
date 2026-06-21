import pytest

from skiller.application.use_cases.flow.flow_check_model import FlowCheckStatus
from skiller.application.use_cases.flow.flow_checker import FlowCheckerUseCase
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper

pytestmark = pytest.mark.unit


class _FakeFlowPort:
    def __init__(self, raw_flow: object) -> None:
        self.raw_flow = raw_flow
        self.calls: list[tuple[str, str]] = []
        self.mapper = FlowYamlMapper()

    def get_yaml_flow(self, *, source: str, ref: str):
        self.calls.append((source, ref))
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

    result = FlowCheckerUseCase(flow_port=port).execute(
        "diagnostics",
        flow_source="internal",
    )

    assert port.calls == [("internal", "diagnostics")]
    assert result.status == FlowCheckStatus.VALID
    assert result.errors == []


def test_flow_checker_returns_shape_errors_without_collecting_steps() -> None:
    result = FlowCheckerUseCase(flow_port=_FakeFlowPort(["bad"])).execute(
        "demo",
        flow_source="internal",
    )

    assert result.status == FlowCheckStatus.INVALID
    assert [item.code for item in result.errors] == ["FLOW_FORMAT_INVALID"]
