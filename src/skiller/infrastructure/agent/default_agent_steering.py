from skiller.application.ports.agent.agent_steering_port import AgentSteeringPort
from skiller.application.ports.persistence.run_store_port import RunStorePort
from skiller.domain.run.steering_model import SteeringAction, SteeringItem, SteeringTarget


class DefaultAgentSteering(AgentSteeringPort):
    def __init__(self, store: RunStorePort) -> None:
        self.store = store

    def enqueue(self, run_id: str, item: SteeringItem) -> None:
        run = self._get_run_or_raise(run_id)
        run.context.steering_queue.append(item)
        self.store.update_run(run_id, context=run.context)

    def consume_abort_turn(self, run_id: str) -> bool:
        run = self._get_run_or_raise(run_id)
        queue = run.context.steering_queue

        for index, item in enumerate(queue):
            if item.target != SteeringTarget.AGENT:
                continue
            if item.action != SteeringAction.ABORT_TURN:
                continue
            del queue[index]
            self.store.update_run(run_id, context=run.context)
            return True
        return False

    def pop_steering_messages(self, run_id: str) -> list[str]:
        run = self._get_run_or_raise(run_id)
        queue = run.context.steering_queue
        remaining: list[SteeringItem] = []
        messages: list[str] = []

        for item in queue:
            if item.target != SteeringTarget.AGENT:
                remaining.append(item)
                continue
            if item.action != SteeringAction.STEERING_MESSAGE:
                remaining.append(item)
                continue
            if item.text is not None:
                messages.append(item.text)

        if len(remaining) == len(queue):
            return []

        run.context.steering_queue = remaining
        self.store.update_run(run_id, context=run.context)
        return messages

    def _get_run_or_raise(self, run_id: str):
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError(f"Run '{run_id}' not found")
        return run
