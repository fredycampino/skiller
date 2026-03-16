from __future__ import annotations

import json
import os
import shutil

import pytest

from skiller.domain.mcp_config_model import RenderedMcpConfig
from skiller.infrastructure.tools.mcp.client import MCPClientTool

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def stub_mcp_calls() -> None:
    """Override tests/conftest.py autouse fixture for this module."""
    return None


def _require_opt_in() -> None:
    if os.getenv("RUN_CHROME_MCP_TEST") != "1":
        pytest.skip("Set RUN_CHROME_MCP_TEST=1 to run chrome-mcp integration test")


def _has_browser(extra_env: dict[str, str]) -> bool:
    env_browser = (
        extra_env.get("CHROME_PATH")
        or extra_env.get("CHROME_BIN")
        or os.getenv("CHROME_PATH")
        or os.getenv("CHROME_BIN")
    )
    if env_browser:
        return True

    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
    ]
    return any(shutil.which(candidate) for candidate in candidates)


def _build_chrome_mcp_config() -> RenderedMcpConfig:
    if shutil.which("npx") is None and not os.getenv("CHROME_MCP_COMMAND"):
        pytest.fail("npx not found. Install Node.js/npm or set CHROME_MCP_COMMAND")

    command = os.getenv("CHROME_MCP_COMMAND", "npx")

    raw_args = os.getenv("CHROME_MCP_ARGS")
    if raw_args:
        args = json.loads(raw_args)
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError("CHROME_MCP_ARGS must be a JSON array of strings")
    else:
        args = ["-y", "chrome-mcp@latest"]

    extra_env: dict[str, str] = {"CHROME_HEADLESS": "true"}
    raw_env = os.getenv("CHROME_MCP_ENV")
    if raw_env:
        parsed_env = json.loads(raw_env)
        if not isinstance(parsed_env, dict):
            raise ValueError("CHROME_MCP_ENV must be a JSON object")
        for key, value in parsed_env.items():
            extra_env[str(key)] = str(value)

    if not _has_browser(extra_env):
        pytest.fail(
            "No Chrome/Chromium found. Set CHROME_PATH/CHROME_BIN "
            "or install a browser to run chrome-mcp integration"
        )

    cwd = os.getenv("CHROME_MCP_CWD")
    return RenderedMcpConfig(
        name="chrome-mcp",
        transport="stdio",
        command=command,
        args=args,
        cwd=cwd,
        env=extra_env,
    )


def test_chrome_mcp_probe_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_opt_in()
    config = _build_chrome_mcp_config()

    result = MCPClientTool().probe_server("chrome-mcp", config=config)

    assert result["ok"] is True, (
        f"chrome-mcp probe failed: {result}. "
        "Tip: set CHROME_MCP_ARGS/CHROME_MCP_ENV and ensure Chrome is reachable in headless mode."
    )
    assert result["server"] == "chrome-mcp"
    assert str(result.get("endpoint", "")).startswith("stdio://")
    assert isinstance(result.get("tools_count"), int)
    assert result["tools_count"] > 0
