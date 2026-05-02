#!/usr/bin/env python3
"""
Скрипт для запуска сервера с ПОЛНЫМ логированием
"""
import logging
import os
import sys
import uvicorn

# Настраиваем логирование ДО импорта приложения
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Явно настраиваем все логгеры
for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "clinic"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)

# Получаем текущую директорию
current_dir = os.path.dirname(os.path.abspath(__file__))

# Устанавливаем правильные переменные окружения
os.environ["DATABASE_URL"] = "sqlite:///./clinic.db"
os.environ["PYTHONPATH"] = current_dir

# Добавляем путь к проекту
sys.path.insert(0, current_dir)

if __name__ == "__main__":
    PORT = int(os.environ.get("BACKEND_PORT", "18000"))

    print("=" * 80)
    print("🚀 ЗАПУСК СЕРВЕРА С ПОЛНЫМ ЛОГИРОВАНИЕМ")
    print("=" * 80)
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🗄️ База данных: {os.environ['DATABASE_URL']}")
    print(f"🐍 Python path: {os.environ['PYTHONPATH']}")
    print(f"🌐 Порт: {PORT}")
    print("=" * 80)
    
    # Конфигурация uvicorn с МАКСИМАЛЬНЫМ логированием
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,  # Отключаем reload для стабильности
        log_level="info",
        access_log=True,  # ВКЛЮЧАЕМ логи доступа
        use_colors=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "access": {
                    "format": '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
                "access": {
                    "formatter": "access",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
            },
        },
    )
