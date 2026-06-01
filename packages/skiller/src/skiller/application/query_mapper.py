from skiller.domain.run.run_status_runtime_model import RunStatusRuntime


class RunStatusMapper:
    def to_status_dict(self, result: RunStatusRuntime) -> dict[str, object]:
        last_event_type = ""
        if result.last_event_type is not None:
            last_event_type = result.last_event_type.value

        return {
            "run_id": result.run_id,
            "status": result.status.value,
            "wait_type": result.wait_type,
            "prompt": result.prompt,
            "last_event_sequence": result.last_event_sequence,
            "last_event_type": last_event_type,
        }
