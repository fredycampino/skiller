from dataclasses import dataclass
import os
from pathlib import Path


_DOTENV_LOADED = False


@dataclass(frozen=True)
class Settings:
    db_path: str = "./runtime.db"
    llm_provider: str = "null"
    fake_llm_response_json: str = '{"summary":"fake summary","severity":"low","next_action":"retry"}'
    fake_llm_model: str = "fake-llm"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_model: str = "MiniMax-M2.5"
    minimax_timeout_seconds: float = 30.0
    log_level: str = "INFO"
    webhooks_host: str = "127.0.0.1"
    webhooks_port: int = 8001


def _maybe_load_dotenv() -> None:
    global _DOTENV_LOADED

    if _DOTENV_LOADED:
        return

    dotenv_path = Path(".env")
    if not dotenv_path.exists():
        _DOTENV_LOADED = True
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        env_key = key.strip()
        if not env_key or env_key in os.environ:
            continue

        env_value = value.strip()
        if len(env_value) >= 2 and env_value[0] == env_value[-1] and env_value[0] in {'"', "'"}:
            env_value = env_value[1:-1]

        os.environ[env_key] = env_value

    _DOTENV_LOADED = True


def get_settings() -> Settings:
    _maybe_load_dotenv()

    return Settings(
        db_path=os.getenv("AGENT_DB_PATH", "./runtime.db"),
        llm_provider=os.getenv("AGENT_LLM_PROVIDER", "null"),
        fake_llm_response_json=os.getenv(
            "AGENT_FAKE_LLM_RESPONSE_JSON",
            '{"summary":"fake summary","severity":"low","next_action":"retry"}',
        ),
        fake_llm_model=os.getenv("AGENT_FAKE_LLM_MODEL", "fake-llm"),
        minimax_api_key=os.getenv("AGENT_MINIMAX_API_KEY", ""),
        minimax_base_url=os.getenv("AGENT_MINIMAX_BASE_URL", "https://api.minimax.io/v1"),
        minimax_model=os.getenv("AGENT_MINIMAX_MODEL", "MiniMax-M2.5"),
        minimax_timeout_seconds=float(os.getenv("AGENT_MINIMAX_TIMEOUT_SECONDS", "30")),
        log_level=os.getenv("AGENT_LOG_LEVEL", "INFO"),
        webhooks_host=os.getenv("AGENT_WEBHOOKS_HOST", "127.0.0.1"),
        webhooks_port=int(os.getenv("AGENT_WEBHOOKS_PORT", "8001")),
    )
