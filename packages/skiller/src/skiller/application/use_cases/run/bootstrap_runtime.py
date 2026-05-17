from skiller.domain.run.runtime_bootstrap_port import RuntimeBootstrapPort


class BootstrapRuntimeUseCase:
    def __init__(
        self,
        store: RuntimeBootstrapPort,
    ) -> None:
        self.store = store

    def initialize(self) -> None:
        self.store.init_db()
