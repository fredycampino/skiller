import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_TEMPLATE_RE = re.compile(r"{{\s*([^}]+?)\s*}}")
_FULL_TEMPLATE_RE = re.compile(r"^\s*{{\s*([^}]+?)\s*}}\s*$")
_OUTPUT_VALUE_RE = re.compile(
    r"""^output_value\(\s*(["'])([^"']+)\1\s*\)((?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)$"""
)
_UNSUPPORTED_HELPER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\(")


class FilesystemSkillRunner:
    def __init__(
        self,
        skills_dir: str | None = None,
    ) -> None:
        self.skills_dir = (
            Path(skills_dir) if skills_dir is not None else _find_default_internal_agents_dir()
        )

    def load_skill(self, skill_source: str, skill_ref: str) -> dict[str, Any]:
        if skill_source == "internal":
            yaml_path, json_path = _resolve_internal_skill_paths(
                catalog_dir=self.skills_dir,
                skill_ref=skill_ref,
            )
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

    def read_skill_file(
        self,
        skill_source: str,
        skill_ref: str,
        file_ref: str,
    ) -> str:
        base_path = self._resolve_skill_base_path(
            skill_source=skill_source,
            skill_ref=skill_ref,
        )
        file_path = _resolve_skill_resource_path(
            base_path=base_path,
            file_ref=file_ref,
        )
        if not file_path.exists():
            raise FileNotFoundError(f"Skill file not found: {file_ref}")
        return file_path.read_text(encoding="utf-8")

    def render_step(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        rendered = deepcopy(step)
        render_context = dict(context)
        render_context.setdefault("env", dict(os.environ))
        return self._render_value(rendered, render_context)

    def _resolve_skill_base_path(self, *, skill_source: str, skill_ref: str) -> Path:
        if skill_source == "internal":
            yaml_path, json_path = _resolve_internal_skill_paths(
                catalog_dir=self.skills_dir,
                skill_ref=skill_ref,
            )
            if yaml_path.exists():
                return yaml_path.parent
            if json_path.exists():
                return json_path.parent
            raise FileNotFoundError(f"Skill not found: source={skill_source} ref={skill_ref}")

        if skill_source == "file":
            skill_path = Path(skill_ref)
            if not skill_path.exists():
                raise FileNotFoundError(f"Skill not found: source={skill_source} ref={skill_ref}")
            return skill_path.parent

        raise ValueError(f"Unsupported skill source: {skill_source}")

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
            resolved, value = self._resolve_expression(context, full_match.group(1).strip())
            if resolved:
                return value

        def replace(match: re.Match[str]) -> str:
            resolved, value = self._resolve_expression(context, match.group(1).strip())
            if not resolved:
                return match.group(0)
            return str(value)

        return _TEMPLATE_RE.sub(replace, template)

    def _resolve_expression(self, context: dict[str, Any], expression: str) -> tuple[bool, Any]:
        if ".output.value" in expression and expression.startswith("step_executions."):
            raise ValueError(
                "SKILL_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS: direct output.value "
                "access is not allowed "
                f"(expression={expression})"
            )
        output_value_match = _OUTPUT_VALUE_RE.match(expression)
        if output_value_match is not None:
            step_id = output_value_match.group(2).strip()
            suffix = output_value_match.group(3).strip()
            value = self._resolve_output_value(context, step_id=step_id, suffix=suffix)
            return True, value
        if expression.startswith("output_value("):
            raise ValueError(
                "SKILL_OUTPUT_VALUE_INVALID_SYNTAX: invalid output_value expression "
                f"(expression={expression})"
            )

        if _UNSUPPORTED_HELPER_RE.match(expression):
            raise ValueError(
                "SKILL_OUTPUT_VALUE_UNSUPPORTED_HELPER: unsupported template helper "
                f"(expression={expression})"
            )

        value = self._resolve_path(context, expression)
        if value is None:
            return False, None
        return True, value

    def _resolve_output_value(
        self,
        context: dict[str, Any],
        *,
        step_id: str,
        suffix: str,
    ) -> Any:
        step_executions = context.get("step_executions")
        if not isinstance(step_executions, dict) or step_id not in step_executions:
            raise ValueError(
                "OUTPUT_VALUE_STEP_NOT_EXECUTED: referenced step has no execution yet "
                f"(step_id={step_id})"
            )

        execution = step_executions[step_id]
        if not isinstance(execution, dict):
            raise ValueError(
                "OUTPUT_VALUE_OUTPUT_MISSING: referenced step has no usable output "
                f"(step_id={step_id})"
            )

        output = execution.get("output")
        if not isinstance(output, dict):
            raise ValueError(
                "OUTPUT_VALUE_OUTPUT_MISSING: referenced step has no usable output "
                f"(step_id={step_id})"
            )

        value = self._load_effective_output_value(output=output, step_id=step_id)
        if not suffix:
            return value

        path = suffix.removeprefix(".")
        return self._resolve_field_path(value=value, step_id=step_id, path=path)

    def _load_effective_output_value(self, *, output: dict[str, Any], step_id: str) -> Any:
        if "value" not in output:
            raise ValueError(
                "OUTPUT_VALUE_OUTPUT_MISSING: referenced step has no usable output "
                f"(step_id={step_id})"
            )
        return output.get("value")

    def _resolve_field_path(self, *, value: Any, step_id: str, path: str) -> Any:
        current = value
        for part in path.split("."):
            key = part.strip()
            if not key:
                raise ValueError(
                    "OUTPUT_VALUE_RENDER_ERROR: failed to resolve output_value "
                    f"(step_id={step_id}, path={path})"
                )
            if isinstance(current, dict):
                if key not in current:
                    raise ValueError(
                        "OUTPUT_VALUE_PATH_MISSING: requested field does not exist "
                        f"(step_id={step_id}, path={path})"
                    )
                current = current[key]
                continue
            raise ValueError(
                "OUTPUT_VALUE_UNSUPPORTED_ACCESS: cannot access nested field on scalar value "
                f"(step_id={step_id}, path={path})"
            )
        return current

    def _resolve_path(self, context: dict[str, Any], path: str) -> Any:
        current: Any = context
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current


def _find_default_internal_agents_dir() -> Path:
    module_path = Path(__file__).resolve()
    package_agents_dir = module_path.parents[2] / "agents"
    if package_agents_dir.is_dir():
        return package_agents_dir

    for parent in module_path.parents:
        repo_agents_dir = parent / "packages" / "skiller" / "agents"
        if repo_agents_dir.is_dir():
            return repo_agents_dir

    return Path("packages/skiller/agents")


def _resolve_internal_skill_paths(*, catalog_dir: Path, skill_ref: str) -> tuple[Path, Path]:
    normalized_ref = skill_ref.strip().strip("/")
    nested_yaml_path = catalog_dir / normalized_ref / "agent.yaml"
    nested_json_path = catalog_dir / normalized_ref / "agent.json"
    if nested_yaml_path.exists() or nested_json_path.exists():
        return nested_yaml_path, nested_json_path

    # Keep explicit custom test fixtures working while the runtime catalog
    # moves to agents/*/agent.yaml.
    flat_yaml_path = catalog_dir / f"{normalized_ref}.yaml"
    flat_json_path = catalog_dir / f"{normalized_ref}.json"
    return flat_yaml_path, flat_json_path


def _resolve_skill_resource_path(*, base_path: Path, file_ref: str) -> Path:
    if not isinstance(file_ref, str) or not file_ref.strip():
        raise ValueError("Skill file reference must be a non-empty string")

    relative_path = Path(file_ref)
    if relative_path.is_absolute():
        raise ValueError(f"Skill file reference must be relative: {file_ref}")

    resolved_base = base_path.resolve()
    resolved_path = (resolved_base / relative_path).resolve()
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"Skill file reference escapes skill directory: {file_ref}") from exc
    return resolved_path
