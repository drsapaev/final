from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent


class LifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseTarget:
    url: str
    scheme: str
    user: str
    password: str
    host: str
    port: int
    name: str


def log(message: str) -> None:
    print(message, flush=True)


def pass_message(message: str) -> None:
    print(f"PASS: {message}", flush=True)


def fail(message: str, code: int = 1) -> NoReturn:
    print(f"FAIL: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def require_env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or str(value).strip() == "":
        fail(f"Missing required environment variable: {name}")
    return str(value)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def repo_root() -> Path:
    root = os.environ.get("APP_ROOT")
    if root:
        return Path(root).expanduser().resolve()

    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=SCRIPT_DIR,
            text=True,
        ).strip()
        if output:
            return Path(output).resolve()
    except Exception:
        pass

    return SCRIPT_DIR.parents[2]


def app_root() -> Path:
    return Path(os.environ.get("APP_ROOT", str(repo_root()))).expanduser().resolve()


def backend_dir() -> Path:
    return app_root() / "backend"


def frontend_dir() -> Path:
    return app_root() / "frontend"


def frontend_runtime_probe_script() -> Path:
    return frontend_dir() / "scripts" / "runtime-origin-probe.mjs"


def backend_env_file() -> Path:
    app_env = os.environ.get("APP_ENV", "production")
    return backend_dir() / f".env.{app_env}"


def frontend_env_file() -> Path:
    app_env = os.environ.get("APP_ENV", "production")
    return frontend_dir() / f".env.{app_env}"


def lifecycle_env_file() -> Path:
    explicit = os.environ.get("LIFECYCLE_ENV_FILE")
    if explicit:
        return Path(explicit)

    candidates = [
        app_root() / ".env.clinic-lifecycle",
        app_root() / "clinic_lifecycle.env",
        app_root() / "ops" / "vps" / "clinic_lifecycle.env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value


def load_clinic_env() -> None:
    load_env_file(backend_env_file())
    load_env_file(frontend_env_file())
    load_env_file(lifecycle_env_file())


def backend_python() -> Path:
    candidates = [
        backend_dir() / ".venv" / "bin" / "python",
        backend_dir() / ".venv" / "bin" / "python3",
        backend_dir() / ".venv" / "Scripts" / "python.exe",
        backend_dir() / ".venv" / "Scripts" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def backend_alembic_cmd() -> list[str]:
    return [str(backend_python()), "-m", "alembic"]


def postgres_tool(tool_name: str) -> str:
    stem = Path(tool_name).stem.upper()
    explicit = os.environ.get(f"{stem}_EXE")
    if explicit and Path(explicit).exists():
        return explicit

    candidates: list[Path] = []
    postgres_bin_dir = os.environ.get("POSTGRES_BIN_DIR")
    names = [tool_name]
    if Path(tool_name).suffix.lower() != ".exe":
        names.append(f"{tool_name}.exe")

    if postgres_bin_dir:
        bin_dir = Path(postgres_bin_dir)
        for name in names:
            candidates.append(bin_dir / name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved

    fail(
        "Missing required PostgreSQL executable: "
        f"{tool_name}. Set POSTGRES_BIN_DIR or {stem}_EXE."
    )


def public_url() -> str:
    if os.environ.get("PUBLIC_URL"):
        return os.environ["PUBLIC_URL"].rstrip("/")
    if os.environ.get("APP_HOST"):
        return f"http://{os.environ['APP_HOST'].rstrip('/')}"
    return "http://127.0.0.1:18080"


def backend_url() -> str:
    if os.environ.get("BACKEND_URL"):
        return os.environ["BACKEND_URL"].rstrip("/")
    if os.environ.get("APP_HOST") and os.environ.get("BACKEND_PORT"):
        return f"http://{os.environ['APP_HOST'].rstrip('/')}:{os.environ['BACKEND_PORT']}"
    if os.environ.get("APP_HOST"):
        return f"http://{os.environ['APP_HOST'].rstrip('/')}:18000"
    return "http://127.0.0.1:18000"


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    printable = shlex.join(args)
    log(f"+ {printable}")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)

    if check and result.returncode != 0:
        raise LifecycleError(
            f"Command failed with exit code {result.returncode}: {printable}"
        )

    return result


def http_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[int, Any, str]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if raw:
                try:
                    return response.status, json.loads(raw), raw
                except json.JSONDecodeError:
                    return response.status, raw, raw
            return response.status, None, raw
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed, raw
    except URLError as exc:
        raise LifecycleError(f"Failed to reach {url}: {exc.reason}") from exc


def read_json_payload(path: str | None, inline_json: str | None = None) -> dict[str, Any] | None:
    if inline_json:
        return json.loads(inline_json)

    if not path:
        return None

    payload_path = Path(path)
    if not payload_path.exists():
        fail(f"Payload file not found: {payload_path}")

    return json.loads(payload_path.read_text(encoding="utf-8"))


def parse_database_url(url: str) -> DatabaseTarget:
    if not url:
        fail("DATABASE_URL is required")

    normalized = (
        url.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+psycopg2://", "postgresql://")
    )
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"}:
        fail(f"Unsupported database scheme in URL: {url}")

    name = parsed.path.lstrip("/")
    if not name:
        fail(f"Database name is missing in URL: {url}")

    return DatabaseTarget(
        url=url,
        scheme=parsed.scheme,
        user=parsed.username or "",
        password=parsed.password or "",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        name=name,
    )


def git_head(root: Path | None = None) -> str:
    checkout = root or app_root()
    result = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=str(checkout),
        text=True,
    ).strip()
    return result


def ensure_tool(name: str) -> None:
    if (
        subprocess.run(
            ["bash", "-lc", f"command -v {shlex.quote(name)} >/dev/null 2>&1"]
        ).returncode
        != 0
    ):
        fail(f"Missing required command: {name}")


def ensure_script(path: Path) -> None:
    if not path.exists():
        fail(f"Missing required script: {path}")


def temp_file(suffix: str = "") -> tempfile.NamedTemporaryFile:
    return tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
