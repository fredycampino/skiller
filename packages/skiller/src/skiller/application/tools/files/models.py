from dataclasses import dataclass
from enum import StrEnum

from skiller.domain.tool.tool_contract import ToolRequest


class FilesAction(StrEnum):
    READ = "read"
    WRITE = "write"
    EDIT = "edit"


@dataclass(frozen=True)
class FilesToolRequest(ToolRequest):
    action: FilesAction
    path: str
    write_text: str | None = None
    old_text: str | None = None
    new_text: str | None = None
    effective_path: str | None = None
