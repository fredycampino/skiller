from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from skiller.infrastructure.config.settings import Settings
from skiller.local.tunnels.cloudflared.login_service import CloudflaredLoginService


@dataclass(frozen=True)
class CloudflaredEnsureResult:
    authenticated: bool
    tunnel_name: str
    tunnel_id: str
    hostname: str
    created: bool
    dns_status: str
    config_path: str
    home: str


class CloudflaredEnsureService:
    def __init__(self, settings: Settings, *, tunnel_name: str = "skillerwh") -> None:
        self.settings = settings
        self.tunnel_name = tunnel_name

    def ensure(self, *, domain: str) -> CloudflaredEnsureResult:
        normalized_domain = domain.strip()
        if not normalized_domain:
            raise ValueError("domain is required")

        login_status = CloudflaredLoginService(self.settings).status()
        if not login_status.authenticated:
            raise RuntimeError("cloudflared login is required")

        hostname = f"{self.tunnel_name}.{normalized_domain}"
        tunnel = self._find_tunnel()
        created = False
        if tunnel is None:
            tunnel = self._create_tunnel()
            created = True

        dns_status = self._ensure_dns_route(tunnel_id=tunnel["id"], hostname=hostname)
        config_path = self._write_tunnel_config(
            tunnel_id=tunnel["id"],
            hostname=hostname,
        )
        return CloudflaredEnsureResult(
            authenticated=True,
            tunnel_name=self.tunnel_name,
            tunnel_id=tunnel["id"],
            hostname=hostname,
            created=created,
            dns_status=dns_status,
            config_path=str(config_path),
            home=str(self._home_dir()),
        )

    def _find_tunnel(self) -> dict[str, str] | None:
        tunnels = self._list_tunnels()
        for item in tunnels:
            name = str(item.get("name", "")).strip()
            tunnel_id = str(item.get("id", "")).strip()
            if name.lower() != self.tunnel_name.lower() or not tunnel_id:
                continue
            return {"id": tunnel_id, "name": name}
        return None

    def _list_tunnels(self) -> list[dict[str, object]]:
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
            details = raw_output.strip() or "cloudflared tunnel list failed"
            raise RuntimeError(details)
        try:
            tunnels, _ = json.JSONDecoder().raw_decode(raw_output[start:])
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                raw_output.strip() or "cloudflared tunnel list returned invalid JSON"
            ) from exc
        if not isinstance(tunnels, list):
            raise RuntimeError("cloudflared tunnel list returned invalid payload")
        return [item for item in tunnels if isinstance(item, dict)]

    def _create_tunnel(self) -> dict[str, str]:
        result = subprocess.run(
            ["cloudflared", "tunnel", "create", self.tunnel_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=self._command_env(),
        )
        raw_output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if result.returncode != 0:
            details = raw_output or f"cloudflared tunnel create {self.tunnel_name} failed"
            raise RuntimeError(details)

        tunnel = self._find_tunnel()
        if tunnel is not None:
            return tunnel

        match = re.search(
            r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
            raw_output,
            flags=re.IGNORECASE,
        )
        if match is None:
            raise RuntimeError(
                raw_output
                or f"cloudflared tunnel create {self.tunnel_name} did not return a tunnel id"
            )
        return {"id": match.group(1), "name": self.tunnel_name}

    def _ensure_dns_route(self, *, tunnel_id: str, hostname: str) -> str:
        result = subprocess.run(
            ["cloudflared", "tunnel", "route", "dns", tunnel_id, hostname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            env=self._command_env(),
        )
        raw_output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if result.returncode == 0:
            return "created"

        lowered = raw_output.lower()
        if "already exists" in lowered or "record already exists" in lowered:
            validation_status = self._validate_existing_dns_route(
                tunnel_id=tunnel_id,
                hostname=hostname,
            )
            return validation_status

        details = raw_output or f"cloudflared tunnel route dns failed for {hostname}"
        raise RuntimeError(details)

    def _validate_existing_dns_route(self, *, tunnel_id: str, hostname: str) -> str:
        expected_target = f"{tunnel_id}.cfargotunnel.com"
        try:
            actual_targets = self._lookup_cname_targets(hostname)
        except RuntimeError:
            return "already_exists_unvalidated"

        normalized_expected = self._normalize_dns_target(expected_target)
        normalized_actual = [self._normalize_dns_target(item) for item in actual_targets]
        if normalized_expected in normalized_actual:
            return "already_exists"

        actual_text = ", ".join(actual_targets) if actual_targets else "(no CNAME answer)"
        raise RuntimeError(
            f"{hostname} already exists but points to {actual_text} instead of {expected_target}"
        )

    def _lookup_cname_targets(self, hostname: str) -> list[str]:
        query = urlencode({"name": hostname, "type": "CNAME"})
        request = Request(
            f"https://cloudflare-dns.com/dns-query?{query}",
            headers={"accept": "application/dns-json"},
        )
        try:
            with urlopen(request, timeout=5.0) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"DNS lookup failed for {hostname}") from exc

        answers = payload.get("Answer")
        if not isinstance(answers, list):
            return []

        targets: list[str] = []
        for item in answers:
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if not isinstance(data, str):
                continue
            targets.append(data.strip())
        return targets

    def _normalize_dns_target(self, target: str) -> str:
        return target.strip().rstrip(".").lower()

    def _write_tunnel_config(self, *, tunnel_id: str, hostname: str) -> Path:
        config_path = self._config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            f"tunnel: {tunnel_id}",
        ]
        credentials_path = self._credentials_path_for(tunnel_id)
        if credentials_path.exists():
            lines.append(f"credentials-file: {credentials_path}")
        lines.extend(
            [
                "",
                "ingress:",
                f"  - hostname: {hostname}",
                f"    service: {self._origin_url()}",
                "  - service: http_status:404",
                "",
            ]
        )
        config_path.write_text("\n".join(lines), encoding="utf-8")
        return config_path

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        debug_home = env.get("SKILLER_DEBUG_HOME", "").strip()
        if debug_home:
            Path(debug_home).mkdir(parents=True, exist_ok=True)
            env["HOME"] = debug_home
        return env

    def _home_dir(self) -> Path:
        return Path(self._command_env().get("HOME", str(Path.home()))).expanduser()

    def _origin_url(self) -> str:
        return f"http://{self.settings.webhooks_host}:{self.settings.webhooks_port}"

    def _credentials_path_for(self, tunnel_ref: str) -> Path:
        return self._home_dir() / ".cloudflared" / f"{tunnel_ref}.json"

    def _config_path(self) -> Path:
        return self._home_dir() / ".cloudflared" / f"{self.tunnel_name}-config.yml"
