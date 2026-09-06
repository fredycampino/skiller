from pathlib import Path

from skiller.domain.config.runtime_config_port import RuntimeConfigPort
from skiller.domain.config.skiller_config import SkillerConfig
from skiller.domain.flow.packaged_flow_paths_port import PackagedFlowPathsPort


class GetRuntimeConfigUseCase:
    def __init__(
        self,
        runtime_config: RuntimeConfigPort,
        packaged_flow_paths: PackagedFlowPathsPort,
        environment_config_path: str | None,
        default_config_path: Path,
    ) -> None:
        self.runtime_config = runtime_config
        self.packaged_flow_paths = packaged_flow_paths
        self.environment_config_path = environment_config_path
        self.default_config_path = default_config_path

    def execute(self) -> SkillerConfig:
        config_path = self.default_config_path.expanduser()
        if self.environment_config_path and self.environment_config_path.strip():
            config_path = Path(self.environment_config_path.strip()).expanduser()
            if not config_path.is_file():
                raise FileNotFoundError(f"Missing Skiller config: {config_path}")

        config = self.runtime_config.get_config(config_path)
        flow_paths = list(config.flow_paths)
        for packaged_flow_path in self.packaged_flow_paths.get_paths():
            if packaged_flow_path not in flow_paths:
                flow_paths.append(packaged_flow_path)

        return SkillerConfig(
            version=config.version,
            runtime=config.runtime,
            webhooks=config.webhooks,
            flow_paths=tuple(flow_paths),
        )
