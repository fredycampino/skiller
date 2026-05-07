from typing import Protocol

from skiller.application.ports.persistence.external_event_store_port import (
    ExternalEventStorePort,
)
from skiller.application.ports.persistence.run_store_port import RunStorePort
from skiller.application.ports.persistence.wait_store_port import WaitStorePort
from skiller.application.ports.runtime.runtime_bootstrap_port import RuntimeBootstrapPort
from skiller.application.ports.runtime.runtime_event_store_port import RuntimeEventStorePort


class StateStorePort(
    RuntimeBootstrapPort,
    RunStorePort,
    RuntimeEventStorePort,
    WaitStorePort,
    ExternalEventStorePort,
    Protocol,
):
    pass
