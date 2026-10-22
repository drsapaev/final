"""Windows entry point for an isolated, task-owned WSL staging session.

Never prints resolved Compose config, environment values or container logs.
Session keeps an open WSL stdin for the entire validation command; closing
the pipe releases the keeper even when the Windows parent is interrupted.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
IS_WINDOWS = os.name == "nt"
GIB = 1024**3
BUILD_RESERVE_GIB = 10
RUN_RESERVE_GIB = 2
PORT_KEYS = {
    "backend": ("STAGING_BACKEND_PORT", 18001, 18000),
    "frontend": ("STAGING_FRONTEND_PORT", 18080, 80),
    "postgres": ("STAGING_POSTGRES_HOST_PORT", 55432, 5432),
}
PUBLIC_ORIGIN_KEYS = (
    "STAGING_PUBLIC_HOST",
    "STAGING_PUBLIC_BASE_URL",
    "STAGING_PUBLIC_WS_URL",
    "STAGING_PUBLIC_WS_HOST",
    "CORS_ORIGINS",
)
LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}
LOOPBACK_BIND_IP = "127.0.0.1"
INSPECT = (
    '{"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
    '"lifecycle":{{json (index .Config.Labels "clinic.lifecycle")}},'
    '"owner":{{json (index .Config.Labels "clinic.owner")}},'
    '"expires_at":{{json (index .Config.Labels "clinic.expires_at")}},'
    '"root":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
    '"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},'
    '"mounts":{{json .Mounts}},"ports":{{json .NetworkSettings.Ports}},'
    '"host_port_bindings":{{json .HostConfig.PortBindings}},'
    '"image":{{json .Image}},'
    '"status":{{json .State.Status}},'
    '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}'
)


class GuardError(RuntimeError):
    """Only safe, fixed diagnostic messages belong here."""


def windows_distro_base_path(distribution: str) -> str:
    """Read registration without invoking WSL (which could boot a full VHD)."""
    try:
        import winreg

        matches = []
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Lxss",
        ) as registrations:
            for index in range(winreg.QueryInfoKey(registrations)[0]):
                with winreg.OpenKey(
                    registrations, winreg.EnumKey(registrations, index)
                ) as registered:
                    name = winreg.QueryValueEx(registered, "DistributionName")[0]
                    if not isinstance(name, str):
                        raise TypeError
                    if name.casefold() == distribution.casefold():
                        matches.append(winreg.QueryValueEx(registered, "BasePath")[0])
        if len(matches) != 1 or not isinstance(matches[0], str):
            raise ValueError
        base_path = matches[0]
        base_path = base_path.removeprefix("\\\\?\\")
        path = PureWindowsPath(base_path)
        if (
            not path.is_absolute()
            or not re.fullmatch(r"[A-Za-z]:", path.drive)
            or any(char in base_path for char in ("\0", "\r", "\n", "%"))
        ):
            raise ValueError
        return str(path)
    except (ImportError, OSError, ValueError, TypeError):
        raise GuardError(
            "WSL_STORAGE_UNKNOWN: selected distro needs one local absolute registered BasePath; verify its VHD location"
        ) from None


def native(argv: list[str], *, timeout: int = 30, operation: str = "native") -> str:
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise GuardError(
            f"NATIVE_UNAVAILABLE ({operation}): command missing or timed out; no mutation continued"
        ) from None
    if result.returncode:
        # Native stderr can contain expanded secrets. Do not echo it or argv.
        raise GuardError(
            f"NATIVE_FAILED ({operation}): exit {result.returncode}; no subsequent command continued"
        )
    data = result.stdout
    return data.decode(
        "utf-16-le" if b"\0" in data else "utf-8", errors="replace"
    ).strip()


def tcp_ready(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def validate_windows_listeners(ports: dict[str, int]) -> None:
    # Only validated integers enter this fixed script. No env, paths or secrets.
    selected = ",".join(str(p) for p in ports.values())
    script = (
        "$ErrorActionPreference='Stop'; $selected=@(" + selected + "); "
        "@(Get-NetTCPConnection -State Listen -ErrorAction Stop | "
        "Where-Object { $_.LocalPort -in $selected } | ForEach-Object { "
        "$owner=Get-Process -Id $_.OwningProcess -ErrorAction Stop; "
        "[pscustomobject]@{port=$_.LocalPort; process=$owner.ProcessName} "
        "}) | ConvertTo-Json -Compress"
    )
    raw = native(
        ["powershell.exe", "-NoProfile", "-Command", script],
        operation="windows-listeners",
    )
    listeners = json.loads(raw) if raw else []
    if isinstance(listeners, dict):
        listeners = [listeners]
    if any(
        item.get("process", "").lower() not in {"wslrelay", "wslhost"}
        for item in listeners
    ):
        raise GuardError(
            "WINDOWS_PORT_OWNER: a native or ambiguous Windows listener shadows staging; preserve it"
        )


def local_file(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise GuardError("PATH_OUTSIDE_WORKTREE: use a file in this worktree")
    return path


def context_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise GuardError(
            "ENV_MISSING: prepare an ignored synthetic staging env in this worktree"
        )
    keys = {
        "COMPOSE_PROJECT_NAME",
        "CLINIC_LIFECYCLE",
        "CLINIC_OWNER",
        "CLINIC_EXPIRES_AT",
        *(v[0] for v in PORT_KEYS.values()),
        *PUBLIC_ORIGIN_KEYS,
    }
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^\s*([A-Z_]+)\s*=\s*(.*?)\s*$", line)
        if not match or match[1] not in keys:
            continue
        if match[1] in values:
            raise GuardError("ENV_DUPLICATE: context keys must be unique")
        value = match[2]
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            tail = value[end + 1 :].strip()
            if end < 0 or (tail and not tail.startswith("#")):
                raise GuardError(
                    "ENV_CONTEXT_INVALID: use literal project and numeric ports"
                )
            value = value[1:end]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        values[match[1]] = value
    if not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{1,62}", values.get("COMPOSE_PROJECT_NAME", "")
    ):
        raise GuardError(
            "PROJECT_REQUIRED: set an explicit unique COMPOSE_PROJECT_NAME"
        )
    return values


def validate_public_origins(values: dict[str, str], frontend_port: int) -> None:
    """Reject stale public/client origins before a staging runtime action."""
    if any(not values.get(key) for key in PUBLIC_ORIGIN_KEYS):
        raise GuardError(
            "PUBLIC_ORIGIN_REQUIRED: configure every staging public origin explicitly"
        )

    public_host = values["STAGING_PUBLIC_HOST"].casefold()
    if public_host not in LOOPBACK_HOSTS:
        raise GuardError("PUBLIC_HOST_INVALID: staging public host must be loopback")

    def origin_parts(value: str, scheme: str, *, allow_root_path: bool):
        if any(char in value for char in "\r\n\t"):
            return None
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError:
            return None
        allowed_paths = ("", "/") if allow_root_path else ("",)
        host = parsed.hostname.casefold() if parsed.hostname else None
        if (
            parsed.scheme.casefold() != scheme
            or host not in LOOPBACK_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in allowed_paths
            or parsed.query
            or parsed.fragment
            or "?" in value
            or "#" in value
        ):
            return None
        return host, port

    def require_public_origin(key: str, scheme: str) -> None:
        parts = origin_parts(values[key], scheme, allow_root_path=True)
        if parts is None:
            raise GuardError("PUBLIC_ORIGIN_INVALID: staging origins must use loopback")
        host, port = parts
        if host != public_host or port != frontend_port:
            raise GuardError(
                "PUBLIC_ORIGIN_CONTEXT_MISMATCH: staging origins must match the frontend host and port"
            )

    require_public_origin("STAGING_PUBLIC_BASE_URL", "http")
    require_public_origin("STAGING_PUBLIC_WS_URL", "ws")

    try:
        ws_host = urlsplit("//" + values["STAGING_PUBLIC_WS_HOST"])
        ws_host_port = ws_host.port
    except ValueError:
        raise GuardError(
            "PUBLIC_ORIGIN_INVALID: WebSocket host must be host:port"
        ) from None
    parsed_ws_host = ws_host.hostname.casefold() if ws_host.hostname else None
    if (
        parsed_ws_host not in LOOPBACK_HOSTS
        or ws_host.username is not None
        or ws_host.password is not None
        or ws_host.path
        or ws_host.query
        or ws_host.fragment
        or any(
            char in values["STAGING_PUBLIC_WS_HOST"] for char in "\r\n\t/?#"
        )
    ):
        raise GuardError("PUBLIC_ORIGIN_INVALID: WebSocket host must be loopback host:port")
    if parsed_ws_host != public_host or ws_host_port != frontend_port:
        raise GuardError(
            "PUBLIC_ORIGIN_CONTEXT_MISMATCH: WebSocket host must match the frontend host and port"
        )

    cors_origins = values["CORS_ORIGINS"].split(",")
    if not cors_origins or any(not origin.strip() for origin in cors_origins):
        raise GuardError(
            "PUBLIC_ORIGIN_INVALID: CORS origins must be non-empty loopback origins"
        )
    for origin in cors_origins:
        parts = origin_parts(origin.strip(), "http", allow_root_path=False)
        if parts is None:
            raise GuardError("PUBLIC_ORIGIN_INVALID: CORS origins must use loopback")
        _, port = parts
        if port != frontend_port:
            raise GuardError(
                "PUBLIC_ORIGIN_CONTEXT_MISMATCH: CORS origins must match the frontend port"
            )


def effective_ports(
    config: dict,
    values: dict[str, str],
    linux_root: str,
    *,
    stop_recovery: bool = False,
) -> dict[str, int]:
    ports = {}
    for service, (key, default, target) in PORT_KEYS.items():
        declarations = config.get("services", {}).get(service, {}).get("ports", [])
        if len(declarations) != 1:
            raise GuardError(
                "PORT_SHAPE: expected one explicit binding for each staging service"
            )
        item = declarations[0]
        try:
            port = int(item["published"])
            expected = int(values.get(key, str(default)))
        except (KeyError, TypeError, ValueError):
            raise GuardError("PORT_INVALID: context ports must be numeric") from None
        if not 1024 <= port <= 65535 or port in {18000, 5173, 5432}:
            raise GuardError("PRODUCTION_PORT: unsafe staging port rejected")
        if (
            port != expected
            or int(item.get("target", 0)) != target
            or item.get("protocol", "tcp") != "tcp"
        ):
            raise GuardError(
                "PORT_CONTEXT_MISMATCH: resolved Compose ports differ from the selected env"
            )
        if not stop_recovery and item.get("host_ip") != LOOPBACK_BIND_IP:
            if service == "postgres":
                raise GuardError("POSTGRES_EXPOSED: PostgreSQL must bind to loopback")
            raise GuardError(
                "STAGING_PORT_EXPOSED: published staging services must bind to loopback"
            )
        ports[service] = port
    if len(set(ports.values())) != len(ports):
        raise GuardError("PORT_COLLISION: staging services must use distinct ports")
    for service in ("backend", "worker"):
        volumes = config.get("services", {}).get(service, {}).get("volumes", [])
        if not any(
            v.get("target") == "/app"
            and v.get("type") == "bind"
            and v.get("source") == linux_root + "/backend"
            for v in volumes
        ):
            raise GuardError(
                "SOURCE_MISMATCH: backend and worker must mount this worktree"
            )
    return ports


def validate_ownership(
    containers: list[dict],
    project: str,
    root: str,
    compose: str,
    ports: dict[str, int],
    *,
    enforce_port_bindings: bool = True,
) -> list[dict]:
    owned = []

    def validate_bindings(mapping: dict | None, service: str) -> None:
        expected_key = f"{PORT_KEYS[service][2]}/tcp"
        if not isinstance(mapping, dict) or set(mapping) != {expected_key}:
            raise GuardError(
                "PORT_CONTEXT_MISMATCH: expected the configured container TCP port"
            )
        bindings = mapping[expected_key]
        if not isinstance(bindings, list) or len(bindings) != 1:
            raise GuardError(
                "PORT_CONTEXT_MISMATCH: expected one published binding"
            )
        try:
            host_port = int(bindings[0]["HostPort"])
        except (KeyError, TypeError, ValueError):
            raise GuardError(
                "PORT_CONTEXT_MISMATCH: invalid published port"
            ) from None
        if host_port != ports[service]:
            raise GuardError(
                "PORT_CONTEXT_MISMATCH: existing project uses different ports"
            )
        if bindings[0].get("HostIp") != LOOPBACK_BIND_IP:
            raise GuardError(
                "STAGING_PORT_EXPOSED: existing staging services must bind to loopback"
            )

    for container in containers:
        if container.get("project") == project:
            if (
                container.get("root") != root + "/ops"
                or container.get("files") != compose
            ):
                raise GuardError(
                    "PROJECT_OWNERSHIP: project belongs to another worktree or Compose file"
                )
            if container.get("service") in {"backend", "worker"} and not any(
                m.get("Destination") == "/app" and m.get("Source") == root + "/backend"
                for m in container.get("mounts") or []
            ):
                raise GuardError(
                    "SOURCE_MISMATCH: existing container mounts different source"
                )
            service = container.get("service")
            if enforce_port_bindings and service in ports:
                # NetworkSettings.Ports reflects active publications and is empty
                # on stopped containers. HostConfig.PortBindings preserves the
                # configured binding in both states and is always authoritative
                # for a container that may be started again.
                validate_bindings(container.get("host_port_bindings"), service)
                if container.get("status") == "running":
                    validate_bindings(container.get("ports"), service)
            owned.append(container)
        elif enforce_port_bindings and container.get("status") == "running":
            bindings = [
                binding
                for group in (container.get("ports") or {}).values()
                for binding in (group or [])
            ]
            if any(int(binding["HostPort"]) in ports.values() for binding in bindings):
                raise GuardError(
                    "FOREIGN_PORT: a selected port belongs to another Docker project; preserve it"
                )
    return owned


def validate_pg_env(root: Path, name: str, port: int) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
        raise GuardError(
            "PG_ENV_INVALID: provide the test fixture's environment variable name"
        )
    dsn = os.environ.get(name, "")
    spec = importlib.util.spec_from_file_location(
        "staging_pg_guard", root / "backend/tests/_pg_admin_guard.py"
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        allowed = module.is_local_admin_dsn(dsn)
        parsed = urlsplit(dsn)
        keys = {k.lower() for k, _ in parse_qsl(parsed.query)}
        matches = (
            parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port == port
        )
    except (ImportError, OSError, ValueError, AttributeError):
        raise GuardError(
            "PG_GUARD_UNAVAILABLE: use a backend interpreter and an explicit local admin DSN"
        ) from None
    if (
        not allowed
        or not matches
        or parsed.scheme != "postgresql"
        or not parsed.path.strip("/")
        or keys & {"host", "hostaddr", "port", "service"}
    ):
        raise GuardError(
            "PG_TARGET_REJECTED: admin DSN must address this project's loopback PostgreSQL port"
        )


def pg_child_env(root: Path, name: str) -> dict[str, str]:
    """Pin every known fixture candidate; dotenv must not restore a fallback."""
    environment = dict(os.environ)
    pattern = re.compile(r"\b[A-Z][A-Z0-9_]*PG_ADMIN_(?:URL|DSN)\b")
    candidates = {key for key in environment if pattern.fullmatch(key)}
    for source in (root / "backend/tests").rglob("*.py"):
        candidates.update(pattern.findall(source.read_text(encoding="utf-8")))
    for candidate in candidates:
        environment[candidate] = ""
    environment["LOCAL_PG_SUPERUSER_PASSWORD"] = ""
    # A missing env key could be repopulated by load_dotenv(override=False).
    # An explicit DATABASE_URL also keeps app import on the selected server.
    environment["DATABASE_URL"] = (
        urlsplit(os.environ[name])._replace(scheme="postgresql+psycopg").geturl()
    )
    environment[name] = os.environ[name]
    return environment


def validate_junit(path: Path) -> int:
    try:
        document = ET.parse(path)
    except (OSError, ET.ParseError):
        raise GuardError(
            "PG_PROOF_MISSING: validation must produce a fresh JUnit report"
        ) from None
    cases = list(document.iter("testcase"))
    if not cases or any(
        case.find(tag) is not None
        for case in cases
        for tag in ("skipped", "failure", "error")
    ):
        raise GuardError(
            "PG_PROOF_INCOMPLETE: zero tests, skipped or failed cases are not PostgreSQL proof"
        )
    return len(cases)


def lifecycle_context(values: dict[str, str]) -> tuple[str, str, datetime]:
    """Require bounded ownership metadata before creating disposable resources."""
    lifecycle = values.get("CLINIC_LIFECYCLE", "ephemeral").strip()
    owner = values.get("CLINIC_OWNER", "").strip()
    expires_raw = values.get("CLINIC_EXPIRES_AT", "").strip()
    if lifecycle != "ephemeral":
        raise GuardError("LIFECYCLE_INVALID: staging must be labeled ephemeral")
    if (
        not owner
        or owner.casefold() in {"unknown", "none", "null"}
        or len(owner) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in owner)
    ):
        raise GuardError("LIFECYCLE_OWNER_REQUIRED: provide a specific staging owner")
    try:
        parsed = datetime.fromisoformat(
            expires_raw[:-1] + "+00:00" if expires_raw.endswith("Z") else expires_raw
        )
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
    except (TypeError, ValueError):
        raise GuardError(
            "LIFECYCLE_EXPIRY_REQUIRED: provide CLINIC_EXPIRES_AT as a timezone-aware ISO timestamp"
        ) from None
    expires_at = parsed.astimezone(UTC)
    if expires_at > datetime.now(UTC) + timedelta(days=7):
        raise GuardError(
            "LIFECYCLE_EXPIRY_TOO_FAR: staging lease must expire within seven days"
        )
    return owner, expires_raw, expires_at


class WslStaging:
    def __init__(self, root: Path, env_file: str, distribution: str):
        self.root = root.resolve()
        self.env_file = local_file(self.root, env_file)
        self.values = context_values(self.env_file)
        self.project = self.values["COMPOSE_PROJECT_NAME"]
        self.distribution = distribution
        self.compose = self.root / "ops/compose.staging.yml"
        self.ownership_verified = False
        self.cleanup_policy = None
        self.lifecycle_owner = None
        self.lifecycle_expires_at = None
        self.summary = {
            "project": self.project,
            "worktree": str(self.root),
            "distribution": distribution,
        }

    def wsl(self, *args: str, timeout: int = 30, operation: str = "wsl") -> str:
        return native(
            ["wsl.exe", "--distribution", self.distribution, "--exec", *args],
            timeout=timeout,
            operation=operation,
        )

    def docker(self, *args: str, timeout: int = 30, operation: str = "docker") -> str:
        # Clear ambient WSL env/Compose overrides and forbid a remote Docker context.
        return self.wsl(
            "env",
            "-i",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "COMPOSE_PARALLEL_LIMIT=1",
            "docker",
            "--host",
            "unix:///var/run/docker.sock",
            *args,
            timeout=timeout,
            operation=operation,
        )

    def compose_command(self, *args: str, timeout: int = 30) -> str:
        # Compose relative paths are anchored at ops/, where the canonical YAML lives.
        return self.docker(
            "compose",
            "--project-directory",
            self.linux_root + "/ops",
            "--project-name",
            self.project,
            "--env-file",
            self.linux_env,
            "-f",
            self.linux_compose,
            *args,
            timeout=timeout,
            operation="compose-" + args[0],
        )

    @contextmanager
    def keeper(self):
        try:
            process = subprocess.Popen(
                [
                    "wsl.exe",
                    "--distribution",
                    self.distribution,
                    "--exec",
                    "sh",
                    "-c",
                    "while IFS= read -r line; do :; done",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            raise GuardError(
                "WSL_UNAVAILABLE: install or select the WSL distro before staging"
            ) from None
        try:
            yield process
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)

    def boot_id(self) -> str:
        return self.wsl(
            "cat", "/proc/sys/kernel/random/boot_id", operation="wsl-boot-id"
        )

    def assert_session(self, keeper, boot: str) -> None:
        if keeper.poll() is not None or self.boot_id() != boot:
            raise GuardError(
                "WSL_INTERRUPTED: keeper ended or VM restarted; discard this run and rerun validation"
            )

    def containers(self) -> list[dict]:
        ids = self.docker("ps", "--all", "--quiet").split()
        if not ids:
            return []
        return [
            json.loads(line)
            for line in self.docker("inspect", "--format", INSPECT, *ids).splitlines()
        ]

    def project_resource_ids(self, kind: str) -> list[str]:
        selector = f"label=com.docker.compose.project={self.project}"
        if kind == "container":
            args = ("ps", "--all", "--quiet", "--filter", selector)
        elif kind in {"volume", "network"}:
            args = (kind, "ls", "--quiet", "--filter", selector)
        else:
            raise ValueError("unsupported Docker resource kind")
        return self.docker(*args).split()

    def resource_labels(self, kind: str, resource_id: str) -> dict:
        if kind not in {"volume", "network"}:
            raise ValueError("unsupported Docker resource kind")
        raw = self.docker(
            kind,
            "inspect",
            "--format",
            "{{json .Labels}}",
            resource_id,
        )
        try:
            labels = json.loads(raw)
        except (TypeError, ValueError):
            labels = None
        return labels if isinstance(labels, dict) else {}

    def validate_disposable_labels(self, labels: dict) -> None:
        if (
            labels.get("com.docker.compose.project") != self.project
            or labels.get("clinic.lifecycle") != "ephemeral"
            or labels.get("clinic.owner") != self.lifecycle_owner
            or labels.get("clinic.expires_at") != self.lifecycle_expires_at
        ):
            raise GuardError(
                "RESOURCE_LIFECYCLE_MISMATCH: refusing cleanup without matching ephemeral owner and expiry labels"
            )

    def validate_project_lifecycle_labels(self) -> dict[str, int]:
        owned = validate_ownership(
            self.containers(),
            self.project,
            self.linux_root,
            self.linux_compose,
            self.ports,
            enforce_port_bindings=False,
        )
        for container in owned:
            self.validate_disposable_labels(
                {
                    "com.docker.compose.project": container.get("project"),
                    "clinic.lifecycle": container.get("lifecycle"),
                    "clinic.owner": container.get("owner"),
                    "clinic.expires_at": container.get("expires_at"),
                }
            )

        counts = {"container": len(owned), "volume": 0, "network": 0}
        for kind in ("volume", "network"):
            ids = self.project_resource_ids(kind)
            counts[kind] = len(ids)
            for resource_id in ids:
                self.validate_disposable_labels(self.resource_labels(kind, resource_id))
        return counts

    def teardown_project(self, *, allow_keep: bool) -> str:
        """Remove and verify only this already-validated Compose project."""
        if not self.ownership_verified:
            raise GuardError("PROJECT_OWNERSHIP_UNVERIFIED: refusing staging teardown")
        if allow_keep and os.environ.get("KEEP_STAGING") == "1":
            self.summary["teardown"] = "SKIPPED_KEEP_STAGING"
            return "SKIPPED_KEEP_STAGING"
        if not self.lifecycle_owner or not self.lifecycle_expires_at:
            raise GuardError(
                "LIFECYCLE_UNVERIFIED: refusing staging teardown without owner and expiry"
            )

        before = self.validate_project_lifecycle_labels()

        self.compose_command(
            "down",
            "--volumes",
            "--remove-orphans",
            "--rmi",
            "local",
            timeout=300,
        )

        remaining = {
            kind: len(self.project_resource_ids(kind))
            for kind in ("container", "volume", "network")
        }
        if any(remaining.values()):
            raise GuardError(
                "STAGING_TEARDOWN_INCOMPLETE: project-scoped containers, volumes or networks remain"
            )
        self.summary["teardown"] = {
            "status": "PASS",
            "removed": before,
            "remaining": remaining,
            "local_images": "compose --rmi local",
        }
        return "PASS"

    def finish_after_failure(self, primary: BaseException, keeper, boot: str) -> None:
        if os.environ.get("KEEP_STAGING") == "1":
            self.summary["teardown"] = "SKIPPED_KEEP_STAGING"
            if isinstance(primary, GuardError):
                primary.args = (f"{primary}; STAGING_PRESERVED_KEEP_STAGING=1",)
                return
            raise GuardError(
                f"STAGING_FAILED: {type(primary).__name__}; STAGING_PRESERVED_KEEP_STAGING=1"
            ) from None
        try:
            self.assert_session(keeper, boot)
        except GuardError:
            self.summary["teardown"] = "NOT_RUN_WSL_SESSION_INTERRUPTED"
            if isinstance(primary, GuardError):
                primary.args = (
                    f"{primary}; STAGING_TEARDOWN_NOT_RUN: WSL session continuity was lost",
                )
                return
            raise GuardError(
                f"STAGING_FAILED: {type(primary).__name__}; STAGING_TEARDOWN_NOT_RUN: WSL session continuity was lost"
            ) from None
        try:
            outcome = self.teardown_project(allow_keep=True)
            self.assert_session(keeper, boot)
        except Exception as cleanup_error:  # noqa: BLE001 - preserve the primary failure and redact unknown errors
            self.summary["teardown"] = "FAIL"
            safe_cleanup_error = (
                str(cleanup_error)
                if isinstance(cleanup_error, GuardError)
                else f"STAGING_TEARDOWN_FAILED: {type(cleanup_error).__name__}"
            )
            if isinstance(primary, GuardError):
                primary.args = (f"{primary}; {safe_cleanup_error}",)
                return
            raise GuardError(
                f"STAGING_FAILED: {type(primary).__name__}; {safe_cleanup_error}"
            ) from None
        note = (
            "STAGING_PRESERVED_KEEP_STAGING=1"
            if outcome == "SKIPPED_KEEP_STAGING"
            else "STAGING_TEARDOWN=PASS"
        )
        if isinstance(primary, GuardError):
            primary.args = (f"{primary}; {note}",)
        elif isinstance(primary, Exception):
            raise GuardError(
                f"STAGING_FAILED: {type(primary).__name__}; {note}"
            ) from None

    def host_storage(self, *, build_possible: bool, recovery: bool = False) -> None:
        # The checkout and the sparse distro VHD can live on different volumes.
        # Non-Windows direct calls exist only for the mocked tooling tests.
        backing = (
            windows_distro_base_path(self.distribution) if IS_WINDOWS else str(self.root)
        )
        self.summary["wsl_backing_path"] = backing
        self.storage_recovery = recovery
        reserve = BUILD_RESERVE_GIB if build_possible else RUN_RESERVE_GIB
        self.summary["storage_reserve_gib"] = reserve
        if recovery:
            self.summary["storage_checks"] = "BYPASSED_FOR_OWNED_STOP"
            self.summary.pop("host_disk_free_gib", None)
            self.summary.pop("wsl_backing_disk_free_gib", None)
            return
        try:
            free = shutil.disk_usage(backing).free
        except OSError:
            raise GuardError(
                "WSL_STORAGE_UNKNOWN: selected distro backing storage cannot be measured; no WSL boot attempted"
            ) from None
        self.summary["wsl_backing_disk_free_gib"] = free // GIB
        if free < reserve * GIB:
            raise GuardError(
                f"WSL_BACKING_DISK_LOW: selected distro backing storage needs {reserve} GiB free; recover space before WSL boot"
            )
        try:
            worktree_free = shutil.disk_usage(self.root).free
        except OSError:
            raise GuardError(
                "HOST_STORAGE_UNKNOWN: worktree storage cannot be measured; no WSL boot attempted"
            ) from None
        self.summary["host_disk_free_gib"] = worktree_free // GIB
        if build_possible and worktree_free < RUN_RESERVE_GIB * GIB:
            raise GuardError(
                "DISK_LOW: fewer than 2 GiB available on the worktree drive; resolve before build"
            )

    def linux_storage(self, *, build_possible: bool) -> None:
        """Reject read-only/full virtual storage before Compose or the child."""
        reserve = BUILD_RESERVE_GIB if build_possible else RUN_RESERVE_GIB
        try:
            root = json.loads(self.docker("info", "--format", "{{json .DockerRootDir}}"))
        except (ValueError, TypeError):
            raise GuardError(
                "WSL_STORAGE_UNKNOWN: local Docker storage path cannot be verified"
            ) from None
        if (
            not isinstance(root, str)
            or not root.startswith("/")
            or any(char in root for char in ("\0", "\r", "\n"))
        ):
            raise GuardError("WSL_STORAGE_UNKNOWN: local Docker storage path is invalid")
        self.summary["wsl_storage"] = {}
        prefix = (
            "env",
            "-i",
            "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LC_ALL=C",
        )
        for path in dict.fromkeys(("/", root)):
            try:
                mounts = json.loads(
                    self.wsl(
                        *prefix, "findmnt", "--json", "--target", path,
                        "--output", "TARGET,OPTIONS", operation="wsl-storage-mount",
                    )
                )["filesystems"]
                if len(mounts) != 1:
                    raise ValueError
                target = mounts[0]["target"]
                options = mounts[0]["options"].split(",")
                if not isinstance(target, str) or not target.startswith("/"):
                    raise ValueError
                if "ro" in options:
                    raise GuardError(
                        "WSL_STORAGE_READ_ONLY: root or Docker storage is read-only; recover it before staging"
                    )
                if "rw" not in options:
                    raise ValueError
                available = self.wsl(
                    *prefix, "df", "--block-size=1", "--output=avail", "--", path,
                    operation="wsl-storage-space",
                ).splitlines()
                if (
                    len(available) != 2
                    or available[0].strip() != "Avail"
                    or not re.fullmatch(r"\s*\d+\s*", available[1])
                ):
                    raise ValueError
                free = int(available[1])
            except (ValueError, KeyError, TypeError, AttributeError):
                raise GuardError(
                    "WSL_STORAGE_UNKNOWN: root or Docker mount/space cannot be verified"
                ) from None
            self.summary["wsl_storage"][path] = {
                "mount_target": target,
                "free_gib": free // GIB,
            }
            if free < reserve * GIB:
                raise GuardError(
                    f"WSL_DISK_LOW: root or Docker storage needs {reserve} GiB free; recover space before staging"
                )

    def preflight(self, *, stop_recovery: bool = False) -> list[dict]:
        self.ownership_verified = False
        main = Path(
            native(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                ],
                operation="git-worktree",
            )
        ).parent
        if self.root == main.resolve():
            raise GuardError("MAIN_TREE: run staging from your isolated worktree")
        native(
            ["git", "-C", str(self.root), "check-ignore", str(self.env_file)],
            operation="git-env-ignore",
        )
        self.summary["commit"] = native(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"]
        )
        self.summary["worktree_dirty"] = bool(
            native(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "status",
                    "--porcelain",
                    "--untracked-files=no",
                ]
            )
        )
        # Source mounts identify the checkout; baked frontend assets can be older.
        self.summary["served_revision_verified"] = False
        self.linux_root = self.wsl("wslpath", "-a", "-u", str(self.root))
        self.linux_env = self.wsl("wslpath", "-a", "-u", str(self.env_file))
        self.linux_compose = self.wsl("wslpath", "-a", "-u", str(self.compose))
        self.summary["boot_id"] = self.boot_id()
        self.summary["docker"] = self.docker(
            "version", "--format", "{{.Server.Version}}"
        )
        self.summary["compose"] = self.docker("compose", "version", "--short")
        config = json.loads(self.compose_command("config", "--format", "json"))
        if config.get("name") != self.project:
            raise GuardError(
                "PROJECT_CONTEXT_MISMATCH: effective Compose project differs"
            )
        self.ports = effective_ports(
            config,
            self.values,
            self.linux_root,
            stop_recovery=stop_recovery,
        )
        self.summary["ports"] = self.ports
        if not stop_recovery:
            validate_windows_listeners(self.ports)
        owned = validate_ownership(
            self.containers(),
            self.project,
            self.linux_root,
            self.linux_compose,
            self.ports,
            enforce_port_bindings=not stop_recovery,
        )
        if not stop_recovery:
            owned_ports = {
                int(b["HostPort"])
                for c in owned
                if c.get("status") == "running"
                for group in (c.get("ports") or {}).values()
                for b in group or []
            }
            for port in self.ports.values():
                if tcp_ready(port) and port not in owned_ports:
                    raise GuardError(
                        "HOST_PORT: selected Windows port is already in use outside this project"
                    )
        free = None
        if not getattr(self, "storage_recovery", False):
            free = self.summary.get("host_disk_free_gib")
            if free is None:
                free = shutil.disk_usage(self.root).free // GIB
                self.summary["host_disk_free_gib"] = free
        mem = self.wsl("cat", "/proc/meminfo")
        self.summary["wsl_available_mib"] = (
            int(re.search(r"MemAvailable:\s+(\d+)", mem)[1]) // 1024
        )
        self.summary["warnings"] = []
        if free is not None and free < 10:
            self.summary["warnings"].append(
                "Low host disk space; no automatic prune performed"
            )
        if self.summary["wsl_available_mib"] < 1024:
            self.summary["warnings"].append(
                "Low WSL available memory; build concurrency is limited to one"
            )
        self.ownership_verified = True
        return owned

    def ready(self) -> None:
        validate_windows_listeners(self.ports)
        owned = validate_ownership(
            self.containers(),
            self.project,
            self.linux_root,
            self.linux_compose,
            self.ports,
        )
        by_service = {c["service"]: c for c in owned}
        for service in ("backend", "frontend", "postgres", "redis", "worker"):
            c = by_service.get(service)
            if (
                not c
                or c.get("status") != "running"
                or (service != "worker" and c.get("health") != "healthy")
            ):
                raise GuardError(
                    "STAGING_NOT_READY: missing, stopped or unhealthy service; do not run dependent tests"
                )
        for port in self.ports.values():
            if not tcp_ready(port):
                raise GuardError(
                    "FORWARDING_UNAVAILABLE: container is healthy but Windows cannot reach its port"
                )
        self.summary["images"] = {
            s: by_service[s].get("image") for s in ("backend", "frontend", "worker")
        }

    def _execute_after_preflight(self, args, keeper) -> dict:
        build_possible = args.action in {"start", "session"} and not args.no_build
        if args.action in {"start", "session"}:
            if not self.ownership_verified:
                raise GuardError(
                    "PROJECT_OWNERSHIP_UNVERIFIED: refusing staging execution"
                )
            owner, expires_raw, expires_at = lifecycle_context(self.values)
            self.lifecycle_owner = owner
            self.lifecycle_expires_at = expires_raw
            self.validate_project_lifecycle_labels()
            # Arm cleanup as soon as this exact project and its lifecycle
            # labels are verified. Start must also clean when later safety
            # checks (public origins, Linux storage or keeper continuity) fail.
            self.cleanup_policy = "always" if args.action == "session" else "failure"
            if args.action == "session":
                # A Session owns teardown once its project and lifecycle labels
                # have been verified, including readiness and child failures.
                if expires_at <= datetime.now(UTC):
                    raise GuardError(
                        "LIFECYCLE_EXPIRED: staging lease expired; project will be torn down"
                    )
            elif expires_at <= datetime.now(UTC):
                # A stale project name must not be reused. If it is still the
                # exact project, remove it on this failed Start path.
                raise GuardError(
                    "LIFECYCLE_EXPIRED: staging lease expired; project will be torn down"
                )

        if args.action != "stop":
            validate_public_origins(self.values, self.ports["frontend"])
            self.linux_storage(build_possible=build_possible)
        boot = self.summary["boot_id"]
        self.assert_session(keeper, boot)
        if args.action in {"start", "session"}:
            command = ["up", "-d", "--wait", "--wait-timeout", str(args.timeout)]
            if not args.no_build:
                command.append("--build")
            self.compose_command(
                *command, timeout=args.timeout + (1800 if not args.no_build else 30)
            )
        elif args.action == "stop":
            # Preserve volumes and every foreign project. No distro shutdown/prune.
            self.compose_command("down", timeout=args.timeout)
        if args.action not in {"stop", "preflight"}:
            self.ready()
            self.summary["runtime_readiness"] = "PASS"
        else:
            self.summary["runtime_readiness"] = "NOT_RUN"
        if args.action == "session":
            if not args.command and not args.pg_admin_env:
                raise GuardError(
                    "SESSION_COMMAND_REQUIRED: wrap the complete validation script"
                )
            junit = local_file(self.root, args.junit) if args.junit else None
            if junit and junit.exists():
                raise GuardError(
                    "STALE_REPORT: select a new JUnit path for this invocation"
                )
            if args.pg_admin_env:
                # Other fixtures may have hardcoded fallback ports. Only this
                # audited env-only scratch fixture belongs to the strict path.
                if args.pg_admin_env != "RQ23A_PG_ADMIN_URL" or args.command:
                    raise GuardError(
                        "PG_SUITE_BOUNDARY: strict PG mode runs only the audited effective-settings suite; omit CommandArgs"
                    )
                if not junit:
                    raise GuardError(
                        "PG_REPORT_REQUIRED: PostgreSQL proof must reject skipped tests"
                    )
                validate_pg_env(self.root, args.pg_admin_env, self.ports["postgres"])
                command = [
                    "powershell.exe",
                    "-NoProfile",
                    "-File",
                    str(self.root / "scripts/run_backend_pytest.ps1"),
                    "tests/integration/test_effective_queue_settings_report.py",
                    "--junitxml=" + str(junit),
                    "-q",
                    "-rs",
                ]
            else:
                command = args.command
            child_env = (
                pg_child_env(self.root, args.pg_admin_env)
                if args.pg_admin_env
                else None
            )
            try:
                result = subprocess.run(
                    command, cwd=self.root, env=child_env, check=False
                )
            except OSError:
                raise GuardError(
                    "SESSION_COMMAND_UNAVAILABLE: validation executable is missing"
                ) from None
            self.assert_session(keeper, boot)
            if result.returncode:
                raise GuardError(f"VALIDATION_FAILED: child exit {result.returncode}")
            if junit:
                self.summary["junit_passed_cases"] = validate_junit(junit)
        self.assert_session(keeper, boot)
        return self.summary

    def execute(self, args) -> dict:
        # Session commands are opaque and may build. NoBuild is the caller's
        # explicit promise to run without image builds, not an argv heuristic.
        build_possible = args.action in {"start", "session"} and not args.no_build
        self.host_storage(build_possible=build_possible, recovery=args.action == "stop")
        with self.keeper() as keeper:
            self.preflight(stop_recovery=args.action == "stop")
            self.cleanup_policy = None
            try:
                self._execute_after_preflight(args, keeper)
            except BaseException as primary:
                if self.cleanup_policy in {"failure", "always"}:
                    self.finish_after_failure(primary, keeper, self.summary["boot_id"])
                raise
            if self.cleanup_policy == "always":
                # A passing validation is never retained, even if KEEP_STAGING
                # was left in the process environment from an older failure.
                self.assert_session(keeper, self.summary["boot_id"])
                self.teardown_project(allow_keep=False)
                self.assert_session(keeper, self.summary["boot_id"])
            self.summary.update(action=args.action, result="PASS")
            if args.action == "start":
                self.summary["session_required"] = (
                    "Use Session for the full test/browser lifetime; Start alone releases the keeper"
                )
                if self.ownership_verified:
                    self.summary["teardown"] = "PENDING_SESSION"
            return self.summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--action",
        choices=("preflight", "check", "start", "stop", "session"),
        default="check",
    )
    parser.add_argument("--env-file", default="ops/staging.env")
    parser.add_argument("--distribution", default="Ubuntu-24.04")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--pg-admin-env")
    parser.add_argument("--junit")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command.pop(0)
    try:
        if os.name != "nt":
            raise GuardError(
                "WINDOWS_ONLY: invoke the PowerShell entry point on the Windows host"
            )
        print(
            json.dumps(
                WslStaging(ROOT, args.env_file, args.distribution).execute(args),
                ensure_ascii=True,
            )
        )
        return 0
    except (GuardError, ValueError, KeyError, TypeError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, GuardError)
            else "PREFLIGHT_FORMAT: unexpected native response; no further action"
        )
        print(json.dumps({"result": "FAIL", "reason": reason}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
