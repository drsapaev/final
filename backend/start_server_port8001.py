#!/usr/bin/env python3
"""
Скрипт для запуска сервера на порту 8001 (если основной порт занят)
"""
import logging
import os
import sys
import uvicorn
from sqlalchemy.engine import make_url

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
os.environ["PYTHONPATH"] = current_dir

# Добавляем путь к проекту
sys.path.insert(0, current_dir)


def require_database_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        from app.core.config import get_settings

        database_url = str(get_settings().DATABASE_URL or "").strip()

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required; refusing to start the backend with a fallback database"
        )

    os.environ["DATABASE_URL"] = database_url
    return database_url


def display_database_url(database_url: str) -> str:
    return make_url(database_url).render_as_string(hide_password=True)


if __name__ == "__main__":
    PORT = 8001
    DATABASE_URL = require_database_url()
    
    print("=" * 80)
    print("🚀 Запуск сервера на альтернативном порту")
    print("=" * 80)
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🗄️ База данных: {display_database_url(DATABASE_URL)}")
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
