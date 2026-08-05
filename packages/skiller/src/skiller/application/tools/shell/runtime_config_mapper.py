import re
import sys
from collections.abc import Mapping
from pathlib import Path

from skiller.application.tools.shell.config import ShellToolRuntimeConfig
from skiller.domain.tool.tool_contract import ToolDefinition


class ShellToolRuntimeConfigMapper:
    def from_mapping(
        self,
        *,
        raw: Mapping[str, object],
        definition: type[ToolDefinition],
        base_path: Path,
    ) -> ShellToolRuntimeConfig:
        supported_fields = {
            "allowed_paths",
            "allowlist_enabled",
            "allow_env_prefix",
            "allowed_commands",
        }
        unknown_fields = sorted(set(raw) - supported_fields)
        if unknown_fields:
            unknown_values = ", ".join(unknown_fields)
            raise ValueError(f"Tool 'shell' has unsupported config fields: {unknown_values}")

        configured_paths = _path_list_value(raw, "allowed_paths", base_path=base_path)
        runtime_cwd = Path.cwd().resolve(strict=False)
        runtime_python = Path(sys.executable).resolve(strict=False)
        allowed_paths = [runtime_cwd, runtime_python]
        allowed_paths.extend(configured_paths)
        allowed_paths = list(dict.fromkeys(allowed_paths))
        allowlist_enabled = _bool_value(raw, "allowlist_enabled", False)
        allow_env_prefix = _bool_value(raw, "allow_env_prefix", True)
        allowed_commands = _string_list_value(raw, "allowed_commands")

        return ShellToolRuntimeConfig(
            definition=definition,
            allowed_paths=tuple(allowed_paths),
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


def _path_list_value(
    raw: Mapping[str, object],
    name: str,
    *,
    base_path: Path,
) -> tuple[Path, ...]:
    return tuple(
        _path_value(item, base_path=base_path)
        for item in _string_list_value(raw, name)
    )


def _path_value(raw: str, *, base_path: Path) -> Path:
    value = _resolve_path_template(raw, base_path=base_path)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_path / path
    return path.resolve(strict=False)


def _resolve_path_template(raw: str, *, base_path: Path) -> str:
    values = {
        "flow.dir": str(base_path.resolve(strict=False)),
        "runtime.cwd": str(Path.cwd().resolve(strict=False)),
        "runtime.python": str(Path(sys.executable).resolve(strict=False)),
        "runtime.venv": str(Path(sys.prefix).resolve(strict=False)),
    }

    value = raw.strip()
    for name, resolved in values.items():
        value = value.replace("{{" + name + "}}", resolved)

    if re.search(r"{{|}}", value):
        raise ValueError(f"Tool 'shell' has unsupported path template: {raw}")
    return value
