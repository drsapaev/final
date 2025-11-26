#!/usr/bin/env python3
"""
Скрипт для запуска сервера с правильными настройками
"""
import os
import sys
import uvicorn

# Получаем текущую директорию
current_dir = os.path.dirname(os.path.abspath(__file__))

# Устанавливаем правильные переменные окружения
os.environ["DATABASE_URL"] = "sqlite:///./clinic.db"
os.environ["PYTHONPATH"] = current_dir

# Добавляем путь к проекту
sys.path.insert(0, current_dir)

if __name__ == "__main__":
    print("🚀 Запуск сервера с правильными настройками...")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🗄️ База данных: {os.environ['DATABASE_URL']}")
    print(f"🐍 Python path: {os.environ['PYTHONPATH']}")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
