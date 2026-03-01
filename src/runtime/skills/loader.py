import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_TEMPLATE_RE = re.compile(r"{{\s*([^}]+?)\s*}}")


class SkillRunner:
    def __init__(self, skills_dir: str = "skills") -> None:
        self.skills_dir = Path(skills_dir)

    def load_skill(self, skill_name: str) -> dict[str, Any]:
        yaml_path = self.skills_dir / f"{skill_name}.yaml"
        json_path = self.skills_dir / f"{skill_name}.json"

        if yaml_path.exists():
            return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if json_path.exists():
            return json.loads(json_path.read_text(encoding="utf-8"))

        raise FileNotFoundError(f"Skill not found: {skill_name}")

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

    def _render_string(self, template: str, context: dict[str, Any]) -> str:
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
