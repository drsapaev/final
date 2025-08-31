#!/usr/bin/env python3
"""
Простой скрипт для запуска FastAPI сервера
"""
import uvicorn
from app.main import app

if __name__ == "__main__":
    print("🚀 Запускаем FastAPI сервер...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
