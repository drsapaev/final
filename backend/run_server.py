#!/usr/bin/env python3
"""
Простой скрипт для запуска FastAPI сервера
"""
import os

import uvicorn

from app.main import app

if __name__ == "__main__":
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", "18000"))

    print("Запускаем FastAPI сервер...")
    print(f"[FIX:START] Host={host} Port={port}")
    uvicorn.run(app, host=host, port=port, reload=False, log_level="info")
