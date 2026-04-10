from dataclasses import dataclass
from enum import Enum
from typing import Any

from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.skill_runner_port import SkillRunnerPort
from skiller.application.use_cases.render_current_step import CurrentStep, StepType
from skiller.domain.mcp_config_model import RenderedMcpConfig


class RenderMcpConfigStatus(str, Enum):
    RENDERED = "RENDERED"
    INVALID_CONFIG = "INVALID_CONFIG"


@dataclass(frozen=True)
class RenderMcpConfigResult:
    status: RenderMcpConfigStatus
    mcp_config: RenderedMcpConfig | None = None
    error: str | None = None


class RenderMcpConfigUseCase:
    def __init__(self, store: RunStorePort, skill_runner: SkillRunnerPort) -> None:
        self.store = store
        self.skill_runner = skill_runner

    def execute(self, next_step: CurrentStep) -> RenderMcpConfigResult:
        if next_step.step_type != StepType.MCP:
            return self._invalid(f"Step '{next_step.step_id}' is not an mcp step")

        server_name = str(next_step.step.get("server", "")).strip()
        if not server_name:
            return self._invalid(
                f"Step '{next_step.step_id}' requires mcp server name in field 'server'"
            )

        run = self.store.get_run(next_step.run_id)
        if run is None:
            return self._invalid(f"Run '{next_step.run_id}' not found")

        skill = run.skill_snapshot
        if not isinstance(skill, dict):
            return self._invalid(f"Invalid skill format for '{run.skill_ref}'. Expected an object.")

        raw_declared = skill.get("mcp", [])
        if not isinstance(raw_declared, list):
            return self._invalid(
                f"Invalid MCP configuration for skill '{run.skill_ref}'. Expected a list."
            )

        raw_config = self._find_server_config(raw_declared, server_name)
        if raw_config is None:
            return self._invalid(
                f"MCP server '{server_name}' not declared in skill '{run.skill_ref}'"
            )

        rendered = self.skill_runner.render_step(raw_config, next_step.context.to_dict())
        if not isinstance(rendered, dict):
            return self._invalid(f"Invalid rendered MCP configuration for server '{server_name}'")

        unresolved_path = self._find_unresolved_template(rendered)
        if unresolved_path is not None:
            return self._invalid(
                "Unresolved template in MCP config for "
                f"server '{server_name}' at '{unresolved_path}'"
            )

        try:
            mcp_config = self._build_config(server_name, rendered)
        except ValueError as exc:
            return self._invalid(str(exc))

        return RenderMcpConfigResult(
            status=RenderMcpConfigStatus.RENDERED,
            mcp_config=mcp_config,
        )

    def _find_server_config(self, declared: list[Any], server_name: str) -> dict[str, Any] | None:
        for item in declared:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if name == server_name:
                    return item
                continue

            name = str(item).strip()
            if name == server_name:
                return {"name": name}

        return None

    def _build_config(self, server_name: str, rendered: dict[str, Any]) -> RenderedMcpConfig:
        transport = str(rendered.get("transport", "")).strip()
        url = str(rendered.get("url", "")).strip() or None
        command = str(rendered.get("command", "")).strip() or None

        if not transport:
            raise ValueError(f"MCP server '{server_name}' requires explicit transport")

        raw_args = rendered.get("args", [])
        if raw_args in (None, ""):
            args: list[str] = []
        elif isinstance(raw_args, list):
            args = [str(item) for item in raw_args]
        else:
            raise ValueError(f"Invalid MCP args for server '{server_name}'. Expected a list.")

        raw_env = rendered.get("env", {})
        if raw_env in (None, ""):
            env: dict[str, str] = {}
        elif isinstance(raw_env, dict):
            env = {str(key): str(value) for key, value in raw_env.items()}
        else:
            raise ValueError(f"Invalid MCP env for server '{server_name}'. Expected an object.")

        raw_headers = rendered.get("headers", {})
        if raw_headers in (None, ""):
            headers: dict[str, str] = {}
        elif isinstance(raw_headers, dict):
            headers = {str(key): str(value) for key, value in raw_headers.items()}
        else:
            raise ValueError(f"Invalid MCP headers for server '{server_name}'. Expected an object.")

        cwd = str(rendered.get("cwd", "")).strip() or None

        if transport == "stdio" and not command:
            raise ValueError(f"MCP server '{server_name}' requires command for stdio transport")

        if transport in {"http", "streamable-http"} and not url:
            raise ValueError(f"MCP server '{server_name}' requires url for http transport")

        if transport not in {"stdio", "http", "streamable-http"}:
            raise ValueError(f"Unsupported MCP transport '{transport}' for server '{server_name}'")

        return RenderedMcpConfig(
            name=server_name,
            transport=transport,
            url=url,
            command=command,
            args=args,
            cwd=cwd,
            env=env,
            headers=headers,
        )

    def _find_unresolved_template(self, value: Any, path: str = "mcp") -> str | None:
        if isinstance(value, dict):
            for key, item in value.items():
                found = self._find_unresolved_template(item, f"{path}.{key}")
                if found is not None:
                    return found
            return None

        if isinstance(value, list):
            for index, item in enumerate(value):
                found = self._find_unresolved_template(item, f"{path}[{index}]")
                if found is not None:
                    return found
            return None

        if isinstance(value, str) and "{{" in value and "}}" in value:
            return path

        return None

    def _invalid(self, error: str) -> RenderMcpConfigResult:
        return RenderMcpConfigResult(
            status=RenderMcpConfigStatus.INVALID_CONFIG,
            error=error,
        )
