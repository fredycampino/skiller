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
        base_path: Path,
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
            read=tuple(_path_list_value(raw, "read", base_path=base_path)),
            write=tuple(_path_list_value(raw, "write", base_path=base_path)),
            all=tuple(_path_list_value(raw, "all", base_path=base_path)),
        )


def _path_list_value(
    raw: Mapping[str, object],
    name: str,
    *,
    base_path: Path,
) -> list[Path]:
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
        path = Path(item.strip()).expanduser()
        if not path.is_absolute():
            path = base_path / path
        items.append(path.resolve(strict=False))
    return items
