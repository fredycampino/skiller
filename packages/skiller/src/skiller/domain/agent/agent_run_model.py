from enum import Enum


class AgentRunnerFinish(str, Enum):
    FINAL = "final"
    INTERRUPTED = "interrupted"
    MAX_TURNS_EXHAUSTED = "max_turns_exhausted"
    LLM_REQUEST_FAILED = "llm_request_failed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
