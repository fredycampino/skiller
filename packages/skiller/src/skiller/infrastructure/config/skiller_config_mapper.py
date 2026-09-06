from pathlib import Path

from pydantic import ValidationError

from skiller.domain.config.skiller_config import (
    RuntimeConfig,
    SkillerConfig,
    WebhooksConfig,
)
from skiller.infrastructure.config.skiller_config_schema import SkillerConfigModel


class SkillerConfigMapper:
    def __init__(self, runtime_cwd: Path) -> None:
        self.runtime_cwd = runtime_cwd

    def from_json(
        self,
        raw_config: dict[str, object],
        *,
        base_path: Path,
    ) -> SkillerConfig:
        try:
            config = SkillerConfigModel.model_validate(raw_config)
        except ValidationError as exc:
            raise ValueError(f"Invalid Skiller config: {exc}") from exc

        flow_paths: list[Path] = []
        for path_value in config.flow_paths:
            resolved_value = path_value.replace(
                "{{runtime.cwd}}",
                str(self.runtime_cwd.resolve(strict=False)),
            )
            if "{{" in resolved_value or "}}" in resolved_value:
                raise ValueError(f"Unsupported flow path template: {path_value}")

            flow_path = Path(resolved_value).expanduser()
            if not flow_path.is_absolute():
                flow_path = base_path / flow_path
            flow_paths.append(flow_path.resolve())

        return SkillerConfig(
            version=config.version,
            runtime=RuntimeConfig(
                db_path=config.runtime.db_path,
                log_level=config.runtime.log_level,
            ),
            webhooks=WebhooksConfig(
                host=config.webhooks.host,
                port=config.webhooks.port,
            ),
            flow_paths=tuple(flow_paths),
        )
