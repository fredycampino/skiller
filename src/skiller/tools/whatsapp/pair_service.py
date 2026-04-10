from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from skiller.infrastructure.config.settings import Settings


@dataclass(frozen=True)
class WhatsAppPairStartResult:
    paired: bool
    started: bool
    running: bool
    pid: int | None
    state: str
    qr_count: int
    home: str
    session_path: str
    log_path: str


@dataclass(frozen=True)
class WhatsAppPairStatusResult:
    paired: bool
    running: bool
    pid: int | None
    state: str
    qr_count: int
    home: str
    session_path: str
    log_path: str


@dataclass(frozen=True)
class WhatsAppPairStopResult:
    paired: bool
    stopped: bool
    running: bool
    pid: int | None
    state: str
    qr_count: int
    home: str
    session_path: str
    log_path: str


class WhatsAppPairService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> WhatsAppPairStartResult:
        paired = self._is_paired()
        if paired:
            self._clear_pair_state()
            return WhatsAppPairStartResult(
                paired=True,
                started=False,
                running=False,
                pid=None,
                state="paired",
                qr_count=0,
                home=str(self._home_dir()),
                session_path=str(self._session_dir()),
                log_path=str(self._log_file()),
            )

        managed_pid = self._read_pair_pid()
        if managed_pid is not None:
            if self._is_expected_pair_process(managed_pid):
                return WhatsAppPairStartResult(
                    paired=False,
                    started=False,
                    running=True,
                    pid=managed_pid,
                    state=self._runtime_state().get("state", "waiting_for_scan"),
                    qr_count=self._runtime_qr_count(),
                    home=str(self._home_dir()),
                    session_path=str(self._session_dir()),
                    log_path=str(self._log_file()),
                )
            self._clear_pair_state()

        self._ensure_bridge_requirements()
        pid, paired = self._run_pair_process_foreground(timeout_seconds=120.0)
        return WhatsAppPairStartResult(
            paired=paired,
            started=True,
            running=False,
            pid=pid,
            state="paired" if paired else "stopped",
            qr_count=self._runtime_qr_count(),
            home=str(self._home_dir()),
            session_path=str(self._session_dir()),
            log_path=str(self._log_file()),
        )

    def status(self) -> WhatsAppPairStatusResult:
        paired = self._is_paired()
        managed_pid = self._read_pair_pid()
        if managed_pid is not None and not self._is_expected_pair_process(managed_pid):
            self._clear_pair_state()
            managed_pid = None

        if paired and managed_pid is None:
            self._clear_pair_state()

        return WhatsAppPairStatusResult(
            paired=paired,
            running=managed_pid is not None,
            pid=managed_pid,
            state=self._status_state(paired=paired, running=managed_pid is not None),
            qr_count=self._runtime_qr_count(),
            home=str(self._home_dir()),
            session_path=str(self._session_dir()),
            log_path=str(self._log_file()),
        )

    def stop(self) -> WhatsAppPairStopResult:
        paired = self._is_paired()
        managed_pid = self._read_pair_pid()
        if managed_pid is None:
            return WhatsAppPairStopResult(
                paired=paired,
                stopped=False,
                running=False,
                pid=None,
                state="paired" if paired else "stopped",
                qr_count=self._runtime_qr_count(),
                home=str(self._home_dir()),
                session_path=str(self._session_dir()),
                log_path=str(self._log_file()),
            )

        if not self._is_expected_pair_process(managed_pid):
            self._clear_pair_state()
            return WhatsAppPairStopResult(
                paired=paired,
                stopped=False,
                running=False,
                pid=None,
                state="paired" if paired else "stopped",
                qr_count=self._runtime_qr_count(),
                home=str(self._home_dir()),
                session_path=str(self._session_dir()),
                log_path=str(self._log_file()),
            )

        self._stop_process_group(managed_pid)
        self._clear_pair_state()
        return WhatsAppPairStopResult(
            paired=paired,
            stopped=True,
            running=False,
            pid=managed_pid,
            state="paired" if paired else "stopped",
            qr_count=self._runtime_qr_count(),
            home=str(self._home_dir()),
            session_path=str(self._session_dir()),
            log_path=str(self._log_file()),
        )

    def _run_pair_process_foreground(self, *, timeout_seconds: float) -> tuple[int, bool]:
        self._state_dir().mkdir(parents=True, exist_ok=True)
        self._session_dir().mkdir(parents=True, exist_ok=True)

        with self._log_file().open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(  # noqa: S603
                [
                    "node",
                    str(self._bridge_script()),
                    "--session",
                    str(self._session_dir()),
                    "--runtime-state-file",
                    str(self._runtime_state_file()),
                    "--pair-only",
                ],
                cwd=str(self._bridge_dir()),
                env=self._command_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            self._write_pair_state(process.pid)

            try:
                try:
                    self._stream_process_output(
                        process=process,
                        log_handle=log_handle,
                        timeout_seconds=timeout_seconds,
                    )
                except KeyboardInterrupt as exc:
                    self._stop_process_group(process.pid)
                    raise RuntimeError("WhatsApp pairing cancelled by user") from exc
            finally:
                self._clear_pair_state()

        paired = self._is_paired()
        if process.returncode == 0 and paired:
            return process.pid, True
        if process.returncode == 0:
            raise RuntimeError("WhatsApp pairing exited without saving session credentials")

        details = self._read_log_tail() or (
            f"whatsapp pair process exited with code {process.returncode}"
        )
        raise RuntimeError(details)

    def _stream_process_output(
        self,
        *,
        process: subprocess.Popen[str],
        log_handle,
        timeout_seconds: float,
    ) -> None:
        if process.stdout is None:
            raise RuntimeError("WhatsApp pair process did not expose stdout")

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout_seconds

        while True:
            if time.monotonic() >= deadline:
                self._stop_process_group(process.pid)
                raise RuntimeError(
                    f"WhatsApp pairing timed out after {int(timeout_seconds)} seconds"
                )

            if process.poll() is not None:
                line = process.stdout.readline()
                if line:
                    log_handle.write(line)
                    log_handle.flush()
                    print(line, end="", flush=True)
                    continue
                return

            events = selector.select(timeout=0.5)
            if not events:
                continue

            for key, _ in events:
                line = key.fileobj.readline()
                if not line:
                    continue
                log_handle.write(line)
                log_handle.flush()
                print(line, end="", flush=True)

    def _ensure_bridge_requirements(self) -> None:
        if not self._bridge_script().exists():
            raise RuntimeError(f"WhatsApp bridge script not found: {self._bridge_script()}")

        try:
            result = subprocess.run(
                ["node", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Node.js is required for WhatsApp pairing") from exc
        if result.returncode != 0:
            raise RuntimeError("Node.js is required for WhatsApp pairing")

        if self._has_required_bridge_modules():
            return

        try:
            install_result = subprocess.run(
                ["npm", "install", "--silent"],
                cwd=str(self._bridge_dir()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("npm is required to install WhatsApp bridge dependencies") from exc
        if install_result.returncode != 0:
            detail = (install_result.stderr or install_result.stdout).strip()
            raise RuntimeError(detail or "npm install failed for WhatsApp bridge")

    def _has_required_bridge_modules(self) -> bool:
        node_modules = self._bridge_dir() / "node_modules"
        required_paths = [
            node_modules / "@whiskeysockets" / "baileys",
            node_modules / "express",
            node_modules / "pino",
            node_modules / "qrcode-terminal",
        ]
        return all(path.exists() for path in required_paths)

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        debug_home = env.get("SKILLER_DEBUG_HOME", "").strip()
        if debug_home:
            Path(debug_home).mkdir(parents=True, exist_ok=True)
            env["HOME"] = debug_home
        return env

    def _home_dir(self) -> Path:
        return Path(self._command_env().get("HOME", str(Path.home()))).expanduser()

    def _session_dir(self) -> Path:
        return self._state_dir() / "session"

    def _state_dir(self) -> Path:
        return self._home_dir() / ".skiller" / "whatsapp"

    def _pair_state_file(self) -> Path:
        return self._state_dir() / "pair.json"

    def _runtime_state_file(self) -> Path:
        return self._state_dir() / "pair-runtime.json"

    def _log_file(self) -> Path:
        return self._state_dir() / "pair.log"

    def _bridge_dir(self) -> Path:
        return Path(__file__).resolve().parent / "bridge"

    def _bridge_script(self) -> Path:
        return self._bridge_dir() / "bridge.js"

    def _write_pair_state(self, pid: int) -> None:
        payload = {
            "pid": pid,
            "home": str(self._home_dir()),
            "session_path": str(self._session_dir()),
            "log_path": str(self._log_file()),
        }
        self._pair_state_file().write_text(json.dumps(payload), encoding="utf-8")

    def _read_pair_pid(self) -> int | None:
        state_file = self._pair_state_file()
        if not state_file.exists():
            return None
        try:
            payload = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        raw_pid = payload.get("pid")
        if not isinstance(raw_pid, int):
            return None
        if payload.get("home") != str(self._home_dir()):
            return None
        if payload.get("session_path") != str(self._session_dir()):
            return None
        return raw_pid

    def _clear_pair_state(self) -> None:
        state_file = self._pair_state_file()
        if state_file.exists():
            state_file.unlink()

    def _runtime_state(self) -> dict[str, object]:
        state_file = self._runtime_state_file()
        if not state_file.exists():
            return {}
        try:
            payload = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _runtime_qr_count(self) -> int:
        raw_qr_count = self._runtime_state().get("qr_count")
        if isinstance(raw_qr_count, int):
            return raw_qr_count
        return 0

    def _status_state(self, *, paired: bool, running: bool) -> str:
        if paired:
            return "paired"
        if running:
            runtime_state = self._runtime_state().get("state")
            if isinstance(runtime_state, str) and runtime_state.strip():
                return runtime_state
            return "waiting_for_scan"
        return "stopped"

    def _read_log_tail(self, max_chars: int = 4000) -> str:
        log_file = self._log_file()
        if not log_file.exists():
            return ""
        try:
            raw = log_file.read_text(encoding="utf-8")
        except OSError:
            return ""
        return raw[-max_chars:].strip()

    def _is_paired(self) -> bool:
        return (self._session_dir() / "creds.json").exists()

    def _is_expected_pair_process(self, pid: int) -> bool:
        if not self._is_pid_alive(pid):
            return False
        args = self._read_process_args(pid)
        if args is None:
            return False
        return (
            "node" in args
            and str(self._bridge_script()) in args
            and "--pair-only" in args
            and str(self._session_dir()) in args
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

    def _terminate_process_group(self, pid: int) -> None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return

    def _kill_process_group(self, pid: int) -> None:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return

    def _wait_until_stopped(self, pid: int) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self._is_pid_alive(pid):
                return
            time.sleep(0.2)
        raise RuntimeError(f"whatsapp pair process did not stop cleanly: pid={pid}")

    def _stop_process_group(self, pid: int) -> None:
        self._terminate_process_group(pid)
        try:
            self._wait_until_stopped(pid)
            return
        except RuntimeError:
            self._kill_process_group(pid)
        self._wait_until_stopped(pid)

    def _wait_until_stopped(self, pid: int) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self._is_pid_alive(pid):
                return
            time.sleep(0.2)
        raise RuntimeError(f"whatsapp pair process did not stop cleanly: pid={pid}")
