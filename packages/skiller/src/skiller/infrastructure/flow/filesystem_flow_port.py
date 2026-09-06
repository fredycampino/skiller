from pathlib import Path

from skiller.domain.flow.flow_port import FlowPort
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition
from skiller.infrastructure.flow.flow_file_loader import load_existing_flow
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper


class FilesystemFlowPort(FlowPort):
    def __init__(
        self,
        *,
        mapper: FlowYamlMapper,
    ) -> None:
        self.mapper = mapper

    def get_yaml_flow(self, flow_path: Path) -> FlowRawDefinition:
        suffix = flow_path.suffix.lower()
        if suffix not in {".yaml", ".yml"}:
            raise ValueError(f"Unsupported flow file extension: {flow_path}")
        raw = load_existing_flow(
            yaml_path=flow_path,
            json_path=Path("__missing__.json"),
        )
        return self.mapper.to_flow(raw)
