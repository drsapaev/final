#!/usr/bin/env python3
"""
VS Code launch entrypoint for the FastAPI backend.

Launched by `.vscode/launch.json` → "Backend: FastAPI (run_server.py)".
Simple wrapper around uvicorn so the IDE debugger can attach.

For non-IDE workflows prefer:
    uvicorn app.main:app --reload --port 18000
"""
import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")  # nosec B104 — intentional bind to all interfaces for dev server
    port = int(os.environ.get("BACKEND_PORT", "18000"))
    reload = os.environ.get("BACKEND_RELOAD", "1") == "1"

    print("Запускаем FastAPI сервер...")
    print(f"[FIX:START] Host={host} Port={port} Reload={reload}")
    uvicorn.run(app, host=host, port=port, reload=reload, log_level="info")
