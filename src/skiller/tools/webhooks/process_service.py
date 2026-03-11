from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

from skiller.infrastructure.config.settings import Settings


@dataclass(frozen=True)
class WebhookProcessStartResult:
    endpoint: str
    pid: int | None
    started: bool


class WebhookProcessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> WebhookProcessStartResult:
        endpoint = self._health_endpoint()
        if self._is_endpoint_ready(endpoint):
            return WebhookProcessStartResult(endpoint=endpoint, pid=None, started=False)

        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "skiller.tools.webhooks"],
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_until_ready(endpoint, process)
        return WebhookProcessStartResult(endpoint=endpoint, pid=process.pid, started=True)

    def _health_endpoint(self) -> str:
        return f"http://{self.settings.webhooks_host}:{self.settings.webhooks_port}/health"

    def _is_endpoint_ready(self, endpoint: str) -> bool:
        try:
            with urlopen(endpoint, timeout=0.5) as response:  # noqa: S310
                return response.status == 200
        except (URLError, TimeoutError, ValueError):
            return False

    def _wait_until_ready(self, endpoint: str, process: subprocess.Popen[bytes]) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"webhooks process exited with code {process.returncode} before becoming ready"
                )
            if self._is_endpoint_ready(endpoint):
                return
            time.sleep(0.2)
        raise RuntimeError(f"webhooks process did not become ready: {endpoint}")
