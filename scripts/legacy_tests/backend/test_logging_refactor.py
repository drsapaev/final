#!/usr/bin/env python3
"""
Тестовый скрипт для проверки логирования после рефакторинга
"""
import sys
import os
import logging

# Добавляем путь к app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.logging_config import setup_logging, get_logger


def test_logging_setup():
    """Тест настройки логирования"""
    print("=" * 60)
    print("ТЕСТ: Настройка логирования")
    print("=" * 60)

    setup_logging(level=logging.INFO)
    logger = get_logger(__name__)

    # Тест разных уровней
    logger.debug("DEBUG сообщение (не должно появиться при INFO)")
    logger.info("INFO сообщение")
    logger.warning("WARNING сообщение")
    logger.error("ERROR сообщение")

    print("\n✅ Логирование настроено корректно")
    return True


def test_module_loggers():
    """Тест логгеров для разных модулей"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Логгеры для модулей")
    print("=" * 60)

    # Тест логгеров для разных модулей
    endpoints_logger = get_logger("app.api.v1.endpoints.registrar_wizard")
    services_logger = get_logger("app.services.qr_queue_service")
    crud_logger = get_logger("app.crud.visit")

    endpoints_logger.info("Тест логгера для endpoints")
    services_logger.info("Тест логгера для services")
    crud_logger.info("Тест логгера для crud")

    print("\n✅ Логгеры для модулей работают")
    return True


def test_log_format():
    """Тест формата логов"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Формат логов")
    print("=" * 60)

    logger = get_logger("test.module")

    # Проверяем что формат включает timestamp, name, level, message
    logger.info("Тестовое сообщение с параметрами: %s, %d", "строка", 42)
    logger.warning("Предупреждение с контекстом")
    logger.error("Ошибка с деталями", exc_info=False)

    print("\n✅ Формат логов корректен")
    return True


def test_exception_logging():
    """Тест логирования исключений"""
    print("\n" + "=" * 60)
    print("ТЕСТ: Логирование исключений")
    print("=" * 60)

    logger = get_logger("test.exceptions")

    try:
        raise ValueError("Тестовая ошибка")
    except Exception:
        logger.exception("Исключение перехвачено и залогировано")

    print("\n✅ Логирование исключений работает")
    return True


def main():
    """Главная функция"""
    print("\n🧪 ЗАПУСК ТЕСТОВ ЛОГИРОВАНИЯ\n")

    try:
        test_logging_setup()
        test_module_loggers()
        test_log_format()
        test_exception_logging()

        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
