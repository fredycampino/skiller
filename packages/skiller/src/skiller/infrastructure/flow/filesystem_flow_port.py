import json
from pathlib import Path

import yaml

from skiller.domain.flow.flow_port import FlowPort
from skiller.domain.flow.flow_raw_definition import FlowRawDefinition
from skiller.infrastructure.flow.flow_yaml_mapper import FlowYamlMapper


class FilesystemFlowPort(FlowPort):
    def __init__(
        self,
        *,
        flows_dir: str,
        mapper: FlowYamlMapper,
    ) -> None:
        self.flows_dir = Path(flows_dir)
        self.mapper = mapper

    def get_yaml_flow(self, *, source: str, ref: str) -> FlowRawDefinition:
        raw = self._load_raw(source=source, ref=ref)
        return self.mapper.to_flow(raw)

    def _load_raw(self, *, source: str, ref: str) -> object:
        if source == "internal":
            yaml_path, json_path = _resolve_internal_flow_paths(
                catalog_dir=self.flows_dir,
                ref=ref,
            )
            return _load_existing_flow(yaml_path=yaml_path, json_path=json_path)

        if source == "file":
            path = Path(ref)
            suffix = path.suffix.lower()
            if suffix not in {".yaml", ".yml", ".json"}:
                raise ValueError(f"Unsupported flow file extension: {path}")
            yaml_path = path if suffix in {".yaml", ".yml"} else Path("__missing__.yaml")
            json_path = path if suffix == ".json" else Path("__missing__.json")
            return _load_existing_flow(yaml_path=yaml_path, json_path=json_path)

        raise ValueError(f"Unsupported flow source: {source}")


def _load_existing_flow(*, yaml_path: Path, json_path: Path) -> object:
    if yaml_path.exists():
        return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))

    raise FileNotFoundError(f"Flow not found: yaml={yaml_path} json={json_path}")


def _resolve_internal_flow_paths(*, catalog_dir: Path, ref: str) -> tuple[Path, Path]:
    normalized_ref = ref.strip().strip("/")
    nested_yaml_path = catalog_dir / normalized_ref / "agent.yaml"
    nested_json_path = catalog_dir / normalized_ref / "agent.json"
    if nested_yaml_path.exists() or nested_json_path.exists():
        return nested_yaml_path, nested_json_path

    flat_yaml_path = catalog_dir / f"{normalized_ref}.yaml"
    flat_json_path = catalog_dir / f"{normalized_ref}.json"
    return flat_yaml_path, flat_json_path
