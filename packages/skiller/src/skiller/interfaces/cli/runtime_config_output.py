from typing import Any

from skiller.domain.config.skiller_config import SkillerConfig


class RuntimeConfigOutputMapper:
    def to_dict(self, config: SkillerConfig) -> dict[str, Any]:
        return {
            "version": config.version,
            "runtime": {
                "db_path": config.runtime.db_path,
                "log_level": config.runtime.log_level,
            },
            "webhooks": {
                "host": config.webhooks.host,
                "port": config.webhooks.port,
            },
            "flow_paths": [str(path) for path in config.flow_paths],
        }
