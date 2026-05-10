class AgentFinalMessageExtractor:
    def extract_final_message(self, *, step_id: str, content: str | None) -> str:
        if content is None:
            raise ValueError(f"Agent step '{step_id}' returned no final answer")

        final_message = content.strip()
        if not final_message:
            raise ValueError(f"Agent step '{step_id}' returned no final answer")
        return final_message
