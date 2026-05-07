import pytest

from skiller.application.agent.prompt.final_message_extractor import (
    AgentFinalMessageExtractor,
)

pytestmark = pytest.mark.unit


def test_agent_final_message_extractor_extracts_final_message_from_plain_content() -> None:
    extractor = AgentFinalMessageExtractor()

    final_text = extractor.extract_final_message(
        step_id="support_agent",
        content="Hello back.",
    )

    assert final_text == "Hello back."


def test_agent_final_message_extractor_rejects_empty_content() -> None:
    extractor = AgentFinalMessageExtractor()

    with pytest.raises(ValueError, match="returned no final answer"):
        extractor.extract_final_message(step_id="support_agent", content="   ")
