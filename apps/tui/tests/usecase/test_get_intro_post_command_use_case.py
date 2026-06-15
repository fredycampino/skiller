from __future__ import annotations

import pytest

from stui.usecase.get_intro_post_command_use_case import GetIntroPostCommandUseCase
from stui.usecase.normalize_command_use_case import CommandKind

pytestmark = pytest.mark.unit


def test_get_intro_post_command_returns_onboarding_intro_run_command() -> None:
    result = GetIntroPostCommandUseCase().execute()

    assert result.command.kind == CommandKind.RUN
    assert result.command.name == "/run"
    assert result.command.raw_text == "/run onboarding/intro"
    assert result.command.args_text == "onboarding/intro"
