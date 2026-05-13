from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TuiTheme:
    color_terminal_default: str = "ansi_default"
    color_text_primary: str = "ansi_default"
    color_text_secondary: str = "#8a8a8a"
    color_text_muted: str = "#555555"
    color_text_warning: str = "#d29922"
    color_text_success: str = "#7ee787"
    color_text_error: str = "#ff7b72"
    color_text_accent: str = "#79c0ff"
    color_text_selected: str = "white"
    color_prompt_border: str = "#444444"
    cursor: str = ">"
    user_icon: str = "›"
    agent_message_icon: str = "‹"
    agent_tool_icon: str = "▪"
    system_warning_icon: str = "!"
    selector: str = "→"
    autocomplete_selector_icon: str = "->"
    prompt_placeholder: str = "type / for commands"
    session_empty_icon: str = "◌"
    status_spinner_frames: tuple[str, ...] = ("◐", "◓", "◑", "◒")
    status_icon_waiting: str = "◌"
    status_icon_success: str = "✓"
    status_icon_error: str = "×"
    status_animation_interval: float = 0.1
    slash_command_name_width: int = 8
    autocomplete_visible_lines: int = 6
    horizontal_padding: int = 1
    status_margin_top: int = 1
    prompt_prefix_width: int = 2
    prompt_min_height: int = 3
    prompt_max_height: int = 5
    prompt_editor_max_height: int = 3
    footer_margin_top: int = 1

    def rich_style(self, color: str) -> str:
        if color == self.color_terminal_default:
            return ""
        return color


DEFAULT_TUI_THEME = TuiTheme()


def build_textual_css(theme: TuiTheme = DEFAULT_TUI_THEME) -> str:
    footer_margin_x = theme.horizontal_padding * 2
    autocomplete_box_height = theme.autocomplete_visible_lines + 2
    return f"""
        App {{
            background: {theme.color_terminal_default};
            color: {theme.color_text_primary};
        }}

        Screen {{
            layout: vertical;
            background: {theme.color_terminal_default};
            color: {theme.color_text_primary};
        }}

        #root {{
            layout: vertical;
            height: 100%;
            background: {theme.color_terminal_default};
        }}

        #transcript-log {{
            height: 1fr;
            width: 100%;
            overflow: scroll;
            scrollbar-size: 0 0;
            scrollbar-visibility: hidden;
            background: {theme.color_terminal_default};
            border: none;
            margin: 0 {theme.horizontal_padding} 0 {theme.horizontal_padding};
            padding: 0 1;
        }}

        #status {{
            height: auto;
            width: 100%;
            margin:
                {theme.status_margin_top}
                {theme.horizontal_padding}
                0
                {theme.horizontal_padding};
            padding: 0 1;
            color: {theme.color_text_primary};
            text-style: dim;
            background: {theme.color_terminal_default};
        }}

        #runs-table-area {{
            height: 1fr;
            align: center bottom;
            width: 100%;
            margin: 0 {theme.horizontal_padding} 0 {theme.horizontal_padding};
            overflow: hidden;
            scrollbar-size: 0 0;
            scrollbar-visibility: hidden;
        }}

        #prompt-row {{
            height: auto;
            width: 100%;
            min-height: {theme.prompt_min_height};
            max-height: {theme.prompt_max_height};
            margin: 0 {theme.horizontal_padding} 0 {theme.horizontal_padding};
            padding: 0 1;
            border: round {theme.color_prompt_border};
            background: {theme.color_terminal_default};
        }}

        #prompt-prefix {{
            width: {theme.prompt_prefix_width};
            padding: 0;
            content-align: left top;
            color: {theme.color_text_primary};
            background: {theme.color_terminal_default};
        }}

        #prompt {{
            height: auto;
            min-height: 1;
            max-height: {theme.prompt_editor_max_height};
            border: none;
            padding: 0;
            margin: 0;
            overflow-y: auto;
            background: {theme.color_terminal_default};
            color: {theme.color_text_primary};
        }}

        #prompt:focus {{
            background-tint: transparent;
        }}

        #prompt .text-area--placeholder {{
            color: {theme.color_text_muted};
            text-style: none;
        }}

        #prompt .text-area--selection {{
            background: {theme.color_terminal_default};
            text-style: reverse;
        }}

        #prompt .text-area--cursor-line {{
            background: {theme.color_terminal_default};
        }}

        #autocomplete {{
            height: {autocomplete_box_height};
            min-height: {autocomplete_box_height};
            max-height: {autocomplete_box_height};
            margin: 0 {theme.horizontal_padding} 0 {theme.horizontal_padding};
            padding: 0 1;
            border: round {theme.color_prompt_border};
            background: {theme.color_terminal_default};
            color: {theme.color_text_secondary};
            overflow: hidden;
        }}

        #runs-table {{
            height: auto;
            width: 100%;
            padding: 0 0 0 0;
            border: round {theme.color_prompt_border};
            background: {theme.color_terminal_default};
            color: {theme.color_text_secondary};
            overflow: hidden;
            scrollbar-size: 0 0;
            scrollbar-visibility: hidden;
        }}

        #runs-table > .datatable--header {{
            color: {theme.color_text_primary};
            background: {theme.color_terminal_default};
            padding-bottom: 1;
            text-style: bold;
        }}

        #runs-table > .datatable--cursor {{
            color: {theme.color_text_accent};
            background: {theme.color_terminal_default} 0%;
            text-style: bold;
        }}

        #footer {{
            height: 2;
            margin: {theme.footer_margin_top} {footer_margin_x} 0 {footer_margin_x};
            padding: 0 0 1 0;
            color: {theme.color_text_secondary};
            text-style: dim;
            background: {theme.color_terminal_default};
        }}

        #footer-left {{
            width: 1fr;
        }}

        #footer-right {{
            width: auto;
            text-align: right;
        }}

        #slash-autocomplete {{
            height: {autocomplete_box_height};
            max-height: {autocomplete_box_height};
            padding: 0 {theme.horizontal_padding} 0 {theme.horizontal_padding};
            background: {theme.color_terminal_default};
            color: {theme.color_text_primary};
        }}
        """
