#!/usr/bin/env python3
"""
Тест CRUD функций вебхуков
"""
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.crud.payment_webhook import (count_transactions, count_webhooks,
                                      get_all_transactions, get_all_webhooks)
from app.db.session import get_db


def test_crud_functions():
    """Тестируем CRUD функции"""
    print("🚀 Тест CRUD функций вебхуков")
    print("=" * 50)

    try:
        # Получаем сессию БД
        db = next(get_db())
        print("✅ Подключение к БД установлено")

        # Тест 1: Подсчёт вебхуков
        print("\n📊 Тест подсчёта вебхуков...")
        try:
            webhook_count = count_webhooks(db)
            print(f"✅ Количество вебхуков: {webhook_count}")
        except Exception as e:
            print(f"❌ Ошибка подсчёта вебхуков: {e}")

        # Тест 2: Получение всех вебхуков
        print("\n📋 Тест получения всех вебхуков...")
        try:
            webhooks = get_all_webhooks(db)
            print(f"✅ Получено вебхуков: {len(webhooks)}")
            if webhooks:
                print(f"  Первый вебхук: {webhooks[0]}")
        except Exception as e:
            print(f"❌ Ошибка получения вебхуков: {e}")

        # Тест 3: Подсчёт транзакций
        print("\n💳 Тест подсчёта транзакций...")
        try:
            transaction_count = count_transactions(db)
            print(f"✅ Количество транзакций: {transaction_count}")
        except Exception as e:
            print(f"❌ Ошибка подсчёта транзакций: {e}")

        # Тест 4: Получение всех транзакций
        print("\n💳 Тест получения всех транзакций...")
        try:
            transactions = get_all_transactions(db)
            print(f"✅ Получено транзакций: {len(transactions)}")
            if transactions:
                print(f"  Первая транзакция: {transactions[0]}")
        except Exception as e:
            print(f"❌ Ошибка получения транзакций: {e}")
            import traceback

            traceback.print_exc()

        db.close()
        print("\n✅ Тест завершён")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_crud_functions()
