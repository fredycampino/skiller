import json
import re
from dataclasses import dataclass
from typing import Any

from skiller.application.ports.execution_output_store_port import ExecutionOutputStorePort
from skiller.application.ports.llm_port import LLMPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepAdvance,
    StepExecutionStatus,
)
from skiller.domain.large_result_truncator import LargeResultTruncator
from skiller.domain.run_model import RunStatus
from skiller.domain.step_execution_model import LlmPromptOutput, StepExecution

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class _LlmPromptStepConfig:
    system: str
    prompt: str
    output: dict[str, Any]
    schema: dict[str, Any]
    large_result: bool


class ExecuteLlmPromptStepUseCase:
    def __init__(
        self,
        store: StateStorePort,
        execution_output_store: ExecutionOutputStorePort,
        llm: LLMPort,
        large_result_truncator: LargeResultTruncator,
    ) -> None:
        self.store = store
        self.execution_output_store = execution_output_store
        self.llm = llm
        self.large_result_truncator = large_result_truncator

    def execute(self, current_step: CurrentStep) -> StepAdvance:
        step_id = current_step.step_id
        config = self._read_step_config(step_id=step_id, step=current_step.step)

        messages = self._build_messages(system=config.system, prompt=config.prompt)
        response = self.llm.generate(
            messages,
            config={"output": config.output, "step_id": step_id},
        )
        self._raise_if_failed(step_id=step_id, response=response)

        parsed = self._parse_response_payload(step_id=step_id, response=response)
        self._validate_schema(schema=config.schema, value=parsed, path="$")
        output = self._build_output(
            run_id=current_step.run_id,
            step_id=step_id,
            parsed=parsed,
            large_result=config.large_result,
        )
        execution = StepExecution(
            step_type=current_step.step_type,
            input={
                "system": config.system,
                "prompt": config.prompt,
                "output": config.output,
                "large_result": config.large_result,
            },
            evaluation={"model": str(response.get("model", "")).strip() or None},
            output=output,
        )
        current_step.context.step_executions[step_id] = execution
        return self._advance(current_step=current_step, execution=execution)

    def _read_step_config(self, *, step_id: str, step: dict[str, Any]) -> _LlmPromptStepConfig:
        prompt = self._parse_prompt(step_id=step_id, step=step)
        output = self._parse_output(step_id=step_id, step=step)
        return _LlmPromptStepConfig(
            system=str(step.get("system", "")),
            prompt=prompt,
            output=output,
            schema=self._parse_schema(step_id=step_id, output=output),
            large_result=self._parse_large_result(step_id=step_id, value=step.get("large_result")),
        )

    def _parse_prompt(self, *, step_id: str, step: dict[str, Any]) -> str:
        prompt = str(step.get("prompt", ""))
        if not prompt.strip():
            raise ValueError(f"Step '{step_id}' requires prompt")
        return prompt

    def _parse_output(self, *, step_id: str, step: dict[str, Any]) -> dict[str, Any]:
        output = step.get("output")
        if not isinstance(output, dict):
            raise ValueError(f"Step '{step_id}' requires output object")

        output_format = str(output.get("format", "")).strip()
        if output_format != "json":
            raise ValueError(f"Step '{step_id}' requires output.format 'json'")
        return output

    def _parse_schema(self, *, step_id: str, output: dict[str, Any]) -> dict[str, Any]:
        schema = output.get("schema")
        if not isinstance(schema, dict):
            raise ValueError(f"Step '{step_id}' requires output.schema object")
        return schema

    def _parse_large_result(self, *, step_id: str, value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        raise ValueError(f"Step '{step_id}' requires boolean large_result")

    def _raise_if_failed(self, *, step_id: str, response: dict[str, Any]) -> None:
        if response.get("ok") is False:
            error = str(response.get("error", "")).strip() or f"LLM step '{step_id}' failed"
            raise ValueError(error)

    def _build_output(
        self,
        *,
        run_id: str,
        step_id: str,
        parsed: Any,
        large_result: bool,
    ) -> LlmPromptOutput:
        full_text = self._build_result_text(parsed)
        text_ref = self._build_text_ref(parsed)
        if not large_result:
            return LlmPromptOutput(
                text=full_text,
                text_ref=text_ref,
                data=parsed,
            )

        full_value = {"data": self._clone(parsed)}
        output_data = self.large_result_truncator.truncate(parsed)
        output_text = self._build_result_text(output_data)

        body_ref = self.execution_output_store.store_execution_output(
            run_id=run_id,
            step_id=step_id,
            output_body={
                "value": full_value,
            },
        )
        return LlmPromptOutput(
            text=output_text,
            text_ref=text_ref,
            data=output_data,
            body_ref=body_ref,
        )

    def _advance(self, *, current_step: CurrentStep, execution: StepExecution) -> StepAdvance:
        step_id = current_step.step_id
        raw_next = current_step.step.get("next")

        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=current_step.context,
            )
            return StepAdvance(
                status=StepExecutionStatus.COMPLETED,
                execution=execution,
            )

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=current_step.context,
        )
        return StepAdvance(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
            execution=execution,
        )

    def _build_messages(self, *, system: str, prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_result_text(self, value: Any) -> str:
        if isinstance(value, dict):
            if "text" in value and isinstance(value["text"], str):
                return value["text"]
            if "reply" in value and isinstance(value["reply"], str):
                return value["reply"]
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    def _build_text_ref(self, value: Any) -> str | None:
        if isinstance(value, dict):
            if "text" in value and isinstance(value["text"], str):
                return "data.text"
            if "reply" in value and isinstance(value["reply"], str):
                return "data.reply"
            return None
        if isinstance(value, (str, int, float, bool)) or value is None:
            return "data"
        return None

    def _parse_response_payload(self, *, step_id: str, response: dict[str, Any]) -> Any:
        if "json" in response:
            return response["json"]

        content = response.get("content")
        if isinstance(content, (dict, list, int, float, bool)) or content is None:
            return content

        if not isinstance(content, str):
            raise ValueError(f"LLM step '{step_id}' returned invalid response payload")

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            normalized_content = self._strip_json_fence(content)
            if normalized_content != content:
                try:
                    return json.loads(normalized_content)
                except json.JSONDecodeError:
                    pass

            raise ValueError(f"LLM step '{step_id}' returned invalid JSON: {exc.msg}") from exc

    def _validate_schema(self, *, schema: dict[str, Any], value: Any, path: str) -> None:
        schema_type = schema.get("type")
        if schema_type is not None and not isinstance(schema_type, str):
            raise ValueError(f"Invalid schema at {path}: field 'type' must be a string")
        if isinstance(schema_type, str) and schema_type not in {
            "object",
            "array",
            "string",
            "boolean",
            "integer",
            "number",
        }:
            raise ValueError(f"Invalid schema at {path}: unsupported type '{schema_type}'")

        if "enum" in schema:
            enum_values = schema["enum"]
            if not isinstance(enum_values, list):
                raise ValueError(f"Invalid schema at {path}: field 'enum' must be an array")
            if value not in enum_values:
                raise ValueError(
                    "LLM step output schema validation failed "
                    f"at {path}: value must be one of {enum_values}"
                )

        if schema_type == "object":
            self._validate_object_schema(schema=schema, value=value, path=path)
            return

        if schema_type == "array":
            self._validate_array_schema(schema=schema, value=value, path=path)
            return

        if schema_type == "string" and not isinstance(value, str):
            raise ValueError(f"LLM step output schema validation failed at {path}: expected string")
        if schema_type == "boolean" and not isinstance(value, bool):
            raise ValueError(
                f"LLM step output schema validation failed at {path}: expected boolean"
            )
        if schema_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(
                f"LLM step output schema validation failed at {path}: expected integer"
            )
        if schema_type == "number" and not self._is_number(value):
            raise ValueError(f"LLM step output schema validation failed at {path}: expected number")

    def _validate_object_schema(self, *, schema: dict[str, Any], value: Any, path: str) -> None:
        if not isinstance(value, dict):
            raise ValueError(f"LLM step output schema validation failed at {path}: expected object")

        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise ValueError(
                f"Invalid schema at {path}: field 'required' must be an array of strings"
            )

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"Invalid schema at {path}: field 'properties' must be an object")

        for field_name in required:
            if field_name not in value:
                raise ValueError(
                    "LLM step output schema validation failed "
                    f"at {path}.{field_name}: required field is missing"
                )

        for field_name, field_schema in properties.items():
            if field_name not in value:
                continue
            if not isinstance(field_schema, dict):
                raise ValueError(
                    f"Invalid schema at {path}.{field_name}: property schema must be an object"
                )
            self._validate_schema(
                schema=field_schema, value=value[field_name], path=f"{path}.{field_name}"
            )

    def _validate_array_schema(self, *, schema: dict[str, Any], value: Any, path: str) -> None:
        if not isinstance(value, list):
            raise ValueError(f"LLM step output schema validation failed at {path}: expected array")

        items = schema.get("items")
        if items is None:
            return
        if not isinstance(items, dict):
            raise ValueError(f"Invalid schema at {path}: field 'items' must be an object")

        for index, item in enumerate(value):
            self._validate_schema(schema=items, value=item, path=f"{path}[{index}]")

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, int | float) and not isinstance(value, bool)

    def _strip_json_fence(self, content: str) -> str:
        match = _JSON_FENCE_RE.match(content)
        if match is None:
            return content
        return match.group(1).strip()

    def _clone(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item) for item in value]
        return value
