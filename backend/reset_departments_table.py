"""
Скрипт для удаления старой таблицы departments и создания новой с правильной структурой
"""
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.department import Department

# Подключение к БД
DB_PATH = "./clinic.db"

def reset_departments_table():
    """Удалить старую таблицу и создать новую"""

    print("[*] Удаление старой таблицы departments...")

    # Используем sqlite3 для удаления таблицы
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS departments")
        conn.commit()
        conn.close()
        print("[OK] Старая таблица departments удалена")
    except Exception as e:
        print(f"[ERROR] Ошибка при удалении таблицы: {e}")
        return False

    # Создаем новую таблицу через SQLAlchemy
    print("\n[*] Создание новой таблицы departments...")
    try:
        engine = create_engine(f"sqlite:///{DB_PATH}", echo=True)
        Base.metadata.create_all(bind=engine, tables=[Department.__table__])
        print("[OK] Новая таблица departments создана")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка при создании таблицы: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("RESET DEPARTMENTS TABLE")
    print("=" * 60)

    if reset_departments_table():
        print("\n[OK] Таблица успешно пересоздана")
        print("Теперь можно запустить: python init_departments.py")
    else:
        print("\n[ERROR] Не удалось пересоздать таблицу")
