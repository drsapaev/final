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
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PORT_KEYS = {
    "backend": ("STAGING_BACKEND_PORT", 18001, 18000),
    "frontend": ("STAGING_FRONTEND_PORT", 18080, 80),
    "postgres": ("STAGING_POSTGRES_HOST_PORT", 55432, 5432),
}
INSPECT = (
    '{"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
    '"root":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
    '"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},'
    '"mounts":{{json .Mounts}},"ports":{{json .NetworkSettings.Ports}},'
    '"image":{{json .Image}},'
    '"status":{{json .State.Status}},'
    '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}'
)


class GuardError(RuntimeError):
    """Only safe, fixed diagnostic messages belong here."""


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
    keys = {"COMPOSE_PROJECT_NAME", *(v[0] for v in PORT_KEYS.values())}
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


def effective_ports(
    config: dict, values: dict[str, str], linux_root: str
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
        if service == "postgres" and item.get("host_ip") != "127.0.0.1":
            raise GuardError("POSTGRES_EXPOSED: PostgreSQL must bind to loopback")
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
    containers: list[dict], project: str, root: str, compose: str, ports: dict[str, int]
) -> list[dict]:
    owned = []
    for container in containers:
        bindings = [
            b
            for group in (container.get("ports") or {}).values()
            for b in (group or [])
        ]
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
            if service in ports and any(
                int(b["HostPort"]) != ports[service] for b in bindings
            ):
                raise GuardError(
                    "PORT_CONTEXT_MISMATCH: existing project uses different ports"
                )
            owned.append(container)
        elif container.get("status") == "running" and any(
            int(b["HostPort"]) in ports.values() for b in bindings
        ):
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


class WslStaging:
    def __init__(self, root: Path, env_file: str, distribution: str):
        self.root = root.resolve()
        self.env_file = local_file(self.root, env_file)
        self.values = context_values(self.env_file)
        self.project = self.values["COMPOSE_PROJECT_NAME"]
        self.distribution = distribution
        self.compose = self.root / "ops/compose.staging.yml"
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

    def preflight(self) -> list[dict]:
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
        self.ports = effective_ports(config, self.values, self.linux_root)
        self.summary["ports"] = self.ports
        validate_windows_listeners(self.ports)
        owned = validate_ownership(
            self.containers(),
            self.project,
            self.linux_root,
            self.linux_compose,
            self.ports,
        )
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
        free = shutil.disk_usage(self.root).free // (1024**3)
        self.summary["host_disk_free_gib"] = free
        mem = self.wsl("cat", "/proc/meminfo")
        self.summary["wsl_available_mib"] = (
            int(re.search(r"MemAvailable:\s+(\d+)", mem)[1]) // 1024
        )
        self.summary["warnings"] = []
        if free < 10:
            self.summary["warnings"].append(
                "Low host disk space; no automatic prune performed"
            )
        if self.summary["wsl_available_mib"] < 1024:
            self.summary["warnings"].append(
                "Low WSL available memory; build concurrency is limited to one"
            )
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

    def execute(self, args) -> dict:
        with self.keeper() as keeper:
            self.preflight()
            boot = self.summary["boot_id"]
            self.assert_session(keeper, boot)
            if args.action == "start":
                if not args.no_build and self.summary["host_disk_free_gib"] < 2:
                    raise GuardError(
                        "DISK_LOW: fewer than 2 GiB available on the worktree drive; resolve before build"
                    )
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
                    validate_pg_env(
                        self.root, args.pg_admin_env, self.ports["postgres"]
                    )
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
                    raise GuardError(
                        f"VALIDATION_FAILED: child exit {result.returncode}"
                    )
                if junit:
                    self.summary["junit_passed_cases"] = validate_junit(junit)
            self.assert_session(keeper, boot)
            self.summary.update(action=args.action, result="PASS")
            if args.action == "start":
                self.summary["session_required"] = (
                    "Use Session for the full test/browser lifetime; Start alone releases the keeper"
                )
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
