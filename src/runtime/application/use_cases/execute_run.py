from typing import Any

from runtime.application.ports.policy_gate import PolicyGatePort
from runtime.application.ports.skill_runner import SkillRunnerPort
from runtime.application.ports.state_store import StateStorePort
from runtime.application.ports.tool_executor import ToolExecutorPort
from runtime.domain.models import RunStatus


class ExecuteRunUseCase:
    def __init__(
        self,
        store: StateStorePort,
        skill_runner: SkillRunnerPort,
        policy_gate: PolicyGatePort,
        tool_router: ToolExecutorPort,
    ) -> None:
        self.store = store
        self.skill_runner = skill_runner
        self.policy_gate = policy_gate
        self.tool_router = tool_router

    def execute(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        if run is None:
            return

        context = run.get("context", {})
        if not isinstance(context, dict):
            context = {}
        context.setdefault("inputs", {})
        context.setdefault("steps", {})

        skill = self.skill_runner.load_skill(run["skill_name"])
        steps = skill.get("steps", [])
        step_index = int(run.get("current_step", 0))

        self.store.update_run(run_id, status=RunStatus.RUNNING, current_step=step_index, context=context)

        try:
            while step_index < len(steps):
                raw_step = steps[step_index]
                step = self.skill_runner.render_step(raw_step, context)
                step_id = str(step.get("id", f"step_{step_index}"))

                if not self.policy_gate.authorize(run["skill_name"], step):
                    self.store.update_run(run_id, status=RunStatus.FAILED, current_step=step_index, context=context)
                    self.store.append_event("STEP_DENIED", {"step": step_id}, run_id=run_id)
                    return

                step_type = step.get("type")

                if step_type == "tool":
                    result = self.tool_router.call(str(step.get("tool", "")), step.get("args", {}))
                    context["steps"][step_id] = result
                    step_index += 1
                    self.store.update_run(run_id, current_step=step_index, context=context)
                    self.store.append_event(
                        "TOOL_RESULT",
                        {"step": step_id, "tool": step.get("tool"), "result": result},
                        run_id=run_id,
                    )
                    continue

                if step_type == "notify":
                    message = str(step.get("message", ""))
                    context["steps"][step_id] = {"ok": True, "message": message}
                    step_index += 1
                    self.store.update_run(run_id, current_step=step_index, context=context)
                    self.store.append_event("NOTIFY", {"step": step_id, "message": message}, run_id=run_id)
                    continue

                if step_type == "llm":
                    context["steps"][step_id] = {"ok": False, "reason": "llm-not-implemented"}
                    step_index += 1
                    self.store.update_run(run_id, current_step=step_index, context=context)
                    self.store.append_event("LLM_STEP_SKIPPED", {"step": step_id}, run_id=run_id)
                    continue

                if step_type == "wait_webhook":
                    wait_key = str(step.get("wait_key", ""))
                    match = step.get("match", {})
                    if not wait_key:
                        raise ValueError(f"Step '{step_id}' requires wait_key")
                    if not isinstance(match, dict):
                        raise ValueError(f"Step '{step_id}' match must be an object")

                    wait_id = self.store.create_wait(run_id, wait_key, match, step_id=step_id)
                    step_index += 1
                    self.store.update_run(
                        run_id,
                        status=RunStatus.WAITING,
                        current_step=step_index,
                        context=context,
                    )
                    self.store.append_event(
                        "WAITING",
                        {"step": step_id, "wait_id": wait_id, "wait_key": wait_key, "match": match},
                        run_id=run_id,
                    )
                    return

                raise ValueError(f"Unknown step type '{step_type}' in step '{step_id}'")

            self.store.update_run(
                run_id,
                status=RunStatus.SUCCEEDED,
                current_step=step_index,
                context=context,
            )
            self.store.append_event("RUN_FINISHED", {"status": RunStatus.SUCCEEDED.value}, run_id=run_id)

        except Exception as exc:  # noqa: BLE001
            self.store.update_run(run_id, status=RunStatus.FAILED, current_step=step_index, context=context)
            self.store.append_event("RUN_FAILED", {"error": str(exc)}, run_id=run_id)
