"""
Тест для воспроизведения ошибки 500 в /registrar/cart
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.crud import clinic as crud_clinic

# Создаем сессию БД
engine = create_engine("sqlite:///./clinic.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    print("[*] Тестирование get_queue_settings...")

    # Вызываем функцию, которая вызывается в create_cart_appointments
    queue_settings = crud_clinic.get_queue_settings(db)

    print("[OK] Функция выполнена успешно!")
    print(f"     Результат: {queue_settings}")

except Exception as e:
    print(f"[ERROR] Ошибка при выполнении:")
    print(f"        Тип: {type(e).__name__}")
    print(f"        Сообщение: {str(e)}")
    import traceback
    print("\n[TRACEBACK]")
    traceback.print_exc()

finally:
    db.close()
