from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiStrings:
    intro_title: str = "Skiller.run stui"
    intro_body: str = "Run agentics workflows."
    intro_hint: str = ""
    unsupported_input_message: str = "Use /run <agent> to execute an agent."
    runs_table_empty_message: str = "No runs yet. Use /run to execute your flows."
    runs_table_navigation_hint: str = "↑↓ · Enter · Esc"
    waiting_webhook_message: str = "Waiting webhook"
    notify_action_done_label: str = "done"
    autocomplete_run_description: str = "Run an agentic flow"
    autocomplete_runs_description: str = "Show runs"
    autocomplete_quit_description: str = "Exit the TUI"
    autocomplete_exit_description: str = "Exit the TUI"
    autocomplete_dev_description: str = "Show local debug state"
    agent_interrupted_notice: str = "Interrupted by user"
    agent_max_turns_exhausted_notice: str = "Turn limit reached"
    agent_config_invalid_notice_title: str = "Invalid agent config"
    agent_config_invalid_notice_template: str = "{title}\n\n{message}"
    agent_llm_request_failed_notice_title: str = "LLM request failed"
    agent_llm_request_failed_notice_template: str = "{title}\n\n{message}"
    agent_context_stats_title: str = "Agent Context"
    run_snapshot_updated_notice_template: str = "Run snapshot updated: {ref}"
    run_snapshot_failed_notice_template: str = "Run snapshot sync failed: {error}"


DEFAULT_TUI_STRINGS = TuiStrings()
