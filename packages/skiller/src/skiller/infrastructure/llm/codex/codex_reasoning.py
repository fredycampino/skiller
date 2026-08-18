from enum import Enum


class CodexReasoningEffort(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"
    ULTRA = "ultra"


CODEX_DEFAULT_REASONING_EFFORT = CodexReasoningEffort.MEDIUM
