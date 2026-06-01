from skiller.application.use_cases.flow.flow_check_model import (
    FlowCheckError,
    ParsedFlowStep,
)
from skiller.domain.flow.flow_raw_definition import FlowRawStepDefinition
from skiller.domain.step.step_type import StepType


class FlowStepCollector:
    def collect(
        self,
        *,
        raw_steps: tuple[FlowRawStepDefinition, ...],
        errors: list[FlowCheckError],
    ) -> list[ParsedFlowStep]:
        parsed_steps: list[ParsedFlowStep] = []
        seen_step_ids: set[str] = set()
        valid_step_types = {item.value for item in StepType}

        for raw_step in raw_steps:
            index = raw_step.index
            if not isinstance(raw_step.raw, dict):
                errors.append(
                    FlowCheckError(
                        code="FLOW_STEP_PRIMARY_HEADER_MISSING",
                        message="FLOW_STEP_PRIMARY_HEADER_MISSING: step requires "
                        f"a primary header (index={index})",
                    )
                )
                continue

            primary_keys = [key for key in raw_step.raw if key in valid_step_types]
            if not primary_keys:
                if raw_step.raw:
                    first_key = next(iter(raw_step.raw))
                    errors.append(
                        FlowCheckError(
                            code="FLOW_STEP_PRIMARY_HEADER_INVALID",
                            message="FLOW_STEP_PRIMARY_HEADER_INVALID: unsupported "
                            f"step type (index={index}, step_type={first_key})",
                        )
                    )
                    continue
                errors.append(
                    FlowCheckError(
                        code="FLOW_STEP_PRIMARY_HEADER_MISSING",
                        message="FLOW_STEP_PRIMARY_HEADER_MISSING: step requires "
                        f"a primary header (index={index})",
                    )
                )
                continue

            if len(primary_keys) > 1:
                errors.append(
                    FlowCheckError(
                        code="FLOW_STEP_PRIMARY_HEADER_INVALID",
                        message="FLOW_STEP_PRIMARY_HEADER_INVALID: unsupported step "
                        f"type (index={index}, step_type=multiple)",
                    )
                )
                continue

            step_type = primary_keys[0]
            step_id = str(raw_step.raw.get(step_type, "")).strip()
            if not step_id:
                errors.append(
                    FlowCheckError(
                        code="FLOW_STEP_ID_MISSING",
                        message="FLOW_STEP_ID_MISSING: step requires non-empty "
                        f"step_id (index={index}, step_type={step_type})",
                    )
                )
                continue

            if step_id in seen_step_ids:
                errors.append(
                    FlowCheckError(
                        code="FLOW_STEP_ID_DUPLICATED",
                        message=f"FLOW_STEP_ID_DUPLICATED: duplicated step_id "
                        f"(step_id={step_id})",
                    )
                )
                continue

            seen_step_ids.add(step_id)
            parsed_steps.append(
                ParsedFlowStep(
                    index=index or 0,
                    step_id=step_id,
                    step_type=step_type,
                    body={
                        key: value for key, value in raw_step.raw.items() if key != step_type
                    },
                )
            )

        return parsed_steps
