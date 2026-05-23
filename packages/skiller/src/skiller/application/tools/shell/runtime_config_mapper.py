from collections.abc import Mapping

from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.tool.tool_contract import ToolDefinition


class ShellToolRuntimeConfigMapper:
    def from_mapping(
        self,
        *,
        raw: Mapping[str, object],
        definition: type[ToolDefinition],
    ) -> ShellToolRuntimeConfig:
        supported_fields = {
            "workspace",
            "allowlist_enabled",
            "allow_env_prefix",
            "allowed_commands",
        }
        unknown_fields = sorted(set(raw) - supported_fields)
        if unknown_fields:
            unknown_values = ", ".join(unknown_fields)
            raise ValueError(f"Tool 'shell' has unsupported config fields: {unknown_values}")

        workspace = _string_value(raw, "workspace", "")
        allowlist_enabled = _bool_value(raw, "allowlist_enabled", False)
        allow_env_prefix = _bool_value(raw, "allow_env_prefix", True)
        allowed_commands = _string_list_value(raw, "allowed_commands")

        return ShellToolRuntimeConfig(
            definition=definition,
            workspace=workspace,
            allowlist_enabled=allowlist_enabled,
            allow_env_prefix=allow_env_prefix,
            allowed_commands=tuple(allowed_commands),
        )


def _bool_value(raw: Mapping[str, object], name: str, default: bool) -> bool:
    value = raw.get(name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise ValueError(f"Tool 'shell' field '{name}' must be a boolean")


def _string_value(raw: Mapping[str, object], name: str, default: str) -> str:
    value = raw.get(name)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    raise ValueError(f"Tool 'shell' field '{name}' must be a string")


def _string_list_value(raw: Mapping[str, object], name: str) -> list[str]:
    value = raw.get(name)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Tool 'shell' field '{name}' must be a list of strings")

    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"Tool 'shell' field '{name}' must be a list of non-empty strings"
            )
        items.append(item.strip())
    return items
