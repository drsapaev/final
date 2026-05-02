#!/usr/bin/env python3
"""
Простой скрипт для запуска FastAPI сервера
"""
import uvicorn

from app.main import app

if __name__ == "__main__":
    print("🚀 Запускаем FastAPI сервер...")
    print("📡 Хост: 0.0.0.0")
    print("🔌 Порт: 18000")
    print("🌐 CORS: включен для localhost:5173")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=18000, reload=False, log_level="info")
