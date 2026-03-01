from runtime.application.ports.state_store import StateStorePort
from runtime.application.use_cases.execute_run import ExecuteRunUseCase
from runtime.domain.models import Event, RunStatus


class ProcessEventUseCase:
    def __init__(self, store: StateStorePort, execute_run_use_case: ExecuteRunUseCase) -> None:
        self.store = store
        self.execute_run_use_case = execute_run_use_case

    def execute(self, event: Event) -> list[str]:
        if event.event_type == "START_RUN":
            self.store.append_event("START_RUN", event.payload, run_id=event.run_id)
            if event.run_id:
                self.execute_run_use_case.execute(event.run_id)
            return []

        if event.event_type == "WEBHOOK_RECEIVED":
            wait_key = str(event.payload.get("key", ""))
            payload = event.payload.get("payload", {})
            self.store.append_event("WEBHOOK_RECEIVED", event.payload)
            if not isinstance(payload, dict):
                return []

            waits = self.store.find_matching_waits(wait_key, payload)
            resumed: list[str] = []
            for wait in waits:
                run_id = wait["run_id"]
                self.store.resolve_wait(wait["id"])
                self.store.append_event(
                    "WAIT_RESOLVED",
                    {
                        "wait_id": wait["id"],
                        "wait_key": wait_key,
                        "payload": payload,
                    },
                    run_id=run_id,
                )
                self.store.update_run(run_id, status=RunStatus.RUNNING)
                self.execute_run_use_case.execute(run_id)
                resumed.append(run_id)
            return resumed

        return []
