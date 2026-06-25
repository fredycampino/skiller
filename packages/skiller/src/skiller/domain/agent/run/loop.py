from dataclasses import dataclass


@dataclass
class AgentLoop:
    max_turns: int
    turn_count: int = 0

    def has_next(self) -> bool:
        return self.turn_count < self.max_turns

    def is_last_turn(self) -> bool:
        return self.max_turns - self.turn_count == 1

    def advance(self) -> None:
        self.turn_count += 1
