#!/usr/bin/env python3
"""
Скрипт для запуска backend без принудительного отката на SQLite.
"""
from pathlib import Path
import os
import socket
import sys
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn


current_dir = Path(__file__).resolve().parent
os.chdir(current_dir)
os.environ["PYTHONPATH"] = str(current_dir)
os.environ.setdefault("WS_DEV_ALLOW", "1")
os.environ.setdefault("CORS_DISABLE", "0")
os.environ.setdefault("REQUIRE_LICENSE", "0")

sys.path.insert(0, str(current_dir))


def env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def debugger_attached() -> bool:
    return sys.gettrace() is not None or "debugpy" in sys.modules or bool(os.environ.get("DEBUGPY_LAUNCHER_PORT"))


def port_available(host: str, port: int) -> tuple[bool, str | None]:
    for check_host in ("127.0.0.1", "localhost"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check_sock:
            check_sock.settimeout(0.2)
            if check_sock.connect_ex((check_host, port)) == 0:
                return False, f"local listener already accepts connections on {check_host}:{port}"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True, None
    except OSError as exc:
        return False, str(exc)
    finally:
        sock.close()


def existing_backend_status(port: int) -> str | None:
    url = f"http://127.0.0.1:{port}/api/v1/health"
    try:
        with urlopen(url, timeout=2) as response:
            return response.read().decode("utf-8")
    except (OSError, URLError):
        return None


def main() -> int:
    env_file = current_dir / ".env"
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", "18000"))
    under_debugger = debugger_attached()
    reload_enabled = env_flag("BACKEND_RELOAD", default=not under_debugger)

    print("Starting backend server with project settings...")
    print(f"Working directory: {current_dir}")
    print(f"Env file: {env_file}")
    print(f"DATABASE_URL env: {os.environ.get('DATABASE_URL', '<loaded by backend settings>')}")
    print(f"Python path: {os.environ['PYTHONPATH']}")
    print(f"[FIX:START] Host={host} Port={port} Reload={reload_enabled}")

    if under_debugger and "BACKEND_RELOAD" not in os.environ:
        print("[FIX:START] Debugger detected; reload disabled by default for stable Windows startup.")

    available, bind_error = port_available(host, port)
    if not available:
        print(f"[FIX:START] Cannot bind {host}:{port}: {bind_error}")
        health_status = existing_backend_status(port)
        if health_status:
            print(f"[FIX:START] Existing backend already отвечает на http://127.0.0.1:{port}/api/v1/health -> {health_status}")
            print("[FIX:START] Launcher will exit without error because the backend is already healthy.")
            return 0
        print(f"[FIX:START] Stop the existing process or run with BACKEND_PORT={port + 1}.")
        return 1

    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload_enabled,
            log_level="info",
            access_log=True,
        )
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            print(f"[FIX:START] Missing dependency '{exc.name}' in interpreter: {sys.executable}")
            print("[FIX:START] Use backend/.venv/Scripts/python.exe or install backend requirements into the active venv.")
            return 1
        raise

    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        sys.exit(exit_code)
