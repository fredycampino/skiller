from skiller.application.ports.execution_output_store_port import ExecutionOutputStorePort
from skiller.application.ports.runtime_bootstrap_port import RuntimeBootstrapPort
from skiller.application.ports.webhook_registry_port import WebhookRegistryPort


class BootstrapRuntimeUseCase:
    def __init__(
        self,
        store: RuntimeBootstrapPort,
        execution_output_store: ExecutionOutputStorePort,
        webhook_registry: WebhookRegistryPort,
    ) -> None:
        self.store = store
        self.execution_output_store = execution_output_store
        self.webhook_registry = webhook_registry

    def initialize(self) -> None:
        self.store.init_db()
        self.execution_output_store.init_db()
        self.webhook_registry.init_db()
