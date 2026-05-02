#!/usr/bin/env python3
"""
Скрипт для запуска сервера на порту 8001 (если основной порт занят)
"""
import logging
import os
import sys
import uvicorn

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Явно настраиваем все логгеры
for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "clinic"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

# Получаем текущую директорию
current_dir = os.path.dirname(os.path.abspath(__file__))

# Устанавливаем правильные переменные окружения
os.environ["DATABASE_URL"] = "sqlite:///./clinic.db"
os.environ["PYTHONPATH"] = current_dir

# Добавляем путь к проекту
sys.path.insert(0, current_dir)

if __name__ == "__main__":
    PORT = 8001
    
    print("=" * 80)
    print("🚀 Запуск сервера на альтернативном порту")
    print("=" * 80)
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🗄️ База данных: {os.environ['DATABASE_URL']}")
    print(f"🌐 Порт: {PORT}")
    print("=" * 80)
    print()
    print("⚠️  ВАЖНО: Обновите frontend для работы с портом 8001!")
    print(f"   В файле frontend/.env установите: VITE_API_URL=http://localhost:{PORT}")
    print("=" * 80)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info",
        access_log=True
    )
