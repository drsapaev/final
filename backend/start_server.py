#!/usr/bin/env python3
"""
Скрипт для запуска backend без принудительного отката на SQLite.
"""
from pathlib import Path
import os
import sys

import uvicorn


current_dir = Path(__file__).resolve().parent
os.chdir(current_dir)
os.environ["PYTHONPATH"] = str(current_dir)
os.environ.setdefault("WS_DEV_ALLOW", "1")
os.environ.setdefault("CORS_DISABLE", "0")
os.environ.setdefault("REQUIRE_LICENSE", "0")

sys.path.insert(0, str(current_dir))


if __name__ == "__main__":
    env_file = current_dir / ".env"
    print("Starting backend server with project settings...")
    print(f"Working directory: {current_dir}")
    print(f"Env file: {env_file}")
    print(f"DATABASE_URL env: {os.environ.get('DATABASE_URL', '<loaded by backend settings>')}")
    print(f"Python path: {os.environ['PYTHONPATH']}")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
    )
