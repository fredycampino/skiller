from skiller.application.use_cases.bootstrap_runtime import BootstrapRuntimeUseCase


class RuntimeBootstrapService:
    def __init__(self, bootstrap_runtime_use_case: BootstrapRuntimeUseCase) -> None:
        self.bootstrap_runtime_use_case = bootstrap_runtime_use_case

    def initialize(self) -> None:
        self.bootstrap_runtime_use_case.initialize()
