import json
import re
from typing import Any

from skiller.application.ports.llm_port import LLMPort
from skiller.application.ports.state_store_port import StateStorePort
from skiller.application.use_cases.render_current_step import CurrentStep
from skiller.application.use_cases.step_execution_result import (
    StepExecutionResult,
    StepExecutionStatus,
)
from skiller.domain.run_model import RunStatus

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class ExecuteLlmPromptStepUseCase:
    def __init__(self, store: StateStorePort, llm: LLMPort) -> None:
        self.store = store
        self.llm = llm

    def execute(self, current_step: CurrentStep) -> StepExecutionResult:
        step = current_step.step
        step_id = current_step.step_id

        prompt = str(step.get("prompt", ""))
        system = str(step.get("system", ""))
        output = step.get("output")

        if not prompt.strip():
            raise ValueError(f"Step '{step_id}' requires prompt")
        if not isinstance(output, dict):
            raise ValueError(f"Step '{step_id}' requires output object")

        output_format = str(output.get("format", "")).strip()
        if output_format != "json":
            raise ValueError(f"Step '{step_id}' requires output.format 'json'")

        schema = output.get("schema")
        if not isinstance(schema, dict):
            raise ValueError(f"Step '{step_id}' requires output.schema object")

        messages = self._build_messages(system=system, prompt=prompt)
        response = self.llm.generate(messages, config={"output": output, "step_id": step_id})

        if response.get("ok") is False:
            error = str(response.get("error", "")).strip() or f"LLM step '{step_id}' failed"
            self._append_error_event(current_step=current_step, message=error, response=response)
            raise ValueError(error)

        try:
            parsed = self._parse_response_payload(step_id=step_id, response=response)
            self._validate_schema(schema=schema, value=parsed, path="$")
        except ValueError as exc:
            self._append_error_event(current_step=current_step, message=str(exc), response=response)
            raise

        current_step.context.results[step_id] = parsed
        self.store.append_event(
            "LLM_PROMPT_RESULT",
            {
                "step": step_id,
                "result": parsed,
                "model": response.get("model"),
            },
            run_id=current_step.run_id,
        )

        raw_next = step.get("next")
        if raw_next is None:
            self.store.update_run(
                current_step.run_id,
                status=RunStatus.RUNNING,
                context=current_step.context,
            )
            return StepExecutionResult(status=StepExecutionStatus.COMPLETED)

        next_step_id = str(raw_next).strip()
        if not next_step_id:
            raise ValueError(f"Step '{step_id}' requires non-empty next")

        self.store.update_run(
            current_step.run_id,
            status=RunStatus.RUNNING,
            current=next_step_id,
            context=current_step.context,
        )
        return StepExecutionResult(
            status=StepExecutionStatus.NEXT,
            next_step_id=next_step_id,
        )

    def _build_messages(self, *, system: str, prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

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

    def _append_error_event(
        self,
        *,
        current_step: CurrentStep,
        message: str,
        response: dict[str, Any],
    ) -> None:
        step_id = current_step.step_id
        model = response.get("model")
        formatted_model = model.strip() if isinstance(model, str) and model.strip() else None

        if "json" in response:
            raw_response = self._truncate_debug_value(response["json"])
        elif "content" in response:
            raw_response = self._truncate_debug_value(response["content"])
        else:
            raw_response = None

        payload: dict[str, Any] = {
            "step": step_id,
            "error": message,
        }
        if formatted_model is not None:
            payload["model"] = formatted_model
        if raw_response is not None:
            payload["raw_response"] = raw_response

        self.store.append_event(
            "LLM_PROMPT_ERROR",
            payload,
            run_id=current_step.run_id,
        )

    def _truncate_debug_value(self, value: Any) -> str:
        if isinstance(value, str):
            raw = value
        else:
            raw = json.dumps(value, ensure_ascii=True)

        compact = raw.replace("\n", "\\n")
        if len(compact) <= 300:
            return compact
        return f"{compact[:300]}..."

    def _strip_json_fence(self, content: str) -> str:
        match = _JSON_FENCE_RE.match(content)
        if match is None:
            return content
        return match.group(1).strip()
