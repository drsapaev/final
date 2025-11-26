"""
Инициализация таблицы departments с начальными данными
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.department import Department

# Создаем engine и сессию
engine = create_engine("sqlite:///./clinic.db", echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем таблицу
Base.metadata.create_all(bind=engine, tables=[Department.__table__])

# Начальные данные
INITIAL_DEPARTMENTS = [
    {
        "key": "cardio",
        "name_ru": "Кардиология",
        "name_uz": "Kardiologiya",
        "icon": "heart",
        "display_order": 1,
        "active": True
    },
    {
        "key": "echokg",
        "name_ru": "ЭКГ",
        "name_uz": "EKG",
        "icon": "activity",
        "display_order": 2,
        "active": True
    },
    {
        "key": "derma",
        "name_ru": "Дерматология",
        "name_uz": "Dermatologiya",
        "icon": "droplet",
        "display_order": 3,
        "active": True
    },
    {
        "key": "dental",
        "name_ru": "Стоматология",
        "name_uz": "Stomatologiya",
        "icon": "smile",
        "display_order": 4,
        "active": True
    },
    {
        "key": "lab",
        "name_ru": "Лаборатория",
        "name_uz": "Laboratoriya",
        "icon": "flask",
        "display_order": 5,
        "active": True
    },
    {
        "key": "procedures",
        "name_ru": "Процедуры",
        "name_uz": "Protseduralar",
        "icon": "clipboard-list",
        "display_order": 6,
        "active": True
    }
]

def init_departments():
    """Инициализация отделений"""
    db = SessionLocal()
    try:
        # Проверяем есть ли уже отделения
        existing_count = db.query(Department).count()
        if existing_count > 0:
            print(f"✅ Отделения уже существуют ({existing_count} записей)")
            return

        # Создаем отделения
        for dept_data in INITIAL_DEPARTMENTS:
            dept = Department(**dept_data)
            db.add(dept)

        db.commit()
        print(f"✅ Создано {len(INITIAL_DEPARTMENTS)} отделений")

        # Выводим созданные отделения
        departments = db.query(Department).order_by(Department.display_order).all()
        for dept in departments:
            print(f"   {dept.display_order}. {dept.key}: {dept.name_ru} ({dept.icon})")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Инициализация таблицы departments...")
    init_departments()
