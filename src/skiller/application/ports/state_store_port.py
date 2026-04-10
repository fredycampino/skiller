from typing import Protocol

from skiller.application.ports.external_event_store_port import ExternalEventStorePort
from skiller.application.ports.run_store_port import RunStorePort
from skiller.application.ports.runtime_bootstrap_port import RuntimeBootstrapPort
from skiller.application.ports.runtime_event_store_port import RuntimeEventStorePort
from skiller.application.ports.wait_store_port import WaitStorePort


class StateStorePort(
    RuntimeBootstrapPort,
    RunStorePort,
    RuntimeEventStorePort,
    WaitStorePort,
    ExternalEventStorePort,
    Protocol,
):
    pass
