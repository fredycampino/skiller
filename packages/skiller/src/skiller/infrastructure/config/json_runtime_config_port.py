from pathlib import Path

from skiller.domain.config.runtime_config_port import RuntimeConfigPort
from skiller.domain.config.skiller_config import SkillerConfig
from skiller.infrastructure.config.json_skiller_config_datasource import (
    JsonSkillerConfigDatasource,
)


class JsonRuntimeConfigPort(RuntimeConfigPort):
    def __init__(
        self,
        *,
        config_datasource: JsonSkillerConfigDatasource,
    ) -> None:
        self.config_datasource = config_datasource

    def get_config(self, config_path: Path) -> SkillerConfig:
        return self.config_datasource.get_config(config_path)
