from __future__ import annotations

from skiller.tools.ui.commands import get_canonical_command_names


def get_command_completion_prefix(text_before_cursor: str) -> str | None:
    normalized = text_before_cursor.lstrip()
    if not normalized.startswith("/"):
        return None
    if "\n" in normalized:
        return None
    if any(character.isspace() for character in normalized):
        return None
    return normalized


def get_command_suggestions(prefix: str) -> list[str]:
    command_suggestions = get_canonical_command_names()
    normalized = prefix.strip().lower()
    if not normalized:
        return command_suggestions
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return [command for command in command_suggestions if command.startswith(normalized)]


def build_prompt_toolkit_completer():  # noqa: ANN201
    try:
        from prompt_toolkit.completion import Completer, Completion
    except ImportError as exc:  # pragma: no cover - exercised through fallback tests
        raise RuntimeError("prompt_toolkit is not installed") from exc

    class SlashCommandCompleter(Completer):
        def get_completions(self, document, complete_event):  # noqa: ANN001, ANN202
            _ = complete_event
            command_prefix = get_command_completion_prefix(document.text_before_cursor)
            if command_prefix is None:
                return

            for command in get_command_suggestions(command_prefix):
                yield Completion(command, start_position=-len(command_prefix))

    return SlashCommandCompleter()
