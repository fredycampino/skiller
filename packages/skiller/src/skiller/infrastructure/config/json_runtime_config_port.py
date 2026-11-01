from pathlib import Path

from skiller.domain.config.runtime_config_port import RuntimeConfigPort
from skiller.domain.config.skiller_config import RuntimeConfig, SkillerConfig, WebhooksConfig
from skiller.infrastructure.config.json_skiller_config_datasource import (
    JsonSkillerConfigDatasource,
)
from skiller.infrastructure.config.settings_model import Settings


class JsonRuntimeConfigPort(RuntimeConfigPort):
    def __init__(
        self,
        *,
        config_datasource: JsonSkillerConfigDatasource,
        settings: Settings,
    ) -> None:
        self.config_datasource = config_datasource
        self.settings = settings

    def get_config(self, config_path: Path) -> SkillerConfig:
        config = self.config_datasource.get_config(config_path)
        return SkillerConfig(
            version=config.version,
            runtime=RuntimeConfig(
                db_path=str(Path(self.settings.db_path).expanduser().resolve()),
                log_level=self.settings.log_level,
            ),
            webhooks=WebhooksConfig(
                host=self.settings.webhooks_host,
                port=self.settings.webhooks_port,
            ),
            flow_paths=config.flow_paths,
        )
