from collections.abc import Mapping
from pathlib import Path

from skiller.application.tools.files.config import FilesToolRuntimeConfig
from skiller.domain.tool.tool_contract import ToolDefinition


class FilesToolRuntimeConfigMapper:
    def from_mapping(
        self,
        *,
        raw: Mapping[str, object],
        definition: type[ToolDefinition],
    ) -> FilesToolRuntimeConfig:
        supported_fields = {
            "read",
            "write",
            "all",
        }
        unknown_fields = sorted(set(raw) - supported_fields)
        if unknown_fields:
            unknown_values = ", ".join(unknown_fields)
            raise ValueError(f"Tool 'files' has unsupported config fields: {unknown_values}")

        return FilesToolRuntimeConfig(
            definition=definition,
            read=tuple(_path_list_value(raw, "read")),
            write=tuple(_path_list_value(raw, "write")),
            all=tuple(_path_list_value(raw, "all")),
        )


def _path_list_value(raw: Mapping[str, object], name: str) -> list[Path]:
    value = raw.get(name)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"Tool 'files' field '{name}' must be a list of strings")

    items: list[Path] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"Tool 'files' field '{name}' must be a list of non-empty strings"
            )
        items.append(Path(item.strip()))
    return items
