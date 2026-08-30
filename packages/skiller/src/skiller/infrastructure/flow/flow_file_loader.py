import json
from pathlib import Path

import yaml

from skiller.domain.flow.flow_load_error import FlowLoadError, FlowNotFoundError


def load_existing_flow(*, yaml_path: Path, json_path: Path) -> object:
    if yaml_path.exists():
        return _load_yaml(yaml_path)
    if json_path.exists():
        return _load_json(json_path)

    raise FlowNotFoundError(f"Flow not found: yaml={yaml_path} json={json_path}")


def _load_yaml(path: Path) -> object:
    try:
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise FlowLoadError(f"Invalid flow YAML '{path}': {exc}") from exc
    except OSError as exc:
        raise FlowLoadError(f"Cannot read flow file '{path}': {exc}") from exc


def _load_json(path: Path) -> object:
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise FlowLoadError(f"Invalid flow JSON '{path}': {exc}") from exc
    except OSError as exc:
        raise FlowLoadError(f"Cannot read flow file '{path}': {exc}") from exc
