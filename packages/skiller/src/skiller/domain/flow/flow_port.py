from pathlib import Path
from typing import Protocol

from skiller.domain.flow.flow_raw_definition import FlowRawDefinition


class FlowPort(Protocol):
    def get_yaml_flow(self, flow_path: Path) -> FlowRawDefinition: ...
