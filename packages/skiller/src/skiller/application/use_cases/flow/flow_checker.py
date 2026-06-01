from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    FlowCheckResult,
    FlowCheckStatus,
)
from skiller.application.use_cases.flow.flow_end_action_checker import FlowEndActionChecker
from skiller.application.use_cases.flow.flow_shape_checker import FlowShapeChecker
from skiller.application.use_cases.flow.flow_step_collector import FlowStepCollector
from skiller.application.use_cases.flow.flow_step_fields_checker import FlowStepFieldsChecker
from skiller.application.use_cases.flow.flow_step_target_checker import FlowStepTargetChecker
from skiller.application.use_cases.flow.flow_template_checker import FlowTemplateChecker
from skiller.domain.flow.flow_port import FlowPort


class FlowCheckerUseCase:
    def __init__(self, flow_port: FlowPort) -> None:
        self.flow_port = flow_port
        self.shape_checker = FlowShapeChecker()
        self.step_collector = FlowStepCollector()
        self.step_target_checker = FlowStepTargetChecker()
        self.step_fields_checker = FlowStepFieldsChecker()
        self.end_action_checker = FlowEndActionChecker()
        self.template_checker = FlowTemplateChecker()

    def execute(
        self,
        flow_ref: str,
        *,
        flow_source: str,
    ) -> FlowCheckResult:
        flow = self.flow_port.get_yaml_flow(source=flow_source, ref=flow_ref)
        errors: list[FlowCheckError] = []

        shape = self.shape_checker.check(flow=flow, errors=errors)
        if not shape.can_continue or shape.steps is None:
            return self._result(errors)

        steps = self.step_collector.collect(raw_steps=shape.steps, errors=errors)
        step_ids = {step.step_id for step in steps}

        self.step_target_checker.check_start(
            start=shape.start,
            step_ids=step_ids,
            errors=errors,
        )
        self.step_target_checker.check_steps(
            steps=steps,
            step_ids=step_ids,
            errors=errors,
        )
        self.step_fields_checker.check(steps=steps, errors=errors)
        self.end_action_checker.check(flow=flow, errors=errors)
        self.template_checker.check_steps(
            steps=steps,
            step_ids=step_ids,
            errors=errors,
        )
        self.template_checker.check_end_actions(
            flow=flow,
            steps=steps,
            step_ids=step_ids,
            errors=errors,
        )

        return self._result(errors)

    def _result(self, errors: list[FlowCheckError]) -> FlowCheckResult:
        if errors:
            return FlowCheckResult(status=FlowCheckStatus.INVALID, errors=errors)
        return FlowCheckResult(status=FlowCheckStatus.VALID, errors=[])
