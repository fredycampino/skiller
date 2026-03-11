import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_TEMPLATE_RE = re.compile(r"{{\s*([^}]+?)\s*}}")
_FULL_TEMPLATE_RE = re.compile(r"^\s*{{\s*([^}]+?)\s*}}\s*$")


class FilesystemSkillRunner:
    def __init__(self, skills_dir: str = "skills") -> None:
        self.skills_dir = Path(skills_dir)

    def load_skill(self, skill_source: str, skill_ref: str) -> dict[str, Any]:
        if skill_source == "internal":
            yaml_path = self.skills_dir / f"{skill_ref}.yaml"
            json_path = self.skills_dir / f"{skill_ref}.json"
        elif skill_source == "file":
            path = Path(skill_ref)
            suffix = path.suffix.lower()
            if suffix not in {".yaml", ".yml", ".json"}:
                raise ValueError(f"Unsupported skill file extension: {path}")
            yaml_path = path if suffix in {".yaml", ".yml"} else Path("__missing__.yaml")
            json_path = path if suffix == ".json" else Path("__missing__.json")
        else:
            raise ValueError(f"Unsupported skill source: {skill_source}")

        if yaml_path.exists():
            return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if json_path.exists():
            return json.loads(json_path.read_text(encoding="utf-8"))

        raise FileNotFoundError(f"Skill not found: source={skill_source} ref={skill_ref}")

    def render_step(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        rendered = deepcopy(step)
        return self._render_value(rendered, context)

    def _render_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {k: self._render_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_value(v, context) for v in value]
        if isinstance(value, str):
            return self._render_string(value, context)
        return value

    def _render_string(self, template: str, context: dict[str, Any]) -> Any:
        full_match = _FULL_TEMPLATE_RE.match(template)
        if full_match is not None:
            value = self._resolve_path(context, full_match.group(1).strip())
            if value is not None:
                return value

        def replace(match: re.Match[str]) -> str:
            path = match.group(1).strip()
            value = self._resolve_path(context, path)
            if value is None:
                return match.group(0)
            return str(value)

        return _TEMPLATE_RE.sub(replace, template)

    def _resolve_path(self, context: dict[str, Any], path: str) -> Any:
        current: Any = context
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
