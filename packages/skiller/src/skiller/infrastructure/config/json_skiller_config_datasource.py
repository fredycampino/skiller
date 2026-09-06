import json
from pathlib import Path

from skiller.domain.config.skiller_config import SkillerConfig
from skiller.infrastructure.config.skiller_config_mapper import SkillerConfigMapper


class JsonSkillerConfigDatasource:
    def __init__(self, mapper: SkillerConfigMapper) -> None:
        self.mapper = mapper

    def get_config(self, config_path: Path) -> SkillerConfig:
        if not config_path.is_file():
            return self.mapper.from_json(
                {},
                base_path=config_path.parent,
            )

        try:
            raw_config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid Skiller config JSON: {config_path} "
                f"(line {exc.lineno}, column {exc.colno})"
            ) from exc

        if not isinstance(raw_config, dict):
            raise ValueError(f"Skiller config must contain a JSON object: {config_path}")

        return self.mapper.from_json(
            raw_config,
            base_path=config_path.parent,
        )
