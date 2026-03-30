from enum import Enum


class StepType(str, Enum):
    ASSIGN = "assign"
    NOTIFY = "notify"
    SHELL = "shell"
    MCP = "mcp"
    LLM_PROMPT = "llm_prompt"
    SWITCH = "switch"
    WHEN = "when"
    WAIT_INPUT = "wait_input"
    WAIT_WEBHOOK = "wait_webhook"
