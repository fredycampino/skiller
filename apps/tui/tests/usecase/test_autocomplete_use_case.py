from __future__ import annotations

import pytest

from stui.di.strings import TuiStrings
from stui.usecase.autocomplete_use_case import AutocompleteUseCase

pytestmark = pytest.mark.unit


def test_autocomplete_use_case_builds_completion_state_for_slash_prefix() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/ru", cursor_position=3)

    assert state is not None
    assert state.visible is True
    assert state.query == "/ru"
    assert [item.label for item in state.items] == ["run", "runs"]
    assert state.items[0].description == "Run an agentic flow"
    assert state.selected_index == 0
    assert state.replace_from == 0
    assert state.replace_to == 3


def test_autocomplete_use_case_hides_exact_command_match() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/run", cursor_position=4)

    assert state is not None
    assert [item.label for item in state.items] == ["runs"]


def test_autocomplete_use_case_hides_non_matching_queries() -> None:
    use_case = AutocompleteUseCase()

    assert use_case.execute(text="/xzx", cursor_position=4) is None


def test_autocomplete_use_case_hides_run_queries_with_whitespace() -> None:
    use_case = AutocompleteUseCase()

    assert use_case.execute(text="/run chat", cursor_position=9) is None


def test_autocomplete_use_case_does_not_suggest_legacy_chat_commands() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/ch", cursor_position=3)

    assert state is None


def test_autocomplete_use_case_lists_all_supported_commands_for_slash() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/", cursor_position=1)

    assert state is not None
    assert [item.label for item in state.items] == [
        "run",
        "runs",
        "auth",
        "models",
        "quit",
        "exit",
        "dev",
    ]


def test_autocomplete_use_case_suggests_auth_command() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/a", cursor_position=2)

    assert state is not None
    assert [item.label for item in state.items] == ["auth"]
    assert state.items[0].description == "Configure authentication"
    assert state.items[0].insert_text == "/auth "


def test_autocomplete_use_case_suggests_auth_provider_params() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/auth ", cursor_position=6)

    assert state is not None
    assert state.query == ""
    assert [item.label for item in state.items] == ["codex", "minimax", "bedrock"]
    assert [item.kind for item in state.items] == ["param", "param", "param"]
    assert state.replace_from == 6
    assert state.replace_to == 6


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("/auth c", "codex"),
        ("/auth m", "minimax"),
        ("/auth b", "bedrock"),
    ],
)
def test_autocomplete_use_case_filters_auth_provider_params(
    text: str,
    label: str,
) -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text=text, cursor_position=len(text))

    assert state is not None
    assert [item.label for item in state.items] == [label]
    assert state.replace_from == 6
    assert state.replace_to == len(text)


def test_autocomplete_use_case_hides_completed_auth_provider_param() -> None:
    use_case = AutocompleteUseCase()

    assert use_case.execute(text="/auth codex", cursor_position=11) is None


def test_autocomplete_use_case_hides_auth_provider_after_extra_space() -> None:
    use_case = AutocompleteUseCase()

    assert use_case.execute(text="/auth codex ", cursor_position=12) is None


def test_autocomplete_use_case_does_not_suggest_auth_params_for_partial_auth_command() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/a", cursor_position=2)

    assert state is not None
    assert [item.label for item in state.items] == ["auth"]
    assert state.replace_from == 0
    assert state.replace_to == 2


def test_autocomplete_use_case_suggests_exit_command() -> None:
    use_case = AutocompleteUseCase()

    state = use_case.execute(text="/e", cursor_position=2)

    assert state is not None
    assert [item.label for item in state.items] == ["exit"]


def test_autocomplete_use_case_uses_strings_for_run_description() -> None:
    use_case = AutocompleteUseCase(
        strings=TuiStrings(autocomplete_run_description="Run a custom flow")
    )

    state = use_case.execute(text="/ru", cursor_position=3)

    assert state is not None
    assert state.items[0].description == "Run a custom flow"
