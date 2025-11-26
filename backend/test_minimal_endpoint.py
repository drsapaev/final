#!/usr/bin/env python3
"""
Минимальный тест endpoint
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from fastapi import FastAPI
from app.api.v1.endpoints.queue import router
import uvicorn

# Создаем минимальное приложение для тестирования
app = FastAPI()
app.include_router(router, prefix="/queue")

@app.get("/test")
def test_endpoint():
    return {"status": "ok", "message": "Test endpoint works"}

if __name__ == "__main__":
    print("🚀 Запуск тестового сервера...")
    print("Доступные endpoints:")
    print("- GET  /test")
    print("- POST /queue/join")
    print("- POST /queue/qrcode")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
