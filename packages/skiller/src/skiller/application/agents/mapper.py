from typing import Any

from skiller.application.use_cases.agent.get_agent_stats import (
    GetAgentStatsResult,
    GetAgentStatsStatus,
)
from skiller.application.use_cases.agent.get_agent_tools import (
    GetAgentToolsResult,
    GetAgentToolsStatus,
)
from skiller.application.use_cases.agent.interrupt_agent import (
    InterruptAgentResult,
    InterruptAgentStatus,
)
from skiller.application.use_cases.agent.list_agent_context import (
    ListAgentContextResult,
    ListAgentContextStatus,
)
from skiller.application.use_cases.agent.list_agent_models import (
    ListAgentModelsResult,
    ListAgentModelsStatus,
)
from skiller.application.use_cases.agent.select_agent_model import (
    SelectAgentModelResult,
    SelectAgentModelStatus,
)
from skiller.domain.agent.context.stats_model import AgentStats


class AgentServiceMapper:
    def to_interrupt_input(self, run_id: str) -> str:
        return run_id.strip()

    def to_interrupt_dict(self, result: InterruptAgentResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "status": result.status.value,
            "enqueued": result.status == InterruptAgentStatus.ENQUEUED,
        }
        if result.item is not None:
            payload["item"] = result.item.to_dict()
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_stats_input(self, run_id: str, agent_id: str) -> tuple[str, str]:
        return run_id.strip(), agent_id.strip()

    def to_stats_dict(self, result: GetAgentStatsResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "agent_id": result.agent_id,
            "status": result.status.value,
            "ok": result.status == GetAgentStatsStatus.OK,
        }
        if result.stats is not None:
            payload["context_id"] = result.stats.context_id
            payload["context"] = self._context_to_dict(result.stats)
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_context_input(self, run_id: str, agent_id: str) -> tuple[str, str]:
        return run_id.strip(), agent_id.strip()

    def to_context_dict(self, result: ListAgentContextResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "agent_id": result.agent_id,
            "status": result.status.value,
            "ok": result.status == ListAgentContextStatus.OK,
        }
        if result.context_id is not None:
            payload["context_id"] = result.context_id
        if result.window is not None:
            payload["request_context"] = {
                "mode": result.window.mode,
                "entries": result.window.entries,
                "start_sequence": result.window.start_sequence,
                "end_sequence": result.window.end_sequence,
                "limit_tokens": result.window.limit_tokens,
                "estimated_tokens": result.window.estimated_tokens,
                "payload_bytes": result.window.payload_bytes,
                "keep_last": result.window.keep_last,
            }
        if result.entries:
            payload["entries"] = [
                {
                    "sequence": entry.sequence,
                    "role": entry.role,
                    "type": entry.type,
                    "delta_tokens": entry.delta_tokens,
                    "delta_compact_tokens": entry.delta_compact_tokens,
                    "payload_bytes": entry.payload_bytes,
                    "usage": entry.usage,
                    "prunable": entry.prunable,
                    "window_start_sequence": entry.window_start_sequence,
                    "window_base": entry.window_base,
                }
                for entry in result.entries
            ]
        else:
            payload["entries"] = []
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_models_input(self, run_id: str) -> str:
        return run_id.strip()

    def to_tools_input(self, run_id: str) -> str:
        return run_id.strip()

    def to_select_model_input(
        self,
        run_id: str,
        provider: str,
        model: str,
    ) -> tuple[str, str, str]:
        return run_id.strip(), provider.strip(), model.strip()

    def to_models_dict(self, result: ListAgentModelsResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "status": result.status.value,
            "ok": result.status == ListAgentModelsStatus.OK,
        }
        if result.providers:
            payload["providers"] = [
                {
                    "name": provider.name,
                    "source": provider.source.value,
                    "models": [
                        {
                            "name": model.name,
                            "active": model.active,
                        }
                        for model in provider.models
                    ],
                }
                for provider in result.providers
            ]
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_tools_dict(self, result: GetAgentToolsResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "agent_id": result.agent_id,
            "status": result.status.value,
            "ok": result.status == GetAgentToolsStatus.OK,
            "source": result.source,
            "ref": result.ref,
            "config_path": str(result.config_path) if result.config_path is not None else None,
            "cwd": str(result.cwd) if result.cwd is not None else None,
        }
        if result.tools is not None:
            payload["tools"] = {
                "shell": {
                    "enabled": result.tools.shell.enabled,
                    "allowed_paths": [
                        str(path) for path in result.tools.shell.allowed_paths
                    ],
                    "allowlist_enabled": result.tools.shell.allowlist_enabled,
                    "allow_env_prefix": result.tools.shell.allow_env_prefix,
                    "allowed_commands": list(result.tools.shell.allowed_commands),
                },
                "files": {
                    "enabled": result.tools.files.enabled,
                    "read": [str(path) for path in result.tools.files.read],
                    "write": [str(path) for path in result.tools.files.write],
                    "all": [str(path) for path in result.tools.files.all],
                },
            }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def to_select_model_dict(self, result: SelectAgentModelResult) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": result.run_id,
            "provider": result.provider,
            "model": result.model,
            "status": result.status.value,
            "ok": result.status == SelectAgentModelStatus.OK,
        }
        if result.error is not None:
            payload["error"] = result.error
        return payload

    def _context_to_dict(self, stats: AgentStats) -> dict[str, Any]:
        return {
            "entries": stats.context.entries,
            "estimated_tokens": stats.context.estimated_tokens,
            "window": {
                "start_sequence": stats.context.window.start_sequence,
                "end_sequence": stats.context.window.end_sequence,
                "current_tokens": stats.context.window.current_tokens,
                "limit_tokens": stats.context.window.limit_tokens,
                "capacity_tokens": stats.context.window.capacity_tokens,
            },
        }
