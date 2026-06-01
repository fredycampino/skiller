from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    ParsedFlowStep,
)
from skiller.domain.step.step_type import StepType


class FlowStepTargetChecker:
    def check_start(
        self,
        *,
        start: str,
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        if start and start not in step_ids:
            errors.append(
                FlowCheckError(
                    code="FLOW_START_STEP_NOT_FOUND",
                    message="FLOW_START_STEP_NOT_FOUND: start references unknown "
                    f"step_id (start={start})",
                )
            )

    def check_steps(
        self,
        *,
        steps: list[ParsedFlowStep],
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        for step in steps:
            self._check_step(step=step, step_ids=step_ids, errors=errors)

    def _check_step(
        self,
        *,
        step: ParsedFlowStep,
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        self._check_next(step=step, step_ids=step_ids, errors=errors)

        if step.step_type == StepType.SWITCH.value:
            self._check_switch(step=step, step_ids=step_ids, errors=errors)

        if step.step_type == StepType.WHEN.value:
            self._check_when(step=step, step_ids=step_ids, errors=errors)

    def _check_next(
        self,
        *,
        step: ParsedFlowStep,
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        raw_next = step.body.get("next")
        if raw_next is None:
            return

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            errors.append(
                FlowCheckError(
                    code="FLOW_STEP_NEXT_EMPTY",
                    message="FLOW_STEP_NEXT_EMPTY: next requires non-empty target "
                    f"(step={step.step_id})",
                )
            )
            return

        if next_step_id not in step_ids:
            errors.append(
                FlowCheckError(
                    code="FLOW_STEP_NEXT_NOT_FOUND",
                    message="FLOW_STEP_NEXT_NOT_FOUND: next references unknown "
                    f"step_id (step={step.step_id}, next={next_step_id})",
                )
            )

    def _check_switch(
        self,
        *,
        step: ParsedFlowStep,
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        raw_cases = step.body.get("cases", {})
        if isinstance(raw_cases, dict):
            for target in raw_cases.values():
                target_step_id = str(target).strip()
                if target_step_id and target_step_id not in step_ids:
                    errors.append(
                        FlowCheckError(
                            code="FLOW_SWITCH_CASE_TARGET_NOT_FOUND",
                            message="FLOW_SWITCH_CASE_TARGET_NOT_FOUND: switch "
                            "case references unknown step_id "
                            f"(step={step.step_id}, target={target_step_id})",
                        )
                    )

        raw_default = str(step.body.get("default", "")).strip()
        if raw_default and raw_default not in step_ids:
            errors.append(
                FlowCheckError(
                    code="FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND",
                    message="FLOW_SWITCH_DEFAULT_TARGET_NOT_FOUND: switch default "
                    "references unknown step_id "
                    f"(step={step.step_id}, target={raw_default})",
                )
            )

    def _check_when(
        self,
        *,
        step: ParsedFlowStep,
        step_ids: set[str],
        errors: list[FlowCheckError],
    ) -> None:
        raw_branches = step.body.get("branches", [])
        if isinstance(raw_branches, list):
            for branch in raw_branches:
                if not isinstance(branch, dict):
                    continue
                target_step_id = str(branch.get("then", "")).strip()
                if target_step_id and target_step_id not in step_ids:
                    errors.append(
                        FlowCheckError(
                            code="FLOW_WHEN_BRANCH_TARGET_NOT_FOUND",
                            message="FLOW_WHEN_BRANCH_TARGET_NOT_FOUND: when branch "
                            "references unknown step_id "
                            f"(step={step.step_id}, target={target_step_id})",
                        )
                    )

        raw_default = str(step.body.get("default", "")).strip()
        if raw_default and raw_default not in step_ids:
            errors.append(
                FlowCheckError(
                    code="FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND",
                    message="FLOW_WHEN_DEFAULT_TARGET_NOT_FOUND: when default "
                    "references unknown step_id "
                    f"(step={step.step_id}, target={raw_default})",
                )
            )
