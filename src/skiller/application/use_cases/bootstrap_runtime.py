from skiller.application.ports.state_store_port import StateStorePort


class BootstrapRuntimeUseCase:
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def initialize(self) -> None:
        self.store.init_db()
