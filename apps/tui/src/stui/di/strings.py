from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiStrings:
    intro_title: str = "Skiller.run stui"
    intro_body: str = "Run agentics workflows."
    intro_hint: str = ""
    unsupported_input_message: str = (
        "Use /run <agent> to execute an agent, or /auth to configure auth."
    )
    runs_table_empty_message: str = "No runs yet. Use /run to execute your flows."
    runs_table_navigation_hint: str = "↑↓ · Enter · Esc"
    waiting_webhook_message: str = "Waiting webhook"
    notify_action_done_label: str = "done"
    autocomplete_run_description: str = "Run an agentic flow"
    autocomplete_runs_description: str = "Show runs"
    autocomplete_auth_description: str = "Configure authentication"
    autocomplete_models_description: str = "Show models"
    models_table_help: str = "↑↓ select · ←→ switch table · Enter select · Esc close"
    models_table_no_provider_selected_message: str = "No provider selected"
    models_table_no_providers_message: str = "No providers available."
    models_table_no_models_message: str = "No models available."
    models_table_select_model_title: str = "Select a model"
    models_table_auth_required_template: str = "Run /auth {provider} to configure"
    models_table_no_models_for_provider_template: str = "{provider}: no models available"
    models_table_provider_configured_marker: str = "✓"
    models_table_active_model_marker: str = "●"
    auth_unknown_provider_message: str = (
        "Unknown auth provider. Use /auth, /auth codex, /auth minimax, or /auth bedrock."
    )
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
