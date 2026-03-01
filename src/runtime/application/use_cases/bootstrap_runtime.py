from runtime.application.ports.bootstrap import RuntimeBootstrapPort
from runtime.application.ports.state_store import StateStorePort


class BootstrapRuntimeUseCase(RuntimeBootstrapPort):
    def __init__(self, store: StateStorePort) -> None:
        self.store = store

    def initialize(self) -> None:
        self.store.init_db()
