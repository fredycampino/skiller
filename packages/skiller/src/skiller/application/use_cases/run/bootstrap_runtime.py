from skiller.domain.event.webhook_registry_port import WebhookRegistryPort
from skiller.domain.run.runtime_bootstrap_port import RuntimeBootstrapPort


class BootstrapRuntimeUseCase:
    def __init__(
        self,
        store: RuntimeBootstrapPort,
        webhook_registry: WebhookRegistryPort,
    ) -> None:
        self.store = store
        self.webhook_registry = webhook_registry

    def initialize(self) -> None:
        self.store.init_db()
        self.webhook_registry.init_db()
