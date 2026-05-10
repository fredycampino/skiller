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
class CloudflaredProcessStartResult:
    origin_url: str
    pid: int | None
    started: bool
    running: bool
    managed: bool
    tunnel_name: str


@dataclass(frozen=True)
class CloudflaredProcessStatusResult:
    origin_url: str
    pid: int | None
    running: bool
    managed: bool
    tunnel_name: str


@dataclass(frozen=True)
class CloudflaredProcessStopResult:
    origin_url: str
    pid: int | None
    running: bool
    stopped: bool
    managed: bool
    tunnel_name: str


class CloudflaredProcessService:
    def __init__(self, settings: Settings, *, tunnel_name: str = "skillerwh") -> None:
        self.settings = settings
        self.tunnel_name = tunnel_name

    def start(self) -> CloudflaredProcessStartResult:
        origin_url = self._origin_url()
        managed_pid = self._read_managed_pid()
        if managed_pid is not None:
            if self._is_managed_process(pid=managed_pid, origin_url=origin_url):
                return CloudflaredProcessStartResult(
                    origin_url=origin_url,
                    pid=managed_pid,
                    started=False,
                    running=True,
                    managed=True,
                    tunnel_name=self.tunnel_name,
                )
            self._clear_managed_pid()

        external_pid = self._find_matching_pid(origin_url=origin_url)
        if external_pid is not None:
            return CloudflaredProcessStartResult(
                origin_url=origin_url,
                pid=external_pid,
                started=False,
                running=True,
                managed=False,
                    tunnel_name=self.tunnel_name,
                )

        run_command = self._build_run_command(origin_url=origin_url)
        process = subprocess.Popen(  # noqa: S603
            run_command,
            env=self._command_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_until_started(process.pid, process, origin_url=origin_url)
        self._write_managed_pid(process.pid)
        return CloudflaredProcessStartResult(
            origin_url=origin_url,
            pid=process.pid,
            started=True,
            running=True,
            managed=True,
            tunnel_name=self.tunnel_name,
        )

    def status(self) -> CloudflaredProcessStatusResult:
        origin_url = self._origin_url()
        managed_pid = self._read_managed_pid()
        if managed_pid is not None:
            if self._is_managed_process(pid=managed_pid, origin_url=origin_url):
                return CloudflaredProcessStatusResult(
                    origin_url=origin_url,
                    pid=managed_pid,
                    running=True,
                    managed=True,
                    tunnel_name=self.tunnel_name,
                )
            self._clear_managed_pid()

        external_pid = self._find_matching_pid(origin_url=origin_url)
        return CloudflaredProcessStatusResult(
            origin_url=origin_url,
            pid=external_pid,
            running=external_pid is not None,
            managed=False,
            tunnel_name=self.tunnel_name,
        )

    def stop(self) -> CloudflaredProcessStopResult:
        origin_url = self._origin_url()
        managed_pid = self._read_managed_pid()
        if managed_pid is None:
            external_pid = self._find_matching_pid(origin_url=origin_url)
            return CloudflaredProcessStopResult(
                origin_url=origin_url,
                pid=external_pid,
                running=external_pid is not None,
                stopped=False,
                managed=False,
                tunnel_name=self.tunnel_name,
            )

        if not self._is_managed_process(pid=managed_pid, origin_url=origin_url):
            self._clear_managed_pid()
            external_pid = self._find_matching_pid(origin_url=origin_url)
            return CloudflaredProcessStopResult(
                origin_url=origin_url,
                pid=external_pid,
                running=external_pid is not None,
                stopped=False,
                managed=False,
                tunnel_name=self.tunnel_name,
            )

        os.kill(managed_pid, signal.SIGTERM)
        self._wait_until_stopped(managed_pid, origin_url=origin_url)
        self._clear_managed_pid()
        return CloudflaredProcessStopResult(
            origin_url=origin_url,
            pid=managed_pid,
            running=False,
            stopped=True,
            managed=True,
            tunnel_name=self.tunnel_name,
        )

    def _origin_url(self) -> str:
        return f"http://{self.settings.webhooks_host}:{self.settings.webhooks_port}"

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        debug_home = env.get("SKILLER_DEBUG_HOME", "").strip()
        if debug_home:
            Path(debug_home).mkdir(parents=True, exist_ok=True)
            env["HOME"] = debug_home
        return env

    def _pid_file(self) -> Path:
        return self._state_dir() / f"managed-{self.settings.webhooks_port}.json"

    def _state_dir(self) -> Path:
        home = Path(self._command_env().get("HOME", str(Path.home()))).expanduser()
        return home / ".skiller" / "cloudflared"

    def _write_managed_pid(self, pid: int) -> None:
        payload = {
            "pid": pid,
            "origin_url": self._origin_url(),
            "tunnel_name": self.tunnel_name,
        }
        self._state_dir().mkdir(parents=True, exist_ok=True)
        self._pid_file().write_text(json.dumps(payload), encoding="utf-8")

    def _read_managed_pid(self) -> int | None:
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
        if payload.get("origin_url") != self._origin_url():
            return None
        if payload.get("tunnel_name") != self.tunnel_name:
            return None
        return raw_pid

    def _clear_managed_pid(self) -> None:
        pid_file = self._pid_file()
        if pid_file.exists():
            pid_file.unlink()

    def _find_matching_pid(self, *, origin_url: str) -> int | None:
        for pid, args in self._list_processes():
            if self._matches_external_command(args=args, origin_url=origin_url):
                return pid
        return None

    def _build_run_command(self, *, origin_url: str) -> list[str]:
        tunnel_id = self._find_tunnel_id()
        tunnel_ref = tunnel_id or self.tunnel_name
        config_path = self._config_path()
        if config_path.exists():
            credentials_path = self._credentials_path_for(tunnel_ref)
            if credentials_path.exists():
                return [
                    "cloudflared",
                    "tunnel",
                    "--config",
                    str(config_path),
                    "run",
                ]

            tunnel_token = self._fetch_tunnel_token(tunnel_ref)
            return [
                "cloudflared",
                "tunnel",
                "--config",
                str(config_path),
                "run",
                "--token",
                tunnel_token,
            ]

        credentials_path = self._credentials_path_for(tunnel_ref)
        if credentials_path.exists():
            return [
                "cloudflared",
                "tunnel",
                "--url",
                origin_url,
                "run",
                tunnel_ref,
            ]

        tunnel_token = self._fetch_tunnel_token(tunnel_ref)
        return [
            "cloudflared",
            "tunnel",
            "--url",
            origin_url,
            "run",
            "--token",
            tunnel_token,
        ]

    def _find_tunnel_id(self) -> str:
        result = subprocess.run(
            ["cloudflared", "tunnel", "list", "--output", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=self._command_env(),
        )
        raw_output = (result.stdout or "") + (result.stderr or "")
        start = raw_output.find("[")
        if result.returncode != 0 or start == -1:
            return ""
        try:
            tunnels, _ = json.JSONDecoder().raw_decode(raw_output[start:])
        except json.JSONDecodeError:
            return ""
        if not isinstance(tunnels, list):
            return ""
        for item in tunnels:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            tunnel_id = str(item.get("id", "")).strip()
            if name.lower() == self.tunnel_name.lower() and tunnel_id:
                return tunnel_id
        return ""

    def _credentials_path_for(self, tunnel_ref: str) -> Path:
        home = Path(self._command_env().get("HOME", str(Path.home()))).expanduser()
        return home / ".cloudflared" / f"{tunnel_ref}.json"

    def _fetch_tunnel_token(self, tunnel_ref: str) -> str:
        result = subprocess.run(
            ["cloudflared", "tunnel", "token", tunnel_ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=self._command_env(),
        )
        raw_output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if result.returncode != 0:
            raise RuntimeError(
                raw_output
                or f"cloudflared tunnel token failed for {self.tunnel_name}"
            )
        tunnel_token = (result.stdout or "").strip()
        if not tunnel_token:
            raise RuntimeError(
                f"cloudflared tunnel token returned an empty token for {tunnel_ref}"
            )
        return tunnel_token

    def _list_processes(self) -> list[tuple[int, str]]:
        result = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip() or "ps command failed"
            raise RuntimeError(details)

        processes: list[tuple[int, str]] = []
        for raw_line in (result.stdout or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            pid_text, _, args = line.partition(" ")
            if not pid_text or not args:
                continue
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            processes.append((pid, args.strip()))
        return processes

    def _is_managed_process(self, *, pid: int, origin_url: str) -> bool:
        if not self._is_pid_alive(pid):
            return False
        args = self._read_process_args(pid)
        if args is None:
            return False
        return self._matches_managed_command(args=args, origin_url=origin_url)

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

    def _matches_external_command(self, *, args: str, origin_url: str) -> bool:
        normalized = f" {args} "
        return (
            "cloudflared" in args
            and " tunnel " in normalized
            and " run " in normalized
            and (
                (origin_url in args and self.tunnel_name in args)
                or str(self._config_path()) in args
            )
        )

    def _matches_managed_command(self, *, args: str, origin_url: str) -> bool:
        normalized = f" {args} "
        return (
            "cloudflared" in args
            and " tunnel " in normalized
            and " run " in normalized
            and (origin_url in args or str(self._config_path()) in args)
        )

    def _config_path(self) -> Path:
        home = Path(self._command_env().get("HOME", str(Path.home()))).expanduser()
        return home / ".cloudflared" / f"{self.tunnel_name}-config.yml"

    def _wait_until_started(
        self,
        pid: int,
        process: subprocess.Popen[bytes],
        *,
        origin_url: str,
    ) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    "cloudflared process exited with code "
                    f"{process.returncode} before becoming ready"
                )
            if self._is_managed_process(pid=pid, origin_url=origin_url):
                return
            time.sleep(0.2)
        raise RuntimeError(f"cloudflared process did not become ready: pid={pid}")

    def _wait_until_stopped(self, pid: int, *, origin_url: str) -> None:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not self._is_managed_process(pid=pid, origin_url=origin_url):
                return
            time.sleep(0.2)
        raise RuntimeError(f"cloudflared process did not stop cleanly: pid={pid}")

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
