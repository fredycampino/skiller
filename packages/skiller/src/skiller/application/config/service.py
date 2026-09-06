from skiller.application.use_cases.config.get_runtime_config import GetRuntimeConfigUseCase
from skiller.domain.config.skiller_config import SkillerConfig


class RuntimeConfigApplicationService:
    def __init__(
        self,
        get_runtime_config_use_case: GetRuntimeConfigUseCase,
    ) -> None:
        self.get_runtime_config_use_case = get_runtime_config_use_case

    def get_runtime_config(self) -> SkillerConfig:
        return self.get_runtime_config_use_case.execute()
