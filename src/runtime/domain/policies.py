from typing import Any


class PolicyGate:
    def authorize(self, _skill_name: str, _step: dict[str, Any]) -> bool:
        # Paso 0: estrategia mínima, permitir todo.
        return True
