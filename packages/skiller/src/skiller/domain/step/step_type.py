from enum import Enum


class StepType(str, Enum):
    AGENT = "agent"
    ASSIGN = "assign"
    SEND = "send"
    NOTIFY = "notify"
    SHELL = "shell"
    MCP = "mcp"
    LLM_PROMPT = "llm_prompt"
    SWITCH = "switch"
    WHEN = "when"
    WAIT_INPUT = "wait_input"
    WAIT_WEBHOOK = "wait_webhook"
    WAIT_CHANNEL = "wait_channel"
