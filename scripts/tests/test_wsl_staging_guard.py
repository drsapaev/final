"""Safety checks for the Windows WSL staging entry point, without host mutation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import posixpath
import shutil
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "wsl_staging_under_test", Path(__file__).parents[1] / "wsl_staging.py"
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

LINUX_ROOT = "/mnt/c/session with spaces"
PROJECT = "aqs-test-session"
PORTS = {"backend": 19001, "frontend": 19080, "postgres": 55441}
VALUES = {
    "COMPOSE_PROJECT_NAME": PROJECT,
    "STAGING_BACKEND_PORT": "19001",
    "STAGING_FRONTEND_PORT": "19080",
    "STAGING_POSTGRES_HOST_PORT": "55441",
}


def compose_config():
    services = {}
    for service, (_, _, target) in guard.PORT_KEYS.items():
        services[service] = {
            "ports": [
                {"published": str(PORTS[service]), "target": target, "protocol": "tcp"}
            ]
        }
    services["postgres"]["ports"][0]["host_ip"] = "127.0.0.1"
    for service in ("backend", "worker"):
        services.setdefault(service, {})["volumes"] = [
            {"type": "bind", "source": LINUX_ROOT + "/backend", "target": "/app"}
        ]
    return {"name": PROJECT, "services": services}


def container(service="backend", *, project=PROJECT, status="running", **changes):
    result = {
        "project": project,
        "service": service,
        "root": LINUX_ROOT + "/ops",
        "files": LINUX_ROOT + "/ops/compose.staging.yml",
        "mounts": [{"Destination": "/app", "Source": LINUX_ROOT + "/backend"}],
        "ports": (
            {"18000/tcp": [{"HostPort": str(PORTS[service])}]}
            if service in PORTS
            else {}
        ),
        "status": status,
        "health": "healthy",
    }
    result.update(changes)
    return result


@pytest.fixture
def staging(tmp_path, monkeypatch):
    # Existing pure tooling tests must never query the host's real registry.
    monkeypatch.setattr(guard, "IS_WINDOWS", False)
    env = tmp_path / "ops" / "staging.env"
    env.parent.mkdir()
    env.write_text(
        "\n".join(f"{key}={value}" for key, value in VALUES.items()), encoding="utf-8"
    )
    return guard.WslStaging(tmp_path, "ops/staging.env", "Ubuntu-24.04")


class KeeperProcess:
    def __init__(self):
        self.stdin = SimpleNamespace(closed=False)
        self.stdin.close = lambda: setattr(self.stdin, "closed", True)
        self.waited = False
        self.terminated = False
        self.exit_code = None

    def poll(self):
        return self.exit_code

    def wait(self, timeout):
        self.waited = True
        return 0

    def terminate(self):
        self.terminated = True


@pytest.fixture
def session(staging, monkeypatch):
    keeper = KeeperProcess()
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *args, **kwargs: keeper)

    def preflight():
        staging.linux_root = LINUX_ROOT
        staging.linux_env = LINUX_ROOT + "/ops/staging.env"
        staging.linux_compose = LINUX_ROOT + "/ops/compose.staging.yml"
        staging.ports = PORTS.copy()
        staging.summary["boot_id"] = "boot-1"
        return []

    monkeypatch.setattr(staging, "preflight", preflight)
    monkeypatch.setattr(staging, "host_storage", lambda **kwargs: None)
    monkeypatch.setattr(staging, "linux_storage", lambda **kwargs: None)
    monkeypatch.setattr(staging, "boot_id", lambda: "boot-1")
    monkeypatch.setattr(staging, "ready", lambda: None)
    return staging, keeper


def args(action="session", **changes):
    result = {
        "action": action,
        "timeout": 180,
        "no_build": True,
        "command": ["validator.exe", "literal argument"],
        "junit": None,
        "pg_admin_env": None,
    }
    result.update(changes)
    return argparse.Namespace(**result)


@pytest.fixture
def registry(monkeypatch):
    """Model only read-only winreg operations; never read actual registrations."""
    def install(rows):
        @contextmanager
        def open_key(parent, name):
            if parent == "HKCU":
                assert name == r"Software\Microsoft\Windows\CurrentVersion\Lxss"
                yield "registrations"
            else:
                assert parent == "registrations"
                yield int(name)

        def value(key, name):
            if name not in rows[key]:
                raise OSError("unavailable registration value")
            return rows[key][name], 1

        module = SimpleNamespace(
            HKEY_CURRENT_USER="HKCU", OpenKey=open_key,
            QueryInfoKey=lambda key: (len(rows), 0, 0),
            EnumKey=lambda key, index: str(index), QueryValueEx=value,
        )
        monkeypatch.setitem(sys.modules, "winreg", module)
        return module

    return install


@pytest.mark.parametrize("base", [r"D:\WSL\Ubuntu-24.04", r"\\?\D:\WSL\Ubuntu-24.04"])
def test_registered_distro_storage_resolves_other_volume_and_extended_path(registry, base):
    registry([
        {"DistributionName": "Ubuntu-other", "BasePath": r"C:\WSL\other"},
        {"DistributionName": "Ubuntu-24.04", "BasePath": base},
    ])
    assert guard.windows_distro_base_path("ubuntu-24.04") == r"D:\WSL\Ubuntu-24.04"


@pytest.mark.parametrize("rows", [
    [],
    [{"DistributionName": "Ubuntu-other", "BasePath": r"D:\WSL\other"}],
    [{"DistributionName": "Ubuntu-24.04"}],
    [{"DistributionName": 123, "BasePath": r"D:\WSL\distro"}],
    [
        {"DistributionName": "Ubuntu-24.04", "BasePath": r"D:\WSL\one"},
        {"DistributionName": "ubuntu-24.04", "BasePath": r"E:\WSL\two"},
    ],
])
def test_unknown_or_ambiguous_distro_registration_fails_before_boot(
    staging, registry, monkeypatch, rows
):
    registry(rows)
    monkeypatch.setattr(guard, "IS_WINDOWS", True)
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: pytest.fail("no boot"))
    monkeypatch.setattr(guard, "native", lambda *a, **k: pytest.fail("no native command"))
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN"):
        staging.execute(args())


@pytest.mark.parametrize("base", [
    None, "", "D:relative", r"\relative", r"\\server\share\distro",
    r"\\?\UNC\server\share\distro", r"%USERPROFILE%\distro", "D:\\private\npath",
])
def test_invalid_backing_paths_fail_without_echoing_registry_values(registry, base):
    registry([{"DistributionName": "Ubuntu-24.04", "BasePath": base}])
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN") as error:
        guard.windows_distro_base_path("Ubuntu-24.04")
    assert "private" not in str(error.value) and "USERPROFILE" not in str(error.value)


def test_registry_failure_is_safe_and_does_not_invoke_wsl(staging, registry, monkeypatch):
    module = registry([])

    def unavailable(*args):
        raise OSError("private registry error")

    monkeypatch.setattr(module, "OpenKey", unavailable)
    monkeypatch.setattr(guard, "IS_WINDOWS", True)
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: pytest.fail("no boot"))
    monkeypatch.setattr(guard, "native", lambda *a, **k: pytest.fail("no native command"))
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN") as error:
        staging.execute(args("start", no_build=False))
    assert "private" not in str(error.value)


@pytest.mark.parametrize("action", ["preflight", "check", "start", "session"])
def test_full_vhd_volume_blocks_before_keeper_even_when_worktree_has_space(
    staging, registry, monkeypatch, action
):
    registry([{"DistributionName": "Ubuntu-24.04", "BasePath": r"\\?\D:\WSL\Ubuntu-24.04"}])
    monkeypatch.setattr(guard, "IS_WINDOWS", True)
    measured = []

    def usage(path):
        measured.append(path)
        return SimpleNamespace(free=0 if str(path).startswith("D:") else 6 * guard.GIB)

    monkeypatch.setattr(guard.shutil, "disk_usage", usage)
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: pytest.fail("no WSL keeper"))
    monkeypatch.setattr(guard, "native", lambda *a, **k: pytest.fail("no WSL/native command"))
    with pytest.raises(guard.GuardError, match="WSL_BACKING_DISK_LOW"):
        staging.execute(args(action))
    assert measured == [r"D:\WSL\Ubuntu-24.04"]


def test_build_with_healthy_backing_but_low_worktree_drive_stops_before_keeper(
    staging, registry, monkeypatch
):
    registry([{"DistributionName": "Ubuntu-24.04", "BasePath": r"D:\WSL\Ubuntu-24.04"}])
    monkeypatch.setattr(guard, "IS_WINDOWS", True)
    monkeypatch.setattr(guard.shutil, "disk_usage", lambda path: SimpleNamespace(
        free=20 * guard.GIB if str(path).startswith("D:") else guard.GIB
    ))
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: pytest.fail("no boot"))
    monkeypatch.setattr(guard, "native", lambda *a, **k: pytest.fail("no Compose/native command"))
    with pytest.raises(guard.GuardError, match="^DISK_LOW"):
        staging.execute(args("start", no_build=False))
    assert staging.summary["wsl_backing_disk_free_gib"] == 20
    assert staging.summary["host_disk_free_gib"] == 1


@pytest.mark.parametrize("build_possible,reserve", [(False, 2), (True, 10)])
@pytest.mark.parametrize("difference", [-1, 0])
def test_host_storage_reserve_uses_exact_byte_boundary(
    staging, monkeypatch, build_possible, reserve, difference
):
    monkeypatch.setattr(guard.shutil, "disk_usage", lambda path: SimpleNamespace(
        free=reserve * guard.GIB + difference
    ))
    if difference < 0:
        with pytest.raises(guard.GuardError, match="WSL_BACKING_DISK_LOW"):
            staging.host_storage(build_possible=build_possible)
    else:
        staging.host_storage(build_possible=build_possible)
        assert staging.summary["wsl_backing_disk_free_gib"] == reserve


@pytest.mark.parametrize("no_build", [False, True])
def test_opaque_session_requires_build_reserve_unless_caller_promises_no_build(
    session, monkeypatch, no_build
):
    staging, keeper = session
    monkeypatch.setattr(staging, "host_storage", guard.WslStaging.host_storage.__get__(staging))
    monkeypatch.setattr(guard.shutil, "disk_usage", lambda path: SimpleNamespace(free=6 * guard.GIB))
    child_calls = []
    monkeypatch.setattr(guard.subprocess, "run", lambda command, **kwargs:
        child_calls.append(command) or SimpleNamespace(returncode=0))
    invocation = args(no_build=no_build, command=["opaque.exe", "build-like literal"])
    if no_build:
        assert staging.execute(invocation)["result"] == "PASS"
        assert child_calls == [invocation.command]
        assert keeper.stdin.closed
    else:
        with pytest.raises(guard.GuardError, match="WSL_BACKING_DISK_LOW"):
            staging.execute(invocation)
        assert not child_calls and not keeper.stdin.closed


def test_unmeasurable_backing_volume_does_not_boot_or_echo_path(staging, monkeypatch):
    def unavailable(path):
        raise OSError("private backing path")

    monkeypatch.setattr(guard.shutil, "disk_usage", unavailable)
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: pytest.fail("no boot"))
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN") as error:
        staging.execute(args())
    assert "private" not in str(error.value)


@pytest.fixture
def linux_storage_stub(staging, monkeypatch):
    options = {"/": "rw,relatime,errors=remount-ro", "/custom Docker data": "rw"}
    space = {path: 20 * guard.GIB for path in options}
    calls = []

    def docker(*command, **kwargs):
        assert command == ("info", "--format", "{{json .DockerRootDir}}")
        return json.dumps("/custom Docker data")

    def wsl(*command, **kwargs):
        calls.append(command)
        assert command[:2] == ("env", "-i") and "LC_ALL=C" in command
        if "findmnt" in command:
            path = command[command.index("--target") + 1]
            return json.dumps({"filesystems": [{"target": path, "options": options[path]}]})
        assert "df" in command and command[-2] == "--"
        return f"Avail\n {space[command[-1]]}"

    monkeypatch.setattr(staging, "docker", docker)
    monkeypatch.setattr(staging, "wsl", wsl)
    return options, space, calls


def test_linux_storage_checks_real_docker_root_and_exact_read_only_token(staging, linux_storage_stub):
    _, _, calls = linux_storage_stub
    staging.linux_storage(build_possible=True)
    assert set(staging.summary["wsl_storage"]) == {"/", "/custom Docker data"}
    assert staging.summary["wsl_storage"]["/custom Docker data"]["free_gib"] == 20
    assert [command[-1] for command in calls if "df" in command] == ["/", "/custom Docker data"]


@pytest.mark.parametrize("response", ["private", "null", '"relative"', '""', '"/private\\npath"'])
def test_unverifiable_docker_storage_path_fails_safely(staging, monkeypatch, response):
    monkeypatch.setattr(staging, "docker", lambda *a, **k: response)
    monkeypatch.setattr(staging, "wsl", lambda *a, **k: pytest.fail("invalid Docker root"))
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN") as error:
        staging.linux_storage(build_possible=False)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("path", ["/", "/custom Docker data"])
def test_read_only_root_or_docker_storage_fails(staging, linux_storage_stub, path):
    options, _, _ = linux_storage_stub
    options[path] = "ro,relatime"
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_READ_ONLY"):
        staging.linux_storage(build_possible=False)


@pytest.mark.parametrize("build_possible,reserve", [(False, 2), (True, 10)])
@pytest.mark.parametrize("difference", [-1, 0])
def test_linux_storage_reserve_uses_exact_byte_boundary(
    staging, linux_storage_stub, build_possible, reserve, difference
):
    _, space, _ = linux_storage_stub
    space["/custom Docker data"] = reserve * guard.GIB + difference
    if difference < 0:
        with pytest.raises(guard.GuardError, match="WSL_DISK_LOW"):
            staging.linux_storage(build_possible=build_possible)
    else:
        staging.linux_storage(build_possible=build_possible)


@pytest.mark.parametrize("response", [
    "not json", "{}", '{"filesystems":[]}',
    '{"filesystems":[{"target":"/","options":"unknown"}]}',
    '{"filesystems":[{"target":"/","options":null}]}',
])
def test_unverifiable_linux_mount_fails_safely(staging, linux_storage_stub, monkeypatch, response):
    monkeypatch.setattr(staging, "wsl", lambda *a, **k: response)
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN"):
        staging.linux_storage(build_possible=False)


@pytest.mark.parametrize("available", [
    "", "Avail", "Avail\n-1", "Avail\nprivate", "Avail\n1\n2", "Unknown\n99999999999",
])
def test_unverifiable_linux_space_fails_safely(staging, linux_storage_stub, monkeypatch, available):
    original = staging.wsl
    monkeypatch.setattr(staging, "wsl", lambda *a, **k:
        available if "df" in a else original(*a, **k))
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_UNKNOWN") as error:
        staging.linux_storage(build_possible=False)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("action", ["start", "session"])
def test_linux_storage_failure_closes_keeper_before_compose_or_child(session, monkeypatch, action):
    staging, keeper = session

    def read_only(**kwargs):
        raise guard.GuardError("WSL_STORAGE_READ_ONLY")

    monkeypatch.setattr(staging, "linux_storage", read_only)
    monkeypatch.setattr(staging, "compose_command", lambda *a, **k: pytest.fail("no Compose mutation"))
    monkeypatch.setattr(guard.subprocess, "run", lambda *a, **k: pytest.fail("no child"))
    with pytest.raises(guard.GuardError, match="WSL_STORAGE_READ_ONLY"):
        staging.execute(args(action))
    assert keeper.stdin.closed and keeper.waited


def test_stop_bypasses_storage_blockers_but_only_runs_owned_down(session, registry, monkeypatch):
    staging, keeper = session
    registry([{"DistributionName": "Ubuntu-24.04", "BasePath": r"D:\WSL\Ubuntu-24.04"}])
    monkeypatch.setattr(guard, "IS_WINDOWS", True)
    monkeypatch.setattr(staging, "host_storage", guard.WslStaging.host_storage.__get__(staging))
    monkeypatch.setattr(guard.shutil, "disk_usage", lambda *a: pytest.fail("Stop must not demand space"))
    monkeypatch.setattr(staging, "linux_storage", lambda **k: pytest.fail("Stop must not demand writable storage"))
    commands = []
    monkeypatch.setattr(staging, "compose_command", lambda *a, **k: commands.append((a, k)))
    assert staging.execute(args("stop"))["storage_checks"] == "BYPASSED_FOR_OWNED_STOP"
    assert commands == [(('down',), {"timeout": 180})]
    assert keeper.stdin.closed and keeper.waited


def test_native_failure_keeps_secret_stderr_and_arguments_private(monkeypatch):
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=7, stdout=b"", stderr=b"secret-password-expanded"
        ),
    )
    with pytest.raises(guard.GuardError, match=r"NATIVE_FAILED.*exit 7") as error:
        guard.native(["docker", "secret-password-in-argv"])
    assert "secret-password" not in str(error.value)


@pytest.mark.parametrize(
    "failure", [OSError("private path"), subprocess.TimeoutExpired("secret", 30)]
)
def test_native_unavailable_is_safe_and_fail_closed(monkeypatch, failure):
    def run(*args, **kwargs):
        raise failure

    monkeypatch.setattr(guard.subprocess, "run", run)
    with pytest.raises(guard.GuardError, match="NATIVE_UNAVAILABLE") as error:
        guard.native(["secret"])
    assert "private path" not in str(error.value)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16-le"])
def test_native_decodes_wsl_output(monkeypatch, encoding):
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=" WSL 3.0.1\r\n".encode(encoding)
        ),
    )
    assert guard.native(["wsl.exe"]) == "WSL 3.0.1"


def test_context_requires_explicit_project(tmp_path):
    path = tmp_path / "staging.env"
    path.write_text("STAGING_BACKEND_PORT=19001\n", encoding="utf-8")
    with pytest.raises(guard.GuardError, match="PROJECT_REQUIRED"):
        guard.context_values(path)


@pytest.mark.parametrize("key", list(VALUES))
def test_context_rejects_duplicate_context_keys(tmp_path, key):
    path = tmp_path / "staging.env"
    path.write_text(
        f"COMPOSE_PROJECT_NAME={PROJECT}\n{key}={VALUES[key]}\n{key}={VALUES[key]}\n"
    )
    with pytest.raises(guard.GuardError, match="ENV_DUPLICATE"):
        guard.context_values(path)


def test_context_reads_quoted_literals_and_comments_without_secrets(tmp_path):
    path = tmp_path / "staging.env"
    path.write_text(
        f'COMPOSE_PROJECT_NAME="{PROJECT}" # task\n'
        "STAGING_BACKEND_PORT='19001'\n"
        "STAGING_FRONTEND_PORT=19080 # local\n"
        "POSTGRES_PASSWORD=secret-not-returned\n",
        encoding="utf-8-sig",
    )
    assert guard.context_values(path) == {
        "COMPOSE_PROJECT_NAME": PROJECT,
        "STAGING_BACKEND_PORT": "19001",
        "STAGING_FRONTEND_PORT": "19080",
    }


@pytest.mark.parametrize("value", ['"unclosed', '"project"junk', "'project' another"])
def test_context_rejects_malformed_quotes(tmp_path, value):
    path = tmp_path / "staging.env"
    path.write_text(f"COMPOSE_PROJECT_NAME={value}\n")
    with pytest.raises(guard.GuardError, match="ENV_CONTEXT_INVALID"):
        guard.context_values(path)


def test_local_file_prevents_escape_and_keeps_spaces(tmp_path):
    assert (
        guard.local_file(tmp_path, "ops/my staging.env")
        == tmp_path / "ops/my staging.env"
    )
    with pytest.raises(guard.GuardError, match="PATH_OUTSIDE_WORKTREE"):
        guard.local_file(tmp_path, "../other-session/staging.env")


def test_effective_ports_accepts_canonical_worktree_bindings():
    assert guard.effective_ports(compose_config(), VALUES, LINUX_ROOT) == PORTS


@pytest.mark.parametrize("port", [18000, 5173, 5432, 1023, 65536])
def test_effective_ports_rejects_production_and_invalid_ports(port):
    config = compose_config()
    values = VALUES.copy()
    config["services"]["backend"]["ports"][0]["published"] = port
    values["STAGING_BACKEND_PORT"] = str(port)
    with pytest.raises(guard.GuardError, match="PRODUCTION_PORT"):
        guard.effective_ports(config, values, LINUX_ROOT)


def test_effective_ports_rejects_service_port_collision():
    config = compose_config()
    values = VALUES.copy()
    config["services"]["frontend"]["ports"][0]["published"] = PORTS["backend"]
    values["STAGING_FRONTEND_PORT"] = str(PORTS["backend"])
    with pytest.raises(guard.GuardError, match="PORT_COLLISION"):
        guard.effective_ports(config, values, LINUX_ROOT)


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"published": "19002"}, "PORT_CONTEXT_MISMATCH"),
        ({"target": 18001}, "PORT_CONTEXT_MISMATCH"),
        ({"protocol": "udp"}, "PORT_CONTEXT_MISMATCH"),
    ],
)
def test_effective_ports_rejects_ambient_context_drift(change, reason):
    config = compose_config()
    config["services"]["backend"]["ports"][0].update(change)
    with pytest.raises(guard.GuardError, match=reason):
        guard.effective_ports(config, VALUES, LINUX_ROOT)


def test_effective_ports_rejects_extra_binding():
    config = compose_config()
    config["services"]["backend"]["ports"].append(
        {"published": "19002", "target": 18000}
    )
    with pytest.raises(guard.GuardError, match="PORT_SHAPE"):
        guard.effective_ports(config, VALUES, LINUX_ROOT)


def test_effective_ports_rejects_exposed_postgresql():
    config = compose_config()
    config["services"]["postgres"]["ports"][0]["host_ip"] = "0.0.0.0"
    with pytest.raises(guard.GuardError, match="POSTGRES_EXPOSED"):
        guard.effective_ports(config, VALUES, LINUX_ROOT)


@pytest.mark.parametrize("service", ["backend", "worker"])
def test_effective_config_rejects_foreign_source(service):
    config = compose_config()
    config["services"][service]["volumes"][0]["source"] = "/mnt/c/final/backend"
    with pytest.raises(guard.GuardError, match="SOURCE_MISMATCH"):
        guard.effective_ports(config, VALUES, LINUX_ROOT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("root", "/mnt/c/foreign-session"),
        ("files", LINUX_ROOT + "/ops/docker-compose.yml"),
    ],
)
def test_ownership_rejects_reused_project_from_another_context(field, value):
    with pytest.raises(guard.GuardError, match="PROJECT_OWNERSHIP"):
        guard.validate_ownership(
            [container(**{field: value})],
            PROJECT,
            LINUX_ROOT,
            LINUX_ROOT + "/ops/compose.staging.yml",
            PORTS,
        )


def test_ownership_rejects_foreign_project_port_and_preserves_stopped_project():
    foreign = container(project="another-agent")
    with pytest.raises(guard.GuardError, match="FOREIGN_PORT"):
        guard.validate_ownership(
            [foreign],
            PROJECT,
            LINUX_ROOT,
            LINUX_ROOT + "/ops/compose.staging.yml",
            PORTS,
        )
    foreign["status"] = "exited"
    assert (
        guard.validate_ownership(
            [foreign],
            PROJECT,
            LINUX_ROOT,
            LINUX_ROOT + "/ops/compose.staging.yml",
            PORTS,
        )
        == []
    )


def test_ownership_rejects_changed_existing_mount_and_port():
    existing = container(
        mounts=[{"Destination": "/app", "Source": "/mnt/c/foreign/backend"}]
    )
    with pytest.raises(guard.GuardError, match="SOURCE_MISMATCH"):
        guard.validate_ownership(
            [existing],
            PROJECT,
            LINUX_ROOT,
            LINUX_ROOT + "/ops/compose.staging.yml",
            PORTS,
        )
    existing = container(ports={"18000/tcp": [{"HostPort": "19002"}]})
    with pytest.raises(guard.GuardError, match="PORT_CONTEXT_MISMATCH"):
        guard.validate_ownership(
            [existing],
            PROJECT,
            LINUX_ROOT,
            LINUX_ROOT + "/ops/compose.staging.yml",
            PORTS,
        )


def test_docker_argv_uses_native_wsl_local_socket_and_explicit_compose(
    staging, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        guard, "native", lambda argv, **kwargs: seen.append((argv, kwargs)) or ""
    )
    staging.linux_root = LINUX_ROOT
    staging.linux_env = LINUX_ROOT + "/ops/my staging.env"
    staging.linux_compose = LINUX_ROOT + "/ops/compose.staging.yml"
    staging.compose_command("config", "--format", "json")
    argv = seen[0][0]
    assert argv[:5] == ["wsl.exe", "--distribution", "Ubuntu-24.04", "--exec", "env"]
    assert "-i" in argv
    assert "unix:///var/run/docker.sock" in argv
    assert "COMPOSE_PARALLEL_LIMIT=1" in argv
    directory = argv[argv.index("--project-directory") + 1]
    assert directory == LINUX_ROOT + "/ops"
    # compose.staging.yml's ../backend source is relative to its ops directory.
    assert posixpath.normpath(directory + "/../backend") == LINUX_ROOT + "/backend"
    assert argv[argv.index("--project-name") + 1] == PROJECT
    assert argv[argv.index("--env-file") + 1] == staging.linux_env
    assert argv[argv.index("-f") + 1] == staging.linux_compose
    assert not any("bash" in argument for argument in argv)


def test_failed_up_aborts_readiness_and_closes_keeper(session, monkeypatch):
    staging, keeper = session
    called = []

    def compose(*command, **kwargs):
        called.append(command)
        raise guard.GuardError("NATIVE_FAILED: exit 1")

    monkeypatch.setattr(staging, "compose_command", compose)
    monkeypatch.setattr(
        staging, "ready", lambda: pytest.fail("must not continue after failed up")
    )
    with pytest.raises(guard.GuardError, match="NATIVE_FAILED"):
        staging.execute(args("start"))
    assert called == [("up", "-d", "--wait", "--wait-timeout", "180")]
    assert keeper.stdin.closed and keeper.waited


def test_preflight_action_reports_readiness_not_run_and_has_no_compose_mutation(
    session, monkeypatch
):
    staging, keeper = session
    monkeypatch.setattr(
        staging,
        "ready",
        lambda: pytest.fail("preflight must not claim runtime readiness"),
    )
    monkeypatch.setattr(
        staging,
        "compose_command",
        lambda *a, **k: pytest.fail("preflight must not mutate Compose"),
    )
    result = staging.execute(args("preflight"))
    assert result["result"] == "PASS"
    assert result["runtime_readiness"] == "NOT_RUN"
    assert keeper.stdin.closed


def test_check_action_cannot_pass_unhealthy_runtime(session, monkeypatch):
    staging, keeper = session

    def ready():
        raise guard.GuardError("STAGING_NOT_READY")

    monkeypatch.setattr(staging, "ready", ready)
    with pytest.raises(guard.GuardError, match="STAGING_NOT_READY"):
        staging.execute(args("check"))
    assert keeper.stdin.closed


def test_start_rejects_build_before_mutation_when_disk_is_low(session, monkeypatch):
    staging, keeper = session
    monkeypatch.setattr(
        staging, "host_storage", guard.WslStaging.host_storage.__get__(staging)
    )
    monkeypatch.setattr(
        guard.shutil, "disk_usage", lambda path: SimpleNamespace(free=guard.GIB)
    )
    monkeypatch.setattr(
        guard.subprocess, "Popen", lambda *a, **k: pytest.fail("do not boot low storage")
    )
    monkeypatch.setattr(
        staging,
        "compose_command",
        lambda *a, **k: pytest.fail("low disk must stop build"),
    )
    with pytest.raises(guard.GuardError, match="DISK_LOW"):
        staging.execute(args("start", no_build=False))
    assert not keeper.stdin.closed and not keeper.waited


def test_session_keeps_wsl_alive_for_exact_child_lifetime(session, monkeypatch):
    staging, keeper = session

    def child(command, **kwargs):
        assert not keeper.stdin.closed
        assert command == ["validator.exe", "literal argument"]
        assert kwargs == {"cwd": staging.root, "env": None, "check": False}
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(guard.subprocess, "run", child)
    result = staging.execute(args())
    assert result["result"] == "PASS"
    assert keeper.stdin.closed and keeper.waited


def test_failed_child_closes_keeper_and_cannot_pass(session, monkeypatch):
    staging, keeper = session
    monkeypatch.setattr(
        guard.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=9)
    )
    with pytest.raises(guard.GuardError, match="VALIDATION_FAILED: child exit 9"):
        staging.execute(args())
    assert keeper.stdin.closed and keeper.waited


def test_missing_child_closes_keeper(session, monkeypatch):
    staging, keeper = session

    def child(*args, **kwargs):
        raise OSError("sensitive executable path")

    monkeypatch.setattr(guard.subprocess, "run", child)
    with pytest.raises(guard.GuardError, match="SESSION_COMMAND_UNAVAILABLE"):
        staging.execute(args())
    assert keeper.stdin.closed and keeper.waited


def test_preflight_failure_closes_keeper_without_child(session, monkeypatch):
    staging, keeper = session

    def preflight():
        raise guard.GuardError("FOREIGN_PORT")

    monkeypatch.setattr(staging, "preflight", preflight)
    monkeypatch.setattr(
        guard.subprocess, "run", lambda *a, **k: pytest.fail("child must not start")
    )
    with pytest.raises(guard.GuardError, match="FOREIGN_PORT"):
        staging.execute(args())
    assert keeper.stdin.closed and keeper.waited


def test_empty_session_command_closes_keeper_before_child(session, monkeypatch):
    staging, keeper = session
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *a, **k: pytest.fail("missing command must fail"),
    )
    with pytest.raises(guard.GuardError, match="SESSION_COMMAND_REQUIRED"):
        staging.execute(args(command=[]))
    assert keeper.stdin.closed and keeper.waited


def test_keeper_releases_own_pipe_after_interruption(staging, monkeypatch):
    keeper = KeeperProcess()
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: keeper)
    with pytest.raises(KeyboardInterrupt), staging.keeper():
        assert not keeper.stdin.closed
        raise KeyboardInterrupt
    assert keeper.stdin.closed and keeper.waited


def test_keeper_timeout_terminates_only_its_own_process(staging, monkeypatch):
    keeper = KeeperProcess()
    waits = []

    def wait(timeout):
        waits.append(timeout)
        if len(waits) == 1:
            raise subprocess.TimeoutExpired("wsl", timeout)
        return 0

    keeper.wait = wait
    monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: keeper)
    with staging.keeper():
        pass
    assert keeper.stdin.closed and keeper.terminated
    assert waits == [5, 5]


def test_ended_keeper_or_changed_boot_cannot_prove_validation(session, monkeypatch):
    staging, keeper = session
    keeper.exit_code = 0
    with pytest.raises(guard.GuardError, match="WSL_INTERRUPTED"):
        staging.assert_session(keeper, "boot-1")
    keeper.exit_code = None
    monkeypatch.setattr(staging, "boot_id", lambda: "boot-2")
    with pytest.raises(guard.GuardError, match="WSL_INTERRUPTED"):
        staging.assert_session(keeper, "boot-1")


def test_vm_restart_after_child_cannot_report_pass(session, monkeypatch):
    staging, keeper = session

    def child(*args, **kwargs):
        monkeypatch.setattr(staging, "boot_id", lambda: "boot-2")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(guard.subprocess, "run", child)
    with pytest.raises(guard.GuardError, match="WSL_INTERRUPTED"):
        staging.execute(args())
    assert keeper.stdin.closed


@pytest.mark.parametrize(
    "body",
    [
        "<testsuites/>",
        "<testsuite><testcase><skipped/></testcase></testsuite>",
        "<testsuite><testcase><error/></testcase></testsuite>",
        "<testsuite><testcase><failure/></testcase></testsuite>",
    ],
)
def test_junit_rejects_zero_skipped_failed_or_error_cases(tmp_path, body):
    path = tmp_path / "proof.xml"
    path.write_text(body)
    with pytest.raises(guard.GuardError, match="PG_PROOF_INCOMPLETE"):
        guard.validate_junit(path)


def test_junit_rejects_missing_and_malformed_report(tmp_path):
    path = tmp_path / "proof.xml"
    with pytest.raises(guard.GuardError, match="PG_PROOF_MISSING"):
        guard.validate_junit(path)
    path.write_text("not xml")
    with pytest.raises(guard.GuardError, match="PG_PROOF_MISSING"):
        guard.validate_junit(path)


def test_junit_counts_real_passed_cases(tmp_path):
    path = tmp_path / "proof.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="one"/><testcase name="two"/></testsuite></testsuites>'
    )
    assert guard.validate_junit(path) == 2


def test_session_rejects_stale_report_before_child(session, monkeypatch):
    staging, keeper = session
    (staging.root / "proof.xml").write_text("<testsuite><testcase/></testsuite>")
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *a, **k: pytest.fail("stale proof must stop child"),
    )
    with pytest.raises(guard.GuardError, match="STALE_REPORT"):
        staging.execute(args(junit="proof.xml"))
    assert keeper.stdin.closed


def test_session_rejects_skipped_pg_proof_and_closes_keeper(session, monkeypatch):
    staging, keeper = session
    report = staging.root / "proof.xml"

    def child(*args, **kwargs):
        report.write_text("<testsuite><testcase><skipped/></testcase></testsuite>")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(guard.subprocess, "run", child)
    monkeypatch.setattr(guard, "validate_pg_env", lambda *a: None)
    monkeypatch.setenv(
        "RQ23A_PG_ADMIN_URL", "postgresql://synthetic@127.0.0.1:55441/postgres"
    )
    with pytest.raises(guard.GuardError, match="PG_PROOF_INCOMPLETE"):
        staging.execute(
            args(junit="proof.xml", pg_admin_env="RQ23A_PG_ADMIN_URL", command=[])
        )
    assert keeper.stdin.closed


def test_pg_proof_requires_report_before_child(session, monkeypatch):
    staging, keeper = session
    monkeypatch.setattr(
        guard.subprocess, "run", lambda *a, **k: pytest.fail("report is mandatory")
    )
    with pytest.raises(guard.GuardError, match="PG_REPORT_REQUIRED"):
        staging.execute(args(pg_admin_env="RQ23A_PG_ADMIN_URL", command=[]))
    assert keeper.stdin.closed


@pytest.mark.parametrize(
    "name,command",
    [
        ("RQ15D_PG_ADMIN_URL", []),
        ("OTHER_PG_ADMIN_URL", []),
        ("RQ23A_PG_ADMIN_URL", ["opaque-validation.exe"]),
        ("RQ23A_PG_ADMIN_URL", ["powershell.exe", "-File", "other-suite.ps1"]),
    ],
)
def test_strict_pg_rejects_unaudited_fixture_or_opaque_command(
    session, monkeypatch, name, command
):
    staging, keeper = session
    monkeypatch.setattr(
        guard.subprocess, "run", lambda *a, **k: pytest.fail("child must not start")
    )
    monkeypatch.setattr(
        guard, "validate_pg_env", lambda *a: pytest.fail("boundary must reject first")
    )
    with pytest.raises(guard.GuardError, match="PG_SUITE_BOUNDARY"):
        staging.execute(args(junit="proof.xml", pg_admin_env=name, command=command))
    assert keeper.stdin.closed and keeper.waited


@pytest.fixture
def pg_guard_stub(monkeypatch):
    # The wrapper must invoke the canonical guard without requiring SQLAlchemy
    # in this tooling-only suite. The backend guard has its own contract tests.
    called = []
    module = SimpleNamespace(is_local_admin_dsn=lambda dsn: called.append(dsn) or True)
    loader = SimpleNamespace(exec_module=lambda imported: None)
    monkeypatch.setattr(
        guard.importlib.util,
        "spec_from_file_location",
        lambda *a: SimpleNamespace(loader=loader),
    )
    monkeypatch.setattr(guard.importlib.util, "module_from_spec", lambda spec: module)
    return module, called


def test_pg_guard_accepts_only_selected_loopback_port(
    staging, monkeypatch, pg_guard_stub
):
    _, called = pg_guard_stub
    dsn = "postgresql://synthetic:secret@127.0.0.1:55441/postgres"
    monkeypatch.setenv("RQ23A_PG_ADMIN_URL", dsn)
    guard.validate_pg_env(staging.root, "RQ23A_PG_ADMIN_URL", PORTS["postgres"])
    assert called == [dsn]


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://synthetic:secret@127.0.0.1:5432/postgres",
        "postgresql://synthetic:secret@db.remote:55441/postgres",
        "postgresql://synthetic:secret@127.0.0.1:55441/postgres?host=127.0.0.1",
        "postgresql://synthetic:secret@127.0.0.1:55441/postgres?HOSTADDR=10.0.0.1",
        "postgresql://synthetic:secret@127.0.0.1:55441/postgres?port=5432",
        "postgresql://synthetic:secret@127.0.0.1:55441/postgres?SERVICE=remote",
        "postgresql+psycopg://synthetic:secret@127.0.0.1:55441/postgres",
        "postgres://synthetic:secret@127.0.0.1:55441/postgres",
        "postgresql://synthetic:secret@127.0.0.1:55441/",
        "postgresql://synthetic:secret@127.0.0.1:55441",
    ],
)
def test_pg_guard_rejects_wrong_port_remote_and_query_redial(
    staging, monkeypatch, pg_guard_stub, dsn
):
    monkeypatch.setenv("RQ23A_PG_ADMIN_URL", dsn)
    with pytest.raises(guard.GuardError, match="PG_TARGET_REJECTED") as error:
        guard.validate_pg_env(staging.root, "RQ23A_PG_ADMIN_URL", PORTS["postgres"])
    assert "secret" not in str(error.value)


def test_pg_guard_honors_canonical_environment_rejection(
    staging, monkeypatch, pg_guard_stub
):
    module, _ = pg_guard_stub
    module.is_local_admin_dsn = lambda dsn: False
    monkeypatch.setenv(
        "RQ23A_PG_ADMIN_URL", "postgresql://synthetic@127.0.0.1:55441/postgres"
    )
    with pytest.raises(guard.GuardError, match="PG_TARGET_REJECTED"):
        guard.validate_pg_env(staging.root, "RQ23A_PG_ADMIN_URL", PORTS["postgres"])


def test_pg_guard_dependency_failure_does_not_echo_dsn(
    staging, monkeypatch, pg_guard_stub
):
    monkeypatch.setenv(
        "RQ23A_PG_ADMIN_URL", "postgresql://secret@127.0.0.1:55441/postgres"
    )

    def load(module):
        raise ImportError("secret-dependent package")

    loader = SimpleNamespace(exec_module=load)
    monkeypatch.setattr(
        guard.importlib.util,
        "spec_from_file_location",
        lambda *a: SimpleNamespace(loader=loader),
    )
    with pytest.raises(guard.GuardError, match="PG_GUARD_UNAVAILABLE") as error:
        guard.validate_pg_env(staging.root, "RQ23A_PG_ADMIN_URL", PORTS["postgres"])
    assert "secret" not in str(error.value)


def test_pg_child_environment_pins_selected_dsn_and_blocks_dotenv_fallback(
    staging, monkeypatch
):
    chosen = "postgresql://synthetic:private@127.0.0.1:55441/postgres"
    tests = staging.root / "backend" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_candidates.py").write_text('CANDIDATE = "SECONDARY_PG_ADMIN_DSN"\n')
    (staging.root / "backend" / ".env").write_text(
        "SECONDARY_PG_ADMIN_DSN=postgresql://other@127.0.0.1:5432/postgres\n"
    )
    monkeypatch.setenv("RQ23A_PG_ADMIN_URL", chosen)
    monkeypatch.setenv(
        "EXISTING_PG_ADMIN_URL", "postgresql://other@127.0.0.1:5432/postgres"
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://production@db.remote:5432/clinic")
    monkeypatch.setenv("LOCAL_PG_SUPERUSER_PASSWORD", "other-private-password")
    monkeypatch.delenv("SECONDARY_PG_ADMIN_DSN", raising=False)
    before = dict(guard.os.environ)
    environment = guard.pg_child_env(staging.root, "RQ23A_PG_ADMIN_URL")
    assert environment["RQ23A_PG_ADMIN_URL"] == chosen
    assert environment["DATABASE_URL"] == chosen.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    assert environment["EXISTING_PG_ADMIN_URL"] == ""
    assert environment["SECONDARY_PG_ADMIN_DSN"] == ""
    assert environment["LOCAL_PG_SUPERUSER_PASSWORD"] == ""
    # Reproduce load_dotenv(override=False): an explicitly blank key stays blank.
    for line in (staging.root / "backend" / ".env").read_text().splitlines():
        key, value = line.split("=", 1)
        environment.setdefault(key, value)
    assert environment["SECONDARY_PG_ADMIN_DSN"] == ""
    assert dict(guard.os.environ) == before


@pytest.mark.parametrize("exit_code", [0, 8])
def test_strict_pg_environment_is_only_given_to_child_and_parent_is_preserved(
    session, monkeypatch, exit_code
):
    staging, keeper = session
    chosen = "postgresql://synthetic:private@127.0.0.1:55441/postgres"
    monkeypatch.setenv("RQ23A_PG_ADMIN_URL", chosen)
    monkeypatch.setenv("DATABASE_URL", "parent-is-preserved")
    monkeypatch.setenv("OTHER_PG_ADMIN_URL", "other-fallback")
    before = dict(guard.os.environ)
    monkeypatch.setattr(guard, "validate_pg_env", lambda *a: None)

    def child(command, **kwargs):
        assert not keeper.stdin.closed
        assert kwargs["env"]["RQ23A_PG_ADMIN_URL"] == chosen
        assert kwargs["env"]["DATABASE_URL"] == chosen.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
        assert kwargs["env"]["OTHER_PG_ADMIN_URL"] == ""
        assert guard.os.environ["DATABASE_URL"] == "parent-is-preserved"
        assert command == [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(staging.root / "scripts/run_backend_pytest.ps1"),
            "tests/integration/test_effective_queue_settings_report.py",
            "--junitxml=" + str(staging.root / "proof.xml"),
            "-q",
            "-rs",
        ]
        (staging.root / "proof.xml").write_text("<testsuite><testcase/></testsuite>")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(guard.subprocess, "run", child)
    invocation = args(junit="proof.xml", pg_admin_env="RQ23A_PG_ADMIN_URL", command=[])
    if exit_code:
        with pytest.raises(guard.GuardError, match="VALIDATION_FAILED"):
            staging.execute(invocation)
    else:
        assert staging.execute(invocation)["junit_passed_cases"] == 1
    assert dict(guard.os.environ) == before
    assert keeper.stdin.closed and keeper.waited


@pytest.mark.parametrize(
    "listeners",
    [
        "",
        "[]",
        '{"port":19001,"process":"wslrelay"}',
        '[{"port":19001,"process":"WSLHOST"},{"port":19080,"process":"wslrelay"}]',
    ],
)
def test_windows_listener_guard_allows_only_known_wsl_forwarders(
    monkeypatch, listeners
):
    calls = []
    monkeypatch.setattr(
        guard, "native", lambda *a, **k: calls.append((a, k)) or listeners
    )
    guard.validate_windows_listeners(PORTS)
    command = calls[0][0][0]
    assert command[:3] == ["powershell.exe", "-NoProfile", "-Command"]
    assert "Get-NetTCPConnection -State Listen" in command[3]
    assert "Stop-Process" not in command[3]
    assert "19001,19080,55441" in command[3]


@pytest.mark.parametrize("process", ["python", "System", "", "docker-proxy"])
def test_windows_listener_guard_rejects_native_or_ambiguous_owner(monkeypatch, process):
    monkeypatch.setattr(
        guard, "native", lambda *a, **k: json.dumps({"port": 19001, "process": process})
    )
    with pytest.raises(guard.GuardError, match="WINDOWS_PORT_OWNER"):
        guard.validate_windows_listeners(PORTS)


def test_preflight_blocks_production_checkout_before_docker(staging, monkeypatch):
    monkeypatch.setattr(guard, "native", lambda *a, **k: str(staging.root / ".git"))
    monkeypatch.setattr(
        staging,
        "docker",
        lambda *a, **k: pytest.fail("production checkout must stop first"),
    )
    with pytest.raises(guard.GuardError, match="MAIN_TREE"):
        staging.preflight()


@pytest.mark.parametrize("action", ["preflight", "stop"])
def test_real_preflight_checks_context_and_stop_bypasses_capacity_probes(
    staging, monkeypatch, action
):
    calls = []
    mutations = []

    def native(argv, **kwargs):
        calls.append(argv)
        if "--git-common-dir" in argv:
            return str(staging.root.parent / "main" / ".git")
        if "check-ignore" in argv:
            return str(staging.env_file)
        if "HEAD" in argv:
            return "a" * 40
        if "status" in argv:
            return ""
        raise AssertionError(argv)

    def wsl(*argv, **kwargs):
        if argv[0] == "wslpath":
            path = Path(argv[-1])
            return LINUX_ROOT + (
                "/" + path.relative_to(staging.root).as_posix()
                if path != staging.root
                else ""
            )
        if argv == ("cat", "/proc/sys/kernel/random/boot_id"):
            return "boot-1"
        if argv == ("cat", "/proc/meminfo"):
            return "MemAvailable: 2097152 kB"
        raise AssertionError(argv)

    def docker(*argv, **kwargs):
        if argv == ("version", "--format", "{{.Server.Version}}"):
            return "29.1.3"
        if argv == ("compose", "version", "--short"):
            return "2.40.3"
        raise AssertionError(argv)

    def compose(*command, **kwargs):
        if command == ("config", "--format", "json"):
            return json.dumps(compose_config())
        assert action == "stop" and command == ("down",)
        mutations.append((command, kwargs))

    monkeypatch.setattr(guard, "native", native)
    monkeypatch.setattr(staging, "wsl", wsl)
    monkeypatch.setattr(staging, "docker", docker)
    monkeypatch.setattr(staging, "compose_command", compose)
    monkeypatch.setattr(staging, "containers", list)
    monkeypatch.setattr(guard, "validate_windows_listeners", lambda ports: None)
    monkeypatch.setattr(guard, "tcp_ready", lambda port: False)
    if action == "stop":
        keeper = KeeperProcess()
        monkeypatch.setattr(guard.subprocess, "Popen", lambda *a, **k: keeper)
        monkeypatch.setattr(guard.shutil, "disk_usage", lambda *a: pytest.fail("Stop capacity probe"))
        monkeypatch.setattr(staging, "linux_storage", lambda **k: pytest.fail("Stop Linux probe"))
        assert staging.execute(args("stop"))["result"] == "PASS"
        assert mutations == [(('down',), {"timeout": 180})]
        assert keeper.stdin.closed and keeper.waited
    else:
        monkeypatch.setattr(
            guard.shutil, "disk_usage", lambda root: SimpleNamespace(free=20 * guard.GIB)
        )
        assert staging.preflight() == []
        assert not mutations
    assert staging.summary["commit"] == "a" * 40
    assert staging.summary["ports"] == PORTS
    assert staging.summary["wsl_available_mib"] == 2048
    assert len(calls) == 4  # No checkout, reset, up/down or any other mutation.


def test_ready_distinguishes_container_health_from_windows_forwarding(
    staging, monkeypatch
):
    staging.linux_root = LINUX_ROOT
    staging.linux_compose = LINUX_ROOT + "/ops/compose.staging.yml"
    staging.ports = PORTS.copy()
    running = [
        container(service)
        for service in ("backend", "frontend", "postgres", "redis", "worker")
    ]
    monkeypatch.setattr(staging, "containers", lambda: deepcopy(running))
    monkeypatch.setattr(guard, "validate_windows_listeners", lambda ports: None)
    monkeypatch.setattr(guard, "tcp_ready", lambda port: port != PORTS["postgres"])
    with pytest.raises(guard.GuardError, match="FORWARDING_UNAVAILABLE"):
        staging.ready()
    running[0]["health"] = "starting"
    with pytest.raises(guard.GuardError, match="STAGING_NOT_READY"):
        staging.ready()


def test_ready_rejects_native_windows_shadow_even_with_owned_healthy_docker(
    staging, monkeypatch
):
    staging.linux_root = LINUX_ROOT
    staging.linux_compose = LINUX_ROOT + "/ops/compose.staging.yml"
    staging.ports = PORTS.copy()
    running = [
        container(service)
        for service in ("backend", "frontend", "postgres", "redis", "worker")
    ]
    monkeypatch.setattr(staging, "containers", lambda: running)
    monkeypatch.setattr(guard, "tcp_ready", lambda port: True)
    monkeypatch.setattr(
        guard,
        "native",
        lambda *a, **k: json.dumps({"port": 19001, "process": "python"}),
    )
    with pytest.raises(guard.GuardError, match="WINDOWS_PORT_OWNER"):
        staging.ready()


def test_stop_only_targets_owned_project_and_does_not_delete_volumes(
    session, monkeypatch
):
    staging, keeper = session
    commands = []
    monkeypatch.setattr(
        staging, "compose_command", lambda *a, **k: commands.append((a, k))
    )
    monkeypatch.setattr(
        staging, "ready", lambda: pytest.fail("stop must not demand ready services")
    )
    assert staging.execute(args("stop"))["result"] == "PASS"
    assert commands == [(("down",), {"timeout": 180})]
    assert keeper.stdin.closed


@pytest.mark.parametrize("exit_code", [0, 13])
def test_powershell_wrapper_preserves_literal_argv_and_exit_code(tmp_path, exit_code):
    powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("Optional Windows wrapper integration requires PowerShell")
    root = tmp_path / "mock worktree with spaces"
    wrappers = root / "ops" / "scripts"
    wrappers.mkdir(parents=True)
    scripts = root / "scripts"
    scripts.mkdir()
    canonical = Path(__file__).parents[2] / "ops/scripts/wsl_staging.ps1"
    shutil.copyfile(canonical, wrappers / "wsl_staging.ps1")
    # Replace only the interpreter launcher: no Python, WSL or Docker is called.
    (scripts / "run_python.ps1").write_text(
        "param([string[]]$RequireModule=@(), [string[]]$PythonArgs)\n"
        "$capture=Join-Path $PSScriptRoot '../captured.json'\n"
        "[pscustomobject]@{argv=$PythonArgs; required=$RequireModule; "
        "cwd=(Get-Location).Path} | ConvertTo-Json -Compress | "
        "Set-Content -LiteralPath $capture -Encoding UTF8\n"
        f"$global:LASTEXITCODE={exit_code}\n",
        encoding="utf-8",
    )
    runner = root / "run-wrapper.ps1"
    runner.write_text(
        "& (Join-Path $PSScriptRoot 'ops/scripts/wsl_staging.ps1') "
        "-Action Session -EnvFile 'ops/my staging.env' -Distribution 'Ubuntu-24.04' "
        "-NoBuild -TimeoutSec 240 "
        "-Junit 'output/fresh proof.xml' "
        "-CommandArgs @('validator.exe','value with spaces','literal \"quote\"','literal $()')\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-File", str(runner)],
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == exit_code, result.stderr.decode(errors="replace")
    captured = json.loads((root / "captured.json").read_text(encoding="utf-8-sig"))
    assert captured["required"] == []
    assert Path(captured["cwd"]) == root
    assert captured["argv"] == [
        str(scripts / "wsl_staging.py"),
        "--action",
        "session",
        "--env-file",
        "ops/my staging.env",
        "--distribution",
        "Ubuntu-24.04",
        "--timeout",
        "240",
        "--no-build",
        "--junit",
        "output/fresh proof.xml",
        "--",
        "validator.exe",
        "value with spaces",
        'literal "quote"',
        "literal $()",
    ]
