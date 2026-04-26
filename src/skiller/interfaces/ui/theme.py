from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiTheme:
    color_background: str
    color_text_primary: str
    color_text_muted: str
    color_error: str
    icon_success: str
    icon_error: str
    icon_waiting: str
    icon_running: str
    icon_created: str
    color_completion_text: str
    color_completion_meta: str
    color_completion_selected_bg: str
    color_completion_selected_text: str
    color_completion_meta_selected_bg: str
    color_completion_meta_selected_text: str


theme = UiTheme(
    color_background="#111111",
    color_text_primary="#f5f5f5",
    color_text_muted="#6b7280",
    color_error="#ef4444",
    icon_success="✓",
    icon_error="×",
    icon_waiting="◌",
    icon_running="•",
    icon_created="·",
    color_completion_text="#e5e7eb",
    color_completion_meta="#94a3b8",
    color_completion_selected_bg="#2563eb",
    color_completion_selected_text="#f9fafb",
    color_completion_meta_selected_bg="#1d4ed8",
    color_completion_meta_selected_text="#e2e8f0",
)


def build_prompt_toolkit_style_dict(*, ui_theme: UiTheme = theme) -> dict[str, str]:
    return {
        "textarea": f"bg:{ui_theme.color_background} {ui_theme.color_text_primary}",
        "footer": f"fg:{ui_theme.color_text_muted}",
        "status": f"fg:{ui_theme.color_text_muted}",
        "status.error": f"fg:{ui_theme.color_error}",
        "completion-menu": f"bg:default {ui_theme.color_completion_text}",
        "completion-menu.completion": f"bg:default {ui_theme.color_completion_text}",
        "completion-menu.completion.current": (
            f"bg:{ui_theme.color_completion_selected_bg} "
            f"{ui_theme.color_completion_selected_text} noreverse"
        ),
        "completion-menu.meta.completion": f"bg:default {ui_theme.color_completion_meta}",
        "completion-menu.meta.completion.current": (
            f"bg:{ui_theme.color_completion_meta_selected_bg} "
            f"{ui_theme.color_completion_meta_selected_text} noreverse"
        ),
    }
