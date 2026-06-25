from skiller.domain.agent.llm.model import LLMToolCall


class AgentRunnerFeedback:
    def last_turn_warning(self) -> str:
        return (
            "[Skiller] Last allowed turn. "
            "If you can finish, return the final answer now. "
            "Otherwise stop and wait for the user to continue."
        )

    def max_turns_exhausted(self) -> str:
        return "[Skiller] max_turns exhausted before a final answer."

    def user_interrupted_turn(self) -> str:
        return "[Skiller] User interrupted the current tool turn."

    def invalid_tool_call_arguments(
        self,
        *,
        step_id: str,
        tool_call: LLMToolCall,
        error: ValueError,
    ) -> str:
        tool_name = str(tool_call.function.name or "").strip() or "unknown"
        detail = str(error).strip() or "invalid tool call arguments"
        return (
            f"[Skiller] Invalid tool call arguments in step '{step_id}' "
            f"for tool '{tool_name}': {detail}. "
            "Return a single JSON object with valid arguments."
        )

    def too_many_tool_calls(
        self,
        *,
        step_id: str,
        max_tool_calls: int,
        tool_call_count: int,
    ) -> str:
        return (
            f"[Skiller] Too many tool calls in step '{step_id}': "
            f"received {tool_call_count}, maximum allowed is {max_tool_calls}. "
            f"Return at most {max_tool_calls} tool call(s) in one response."
        )

    def tool_result_too_large(
        self,
        *,
        tool_name: str,
        field: str,
        max_bytes: int,
        actual_bytes: int,
    ) -> str:
        return (
            f"[Skiller] Tool result {field} from '{tool_name}' is too large "
            f"for agent context: {actual_bytes} bytes, maximum allowed is "
            f"{max_bytes} bytes. "
            "Use a narrower request, filter the output, or inspect smaller ranges."
        )
