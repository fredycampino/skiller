from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from skiller.infrastructure.config.settings import Settings


@dataclass(frozen=True)
class WebhookProcessStartResult:
    endpoint: str
    pid: int | None
    started: bool
    running: bool
    managed: bool


@dataclass(frozen=True)
class WebhookProcessStatusResult:
    endpoint: str
    pid: int | None
    running: bool
    managed: bool


@dataclass(frozen=True)
class WebhookProcessStopResult:
    endpoint: str
    pid: int | None
    running: bool
    stopped: bool
    managed: bool


class WebhookProcessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> WebhookProcessStartResult:
        endpoint = self._health_endpoint()
        managed_pid = self._read_managed_pid()
        if managed_pid is not None and not self._is_expected_server_process(managed_pid):
            self._clear_managed_pid()
            managed_pid = None

        if self._is_endpoint_ready(endpoint):
            return WebhookProcessStartResult(
                endpoint=endpoint,
                pid=managed_pid,
                started=False,
                running=True,
                managed=managed_pid is not None,
            )

        process = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "skiller.local.server"],
            env=self._command_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_until_ready(endpoint, process)
        self._write_managed_pid(process.pid)
        return WebhookProcessStartResult(
            endpoint=endpoint,
            pid=process.pid,
            started=True,
            running=True,
            managed=True,
        )

    def status(self) -> WebhookProcessStatusResult:
        endpoint = self._health_endpoint()
        pid = self._read_managed_pid()
        running = self._is_endpoint_ready(endpoint)
        managed = pid is not None
        if pid is not None and not self._is_expected_server_process(pid):
            self._clear_managed_pid()
            pid = None
            managed = False
        return WebhookProcessStatusResult(
            endpoint=endpoint,
            pid=pid,
            running=running,
            managed=managed,
        )

    def stop(self) -> WebhookProcessStopResult:
        endpoint = self._health_endpoint()
        pid = self._read_managed_pid()
        if pid is None:
            return WebhookProcessStopResult(
                endpoint=endpoint,
                pid=None,
                running=self._is_endpoint_ready(endpoint),
                stopped=False,
                managed=False,
            )

        if not self._is_expected_server_process(pid):
            self._clear_managed_pid()
            return WebhookProcessStopResult(
                endpoint=endpoint,
                pid=None,
                running=self._is_endpoint_ready(endpoint),
                stopped=False,
                managed=False,
            )

        os.kill(pid, signal.SIGTERM)
        self._wait_until_stopped(endpoint, pid)
        self._clear_managed_pid()
        return WebhookProcessStopResult(
            endpoint=endpoint,
            pid=pid,
            running=False,
            stopped=True,
            managed=True,
        )

    def _health_endpoint(self) -> str:
        return f"http://{self.settings.webhooks_host}:{self.settings.webhooks_port}/health"

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        debug_home = env.get("SKILLER_DEBUG_HOME", "").strip()
        if debug_home:
            Path(debug_home).mkdir(parents=True, exist_ok=True)
            env["HOME"] = debug_home
        return env

    def _home_dir(self) -> Path:
        return Path(self._command_env().get("HOME", str(Path.home()))).expanduser()

    def _state_dir(self) -> Path:
        return self._home_dir() / ".skiller" / "webhooks"

    def _pid_file(self) -> Path:
        return self._state_dir() / f"managed-{self.settings.webhooks_port}.json"

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
                    f"server process exited with code {process.returncode} before becoming ready"
                )
            if self._is_endpoint_ready(endpoint):
                return
            time.sleep(0.2)
        raise RuntimeError(f"server process did not become ready: {endpoint}")

    def _wait_until_stopped(self, endpoint: str, pid: int) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self._is_pid_alive(pid) and not self._is_endpoint_ready(endpoint):
                return
            time.sleep(0.2)
        raise RuntimeError(f"server process did not stop cleanly: pid={pid}")

    def _write_managed_pid(self, pid: int) -> None:
        payload = {
            "pid": pid,
            "endpoint": self._health_endpoint(),
        }
        pid_file = self._pid_file()
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(json.dumps(payload), encoding="utf-8")

    def _read_managed_pid(self) -> int | None:
        pid_file = self._pid_file()
        if not pid_file.exists():
            return None
        raw = pid_file.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            try:
                return int(raw)
            except ValueError:
                return None
        if not isinstance(payload, dict):
            return None
        raw_pid = payload.get("pid")
        if not isinstance(raw_pid, int):
            return None
        if payload.get("endpoint") != self._health_endpoint():
            return None
        return raw_pid

    def _clear_managed_pid(self) -> None:
        pid_file = self._pid_file()
        if pid_file.exists():
            pid_file.unlink()

    def _is_expected_server_process(self, pid: int) -> bool:
        if not self._is_pid_alive(pid):
            return False
        args = self._read_process_args(pid)
        if args is None:
            return False
        normalized = f" {args} "
        return (
            sys.executable in args
            and " -m " in normalized
            and "skiller.local.server" in args
        )

    def _read_process_args(self, pid: int) -> str | None:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        args = (result.stdout or "").strip()
        return args or None

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
