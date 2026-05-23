from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from skiller.domain.tool.tool_contract import ToolRuntimeConfig


@dataclass(frozen=True)
class FilesToolRuntimeConfig(ToolRuntimeConfig):
    read: tuple[Path, ...] = ()
    write: tuple[Path, ...] = ()
    all: tuple[Path, ...] = ()
