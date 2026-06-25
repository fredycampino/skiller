from enum import Enum


class AgentStopReason(str, Enum):
    FINAL = "final"
    INTERRUPTED = "interrupted"
    MAX_TURNS_EXHAUSTED = "max_turns_exhausted"
    CONFIG_INVALID = "config_invalid"
    INVALID_FINAL_MESSAGE = "invalid_final_message"
    LLM_REQUEST_FAILED = "llm_request_failed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
