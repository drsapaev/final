#!/usr/bin/env python3
"""
Создание таблиц для системы очередей
"""
import sys
import os

# Добавляем путь к backend
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import engine
from app.models.queue_new import DailyQueue, QueueEntry, QueueToken
from app.db.base_class import Base

def create_tables():
    """Создание таблиц очереди"""
    print("🔧 Создаем таблицы для системы очередей...")
    
    try:
        # Создаем только наши новые таблицы
        DailyQueue.__table__.create(engine, checkfirst=True)
        print("✅ Создана таблица daily_queues_new")
        
        QueueEntry.__table__.create(engine, checkfirst=True)
        print("✅ Создана таблица queue_entries_new")
        
        QueueToken.__table__.create(engine, checkfirst=True)
        print("✅ Создана таблица queue_tokens_new")
        
        print("🎉 Все таблицы созданы успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return False

if __name__ == "__main__":
    success = create_tables()
    if success:
        print("✨ Готово! Теперь можно тестировать API.")
    else:
        print("💥 Не удалось создать таблицы.")
