from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from skiller.infrastructure.config.settings import Settings
from skiller.local.channels.whatsapp.pair_service import WhatsAppPairService
from skiller.local.server.process_service import WebhookProcessService


@dataclass(frozen=True)
class WhatsAppProcessStartResult:
    endpoint: str
    pid: int | None
    started: bool
    running: bool
    managed: bool
    paired: bool
    state: str
    qr_count: int
    queue_length: int
    session_path: str


@dataclass(frozen=True)
class WhatsAppProcessStatusResult:
    endpoint: str
    pid: int | None
    running: bool
    managed: bool
    paired: bool
    state: str
    qr_count: int
    queue_length: int
    session_path: str


@dataclass(frozen=True)
class WhatsAppProcessStopResult:
    endpoint: str
    pid: int | None
    running: bool
    stopped: bool
    managed: bool
    paired: bool
    state: str
    qr_count: int
    queue_length: int
    session_path: str


class WhatsAppProcessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> WhatsAppProcessStartResult:
        self._ensure_bridge_requirements()
        if not self._is_paired():
            raise RuntimeError("WhatsApp session is not paired. Run 'skiller whatsapp pair start'.")

        WebhookProcessService(self.settings).start()
        self._write_channel_token()

        endpoint = self._health_endpoint()
        managed_state = self._read_managed_state()
        if managed_state is not None:
            managed_pid = int(managed_state["pid"])
            if self._is_expected_service_process(managed_pid):
                return self._build_start_result(
                    endpoint=endpoint,
                    pid=managed_pid,
                    started=False,
                    managed=True,
                )
            self._clear_managed_state()

        process = subprocess.Popen(  # noqa: S603
            [
                "node",
                str(self._bridge_script()),
                "--session",
                str(self._session_dir()),
                "--runtime-state-file",
                str(self._runtime_state_file()),
                "--port",
                str(self.settings.whatsapp_bridge_port),
                "--channel-target-base",
                self._channel_target_base(),
                "--channel-token",
                self._read_channel_token(),
            ],
            cwd=str(self._bridge_script().parent),
            env=self._command_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self._wait_until_ready(endpoint, process)
        self._write_managed_state(process.pid)
        return self._build_start_result(
            endpoint=endpoint,
            pid=process.pid,
            started=True,
            managed=True,
        )

    def status(self) -> WhatsAppProcessStatusResult:
        endpoint = self._health_endpoint()
        managed_state = self._read_managed_state()
        pid: int | None = None
        managed = False
        if managed_state is not None:
            candidate_pid = int(managed_state["pid"])
            if self._is_expected_service_process(candidate_pid):
                pid = candidate_pid
                managed = True
            else:
                self._clear_managed_state()

        return self._build_status_result(endpoint=endpoint, pid=pid, managed=managed)

    def stop(self) -> WhatsAppProcessStopResult:
        endpoint = self._health_endpoint()
        managed_state = self._read_managed_state()
        if managed_state is None:
            return self._build_stop_result(
                endpoint=endpoint,
                pid=None,
                stopped=False,
                managed=False,
            )

        pid = int(managed_state["pid"])
        if not self._is_expected_service_process(pid):
            self._clear_managed_state()
            return self._build_stop_result(
                endpoint=endpoint,
                pid=None,
                stopped=False,
                managed=False,
            )

        self._stop_process_group(pid)
        self._wait_until_stopped(endpoint, pid)
        self._clear_managed_state()
        return self._build_stop_result(
            endpoint=endpoint,
            pid=pid,
            stopped=True,
            managed=True,
        )

    def _ensure_bridge_requirements(self) -> None:
        WhatsAppPairService(self.settings)._ensure_bridge_requirements()

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
        return self._home_dir() / ".skiller" / "whatsapp"

    def _session_dir(self) -> Path:
        return self._state_dir() / "session"

    def _runtime_state_file(self) -> Path:
        return self._state_dir() / "bridge-runtime.json"

    def _channel_token_file(self) -> Path:
        return self._state_dir() / f"channel-token-{self.settings.whatsapp_bridge_port}.txt"

    def _pid_file(self) -> Path:
        return self._state_dir() / f"managed-{self.settings.whatsapp_bridge_port}.json"

    def _bridge_script(self) -> Path:
        return Path(__file__).resolve().parent / "bridge" / "bridge.js"

    def _health_endpoint(self) -> str:
        return (
            f"http://{self.settings.whatsapp_bridge_host}:{self.settings.whatsapp_bridge_port}/health"
        )

    def _channel_target_base(self) -> str:
        return (
            f"http://{self.settings.webhooks_host}:{self.settings.webhooks_port}/channels/whatsapp"
        )

    def _build_start_result(
        self,
        *,
        endpoint: str,
        pid: int | None,
        started: bool,
        managed: bool,
    ) -> WhatsAppProcessStartResult:
        health = self._read_health()
        return WhatsAppProcessStartResult(
            endpoint=endpoint,
            pid=pid,
            started=started,
            running=self._is_running(health),
            managed=managed,
            paired=self._is_paired(),
            state=self._health_state(health),
            qr_count=self._health_qr_count(health),
            queue_length=self._health_queue_length(health),
            session_path=str(self._session_dir()),
        )

    def _build_status_result(
        self,
        *,
        endpoint: str,
        pid: int | None,
        managed: bool,
    ) -> WhatsAppProcessStatusResult:
        health = self._read_health()
        return WhatsAppProcessStatusResult(
            endpoint=endpoint,
            pid=pid,
            running=self._is_running(health),
            managed=managed,
            paired=self._is_paired(),
            state=self._health_state(health),
            qr_count=self._health_qr_count(health),
            queue_length=self._health_queue_length(health),
            session_path=str(self._session_dir()),
        )

    def _build_stop_result(
        self,
        *,
        endpoint: str,
        pid: int | None,
        stopped: bool,
        managed: bool,
    ) -> WhatsAppProcessStopResult:
        if stopped:
            return WhatsAppProcessStopResult(
                endpoint=endpoint,
                pid=pid,
                running=False,
                stopped=True,
                managed=managed,
                paired=self._is_paired(),
                state="stopped",
                qr_count=0,
                queue_length=0,
                session_path=str(self._session_dir()),
            )

        health = self._read_health()
        return WhatsAppProcessStopResult(
            endpoint=endpoint,
            pid=pid,
            running=self._is_running(health),
            stopped=False,
            managed=managed,
            paired=self._is_paired(),
            state=self._health_state(health),
            qr_count=self._health_qr_count(health),
            queue_length=self._health_queue_length(health),
            session_path=str(self._session_dir()),
        )

    def _is_running(self, health: dict[str, object] | None) -> bool:
        return health is not None and WebhookProcessService(self.settings).status().running

    def _write_managed_state(self, pid: int) -> None:
        payload = {
            "pid": pid,
            "endpoint": self._health_endpoint(),
            "session_path": str(self._session_dir()),
        }
        self._state_dir().mkdir(parents=True, exist_ok=True)
        self._pid_file().write_text(json.dumps(payload), encoding="utf-8")

    def _read_managed_state(self) -> dict[str, object] | None:
        pid_file = self._pid_file()
        if not pid_file.exists():
            return None
        try:
            payload = json.loads(pid_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        raw_pid = payload.get("pid")
        if not isinstance(raw_pid, int):
            return None
        if payload.get("endpoint") != self._health_endpoint():
            return None
        if payload.get("session_path") != str(self._session_dir()):
            return None
        return payload

    def _clear_managed_state(self) -> None:
        pid_file = self._pid_file()
        if pid_file.exists():
            pid_file.unlink()

    def _is_paired(self) -> bool:
        return (self._session_dir() / "creds.json").exists()

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

    def _is_expected_service_process(self, pid: int) -> bool:
        if not self._is_pid_alive(pid):
            return False
        args = self._read_process_args(pid)
        if args is None:
            return False
        return (
            "node" in args
            and str(self._bridge_script()) in args
            and str(self._session_dir()) in args
            and str(self.settings.whatsapp_bridge_port) in args
        )

    def _read_health(self) -> dict[str, object] | None:
        try:
            with urlopen(self._health_endpoint(), timeout=0.5) as response:  # noqa: S310
                if response.status != 200:
                    return None
                raw = response.read().decode("utf-8")
        except (URLError, TimeoutError, ValueError):
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _health_state(self, health: dict[str, object] | None) -> str:
        if health is None:
            return "stopped"
        raw_state = health.get("status")
        if isinstance(raw_state, str) and raw_state.strip():
            return raw_state
        return "unknown"

    def _health_qr_count(self, health: dict[str, object] | None) -> int:
        if health is None:
            return 0
        raw_qr_count = health.get("qrCount")
        if isinstance(raw_qr_count, int):
            return raw_qr_count
        return 0

    def _health_queue_length(self, health: dict[str, object] | None) -> int:
        if health is None:
            return 0
        raw_queue_length = health.get("queueLength")
        if isinstance(raw_queue_length, int):
            return raw_queue_length
        return 0

    def _wait_until_ready(self, endpoint: str, process: subprocess.Popen[bytes]) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    "whatsapp bridge process exited with code "
                    f"{process.returncode} before becoming ready"
                )
            if self._is_running(self._read_health()):
                return
            time.sleep(0.2)
        raise RuntimeError(f"whatsapp service did not become ready: {endpoint}")

    def _wait_until_stopped(self, endpoint: str, pid: int) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self._is_pid_alive(pid) and self._read_health() is None:
                return
            time.sleep(0.2)
        raise RuntimeError(f"whatsapp service did not stop cleanly: pid={pid}")

    def _stop_process_group(self, pid: int) -> None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return

    def _write_channel_token(self) -> None:
        token_file = self._channel_token_file()
        if token_file.exists() and token_file.read_text(encoding="utf-8").strip():
            return
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(secrets.token_hex(16), encoding="utf-8")

    def _read_channel_token(self) -> str:
        token = self._channel_token_file().read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError("whatsapp channel token is not configured")
        return token
