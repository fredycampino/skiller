import pytest

from skiller.domain.flow.flow_load_error import FlowLoadError
from skiller.infrastructure.flow.filesystem_flow_port import FilesystemFlowPort
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper

pytestmark = pytest.mark.unit


def test_filesystem_flow_port_loads_file_flow(tmp_path) -> None:
    flow_path = tmp_path / "flow.yaml"
    flow_path.write_text(
        """
name: demo
start: intro
steps:
  - notify: intro
    message: Hello
""".strip(),
        encoding="utf-8",
    )

    flow = FilesystemFlowPort(
        flows_dir=str(tmp_path),
        mapper=FlowYamlMapper(),
    ).get_yaml_flow(source="file", ref=str(flow_path))

    assert flow.name == "demo"
    assert flow.start == "intro"
    assert flow.steps[0].step_type == "notify"
    assert flow.steps[0].step_id == "intro"


def test_filesystem_flow_port_translates_invalid_yaml(tmp_path) -> None:
    flow_path = tmp_path / "flow.yaml"
    flow_path.write_text("name: [invalid", encoding="utf-8")

    with pytest.raises(FlowLoadError, match="Invalid flow YAML") as exc_info:
        FilesystemFlowPort(
            flows_dir=str(tmp_path),
            mapper=FlowYamlMapper(),
        ).get_yaml_flow(source="file", ref=str(flow_path))

    assert exc_info.value.__cause__ is not None


def test_filesystem_flow_port_loads_internal_nested_flow(tmp_path) -> None:
    flow_dir = tmp_path / "mono"
    flow_dir.mkdir()
    (flow_dir / "agent.yaml").write_text(
        """
name: mono
start: ask
steps:
  - wait_input: ask
    prompt: Ask
""".strip(),
        encoding="utf-8",
    )

    flow = FilesystemFlowPort(
        flows_dir=str(tmp_path),
        mapper=FlowYamlMapper(),
    ).get_yaml_flow(source="internal", ref="mono")

    assert flow.name == "mono"
    assert flow.steps[0].step_type == "wait_input"


def test_filesystem_flow_port_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="Unsupported flow source"):
        FilesystemFlowPort(
            flows_dir=".",
            mapper=FlowYamlMapper(),
        ).get_yaml_flow(source="remote", ref="demo")
