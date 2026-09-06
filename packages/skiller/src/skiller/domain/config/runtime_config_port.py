from pathlib import Path
from typing import Protocol

from skiller.domain.config.skiller_config import SkillerConfig


class RuntimeConfigPort(Protocol):
    def get_config(self, config_path: Path) -> SkillerConfig: ...
