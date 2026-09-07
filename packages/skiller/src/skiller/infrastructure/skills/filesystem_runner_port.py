import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from skiller.domain.flow.flow_run_reference import FlowRunReference
from skiller.domain.step.runner_port import RunnerPort
from skiller.domain.step.template_resolution_error import UnresolvedTemplateError
from skiller.infrastructure.flow.flow_file_loader import load_existing_flow

_TEMPLATE_RE = re.compile(r"{{\s*([^}]+?)\s*}}")
_FULL_TEMPLATE_RE = re.compile(r"^\s*{{\s*([^}]+?)\s*}}\s*$")
_OUTPUT_VALUE_RE = re.compile(
    r"""^output_value\(\s*(["'])([^"']+)\1\s*\)((?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)$"""
)
_UNSUPPORTED_HELPER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\(")


class FilesystemRunnerPort(RunnerPort):
    def load(self, flow_path: Path) -> dict[str, Any]:
        suffix = flow_path.suffix.lower()
        if suffix not in {".yaml", ".yml"}:
            raise ValueError(f"Unsupported flow file extension: {flow_path}")
        return load_existing_flow(
            yaml_path=flow_path,
            json_path=Path("__missing__.json"),
        )

    def read_file(
        self,
        flow_path: Path,
        file_ref: str,
    ) -> str:
        file_path = self.resolve_file_path(flow_path, file_ref)
        if not file_path.exists():
            raise FileNotFoundError(f"Flow file not found: {file_ref}")
        return file_path.read_text(encoding="utf-8")

    def resolve_file_path(
        self,
        flow_path: Path,
        file_ref: str,
    ) -> Path:
        base_path = self.resolve_flow_dir(flow_path)
        return _resolve_file_path(
            base_path=base_path,
            file_ref=file_ref,
        )

    def resolve_flow_dir(self, flow_path: Path) -> Path:
        return flow_path.parent

    def render(
        self,
        step: dict[str, Any],
        context: dict[str, Any],
        *,
        flow: FlowRunReference,
    ) -> dict[str, Any]:
        rendered = deepcopy(step)
        render_context = dict(context)
        flow_context = render_context.get("flow", {})
        if not isinstance(flow_context, dict):
            flow_context = {}

        flow_context = dict(flow_context)
        flow_context["dir"] = str(self.resolve_flow_dir(flow.flow_path).resolve())
        flow_context["run_id"] = flow.id
        render_context["flow"] = flow_context
        render_context["runtime"] = {
            "python": sys.executable,
            "venv": str(Path(sys.prefix).resolve()),
        }
        render_context.setdefault("env", dict(os.environ))
        return self._render_value(rendered, render_context)

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
                "FLOW_OUTPUT_VALUE_DIRECT_OUTPUT_ACCESS: direct output.value "
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
                "FLOW_OUTPUT_VALUE_INVALID_SYNTAX: invalid output_value expression "
                f"(expression={expression})"
            )

        if _UNSUPPORTED_HELPER_RE.match(expression):
            raise ValueError(
                "FLOW_OUTPUT_VALUE_UNSUPPORTED_HELPER: unsupported template helper "
                f"(expression={expression})"
            )

        value = self._resolve_path(context, expression)
        if value is None:
            if expression.startswith("inputs."):
                return True, ""
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
            raise UnresolvedTemplateError(
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


def _resolve_file_path(*, base_path: Path, file_ref: str) -> Path:
    if not isinstance(file_ref, str) or not file_ref.strip():
        raise ValueError("Flow file reference must be a non-empty string")

    relative_path = Path(file_ref)
    if relative_path.is_absolute():
        raise ValueError(f"Flow file reference must be relative: {file_ref}")

    resolved_base = base_path.resolve()
    resolved_path = (resolved_base / relative_path).resolve()
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"Flow file reference escapes flow directory: {file_ref}") from exc
    return resolved_path
