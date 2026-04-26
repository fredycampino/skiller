from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from skiller.infrastructure.config.settings import Settings


@dataclass(frozen=True)
class CloudflaredLoginStartResult:
    authenticated: bool
    started: bool
    running: bool
    pid: int | None
    home: str
    cert_path: str
    log_path: str


@dataclass(frozen=True)
class CloudflaredLoginStatusResult:
    authenticated: bool
    running: bool
    pid: int | None
    home: str
    cert_path: str
    log_path: str


@dataclass(frozen=True)
class CloudflaredLoginStopResult:
    authenticated: bool
    stopped: bool
    running: bool
    pid: int | None
    home: str
    cert_path: str
    log_path: str


class CloudflaredLoginService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start(self) -> CloudflaredLoginStartResult:
        authenticated = self._is_authenticated()
        if authenticated:
            self._clear_login_state()
            return CloudflaredLoginStartResult(
                authenticated=True,
                started=False,
                running=False,
                pid=None,
                home=str(self._home_dir()),
                cert_path=str(self._cert_path()),
                log_path=str(self._log_file()),
            )

        managed_pid = self._read_login_pid()
        if managed_pid is not None:
            if self._is_expected_login_process(managed_pid):
                return CloudflaredLoginStartResult(
                    authenticated=False,
                    started=False,
                    running=True,
                    pid=managed_pid,
                    home=str(self._home_dir()),
                    cert_path=str(self._cert_path()),
                    log_path=str(self._log_file()),
                )
            self._clear_login_state()

        self._state_dir().mkdir(parents=True, exist_ok=True)
        log_handle = self._log_file().open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(  # noqa: S603
                ["cloudflared", "tunnel", "login"],
                env=self._command_env(),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()

        if process.poll() is not None:
            details = self._read_log_tail() or (
                f"cloudflared login exited with code {process.returncode}"
            )
            raise RuntimeError(details)

        self._write_login_state(process.pid)
        return CloudflaredLoginStartResult(
            authenticated=False,
            started=True,
            running=True,
            pid=process.pid,
            home=str(self._home_dir()),
            cert_path=str(self._cert_path()),
            log_path=str(self._log_file()),
        )

    def status(self) -> CloudflaredLoginStatusResult:
        authenticated = self._is_authenticated()
        managed_pid = self._read_login_pid()
        if managed_pid is not None and not self._is_expected_login_process(managed_pid):
            self._clear_login_state()
            managed_pid = None

        if authenticated and managed_pid is None:
            self._clear_login_state()

        return CloudflaredLoginStatusResult(
            authenticated=authenticated,
            running=managed_pid is not None,
            pid=managed_pid,
            home=str(self._home_dir()),
            cert_path=str(self._cert_path()),
            log_path=str(self._log_file()),
        )

    def stop(self) -> CloudflaredLoginStopResult:
        authenticated = self._is_authenticated()
        managed_pid = self._read_login_pid()
        if managed_pid is None:
            return CloudflaredLoginStopResult(
                authenticated=authenticated,
                stopped=False,
                running=False,
                pid=None,
                home=str(self._home_dir()),
                cert_path=str(self._cert_path()),
                log_path=str(self._log_file()),
            )

        if not self._is_expected_login_process(managed_pid):
            self._clear_login_state()
            return CloudflaredLoginStopResult(
                authenticated=authenticated,
                stopped=False,
                running=False,
                pid=None,
                home=str(self._home_dir()),
                cert_path=str(self._cert_path()),
                log_path=str(self._log_file()),
            )

        os.kill(managed_pid, signal.SIGTERM)
        self._wait_until_stopped(managed_pid)
        self._clear_login_state()
        return CloudflaredLoginStopResult(
            authenticated=authenticated,
            stopped=True,
            running=False,
            pid=managed_pid,
            home=str(self._home_dir()),
            cert_path=str(self._cert_path()),
            log_path=str(self._log_file()),
        )

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        debug_home = env.get("SKILLER_DEBUG_HOME", "").strip()
        if debug_home:
            Path(debug_home).mkdir(parents=True, exist_ok=True)
            env["HOME"] = debug_home
        return env

    def _home_dir(self) -> Path:
        return Path(self._command_env().get("HOME", str(Path.home()))).expanduser()

    def _cert_path(self) -> Path:
        return self._home_dir() / ".cloudflared" / "cert.pem"

    def _state_dir(self) -> Path:
        return self._home_dir() / ".skiller" / "cloudflared"

    def _login_state_file(self) -> Path:
        return self._state_dir() / "login.json"

    def _log_file(self) -> Path:
        return self._state_dir() / "login.log"

    def _write_login_state(self, pid: int) -> None:
        payload = {
            "pid": pid,
            "home": str(self._home_dir()),
            "cert_path": str(self._cert_path()),
            "log_path": str(self._log_file()),
        }
        self._login_state_file().write_text(json.dumps(payload), encoding="utf-8")

    def _read_login_pid(self) -> int | None:
        state_file = self._login_state_file()
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
        return raw_pid

    def _clear_login_state(self) -> None:
        state_file = self._login_state_file()
        if state_file.exists():
            state_file.unlink()

    def _read_log_tail(self, max_chars: int = 4000) -> str:
        log_file = self._log_file()
        if not log_file.exists():
            return ""
        try:
            raw = log_file.read_text(encoding="utf-8")
        except OSError:
            return ""
        return raw[-max_chars:].strip()

    def _is_authenticated(self) -> bool:
        if self._cert_path().exists():
            return True
        result = subprocess.run(
            ["cloudflared", "tunnel", "list", "--output", "json"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            env=self._command_env(),
        )
        return result.returncode == 0

    def _is_expected_login_process(self, pid: int) -> bool:
        if not self._is_pid_alive(pid):
            return False
        args = self._read_process_args(pid)
        if args is None:
            return False
        normalized = f" {args} "
        return "cloudflared" in args and " tunnel " in normalized and " login" in args

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

    def _wait_until_stopped(self, pid: int) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self._is_expected_login_process(pid):
                return
            time.sleep(0.2)
        raise RuntimeError(f"cloudflared login process did not stop cleanly: pid={pid}")

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
