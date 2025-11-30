"""
Конфигурация логирования для приложения
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
) -> None:
    """
    Настройка логирования для приложения

    Args:
        level: Уровень логирования (по умолчанию INFO)
        format_string: Формат строки лога (если None, используется стандартный)
        date_format: Формат даты/времени (если None, используется стандартный)
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if date_format is None:
        date_format = "%Y-%m-%d %H:%M:%S"

    # Настройка root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Настройка уровней для специфичных логгеров
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

    # Логгер для приложения
    app_logger = logging.getLogger("clinic")
    app_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Получить логгер для модуля

    Args:
        name: Имя модуля (обычно __name__)

    Returns:
        Настроенный logger
    """
    return logging.getLogger(name)
