#!/usr/bin/env python3
"""
Скрипт для переноса услуг из .txt файла в справочник с кодами K/D/C/L/S/O
Основан на файле: Услуги и врачи в нашей клинике.txt
"""

import asyncio
import os
from decimal import Decimal


def require_seed_services_wizard_confirmation():
    if os.getenv("CONFIRM_SEED_SERVICES_WIZARD") != "1":
        raise RuntimeError(
            "Refusing to seed wizard services. "
            "Set CONFIRM_SEED_SERVICES_WIZARD=1 only for an explicit catalog seed run."
        )

# Данные из файла "Услуги и врачи в нашей клинике.txt"
def require_postgres_database_url() -> None:
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before seeding wizard services.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("seed_services_wizard.py requires a PostgreSQL DATABASE_URL.")


SERVICES_DATA = [
    # ===== ЛАБОРАТОРНЫЕ АНАЛИЗЫ (L) =====
    # Общий анализ крови
    {"name": "Общий анализ крови", "category_code": "L", "service_code": "L001", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Гемоглобин", "category_code": "L", "service_code": "L002", "price": 15000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Время свертываемости крови", "category_code": "L", "service_code": "L003", "price": 20000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # Биохимические анализы крови
    {"name": "Общий белок", "category_code": "L", "service_code": "L004", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Глюкоза", "category_code": "L", "service_code": "L005", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Холестерин", "category_code": "L", "service_code": "L006", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Мочевина", "category_code": "L", "service_code": "L007", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Креатинин", "category_code": "L", "service_code": "L008", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "АлАТ (аланинаминотрансфераза)", "category_code": "L", "service_code": "L009", "price": 40000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "АсАТ (аспартотаминотрансфераза)", "category_code": "L", "service_code": "L010", "price": 40000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Билирубин (общий, прямой, непрямой)", "category_code": "L", "service_code": "L011", "price": 45000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Щелочная фосфатаза", "category_code": "L", "service_code": "L012", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Альфа-амилаза", "category_code": "L", "service_code": "L013", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Калий", "category_code": "L", "service_code": "L014", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Кальций", "category_code": "L", "service_code": "L015", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Натрий", "category_code": "L", "service_code": "L016", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Витамин Д", "category_code": "L", "service_code": "L017", "price": 80000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Гликированный гемоглобин (HbA1C)", "category_code": "L", "service_code": "L018", "price": 60000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Общий анализ мочи", "category_code": "L", "service_code": "L019", "price": 20000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Желчные пигменты в моче", "category_code": "L", "service_code": "L020", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # Экспресс тесты
    {"name": "HBsAg Экспресс тест", "category_code": "L", "service_code": "L021", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "HCV Экспресс тест", "category_code": "L", "service_code": "L022", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "HIV Экспресс тест", "category_code": "L", "service_code": "L023", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "RW Экспресс тест", "category_code": "L", "service_code": "L024", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Спермограмма", "category_code": "L", "service_code": "L025", "price": 100000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Глюкоза натощак", "category_code": "L", "service_code": "L026", "price": 15000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Глюкоза после нагрузки", "category_code": "L", "service_code": "L027", "price": 20000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # Ревматоидные факторы
    {"name": "Ревматоидный фактор (RF)", "category_code": "L", "service_code": "L028", "price": 40000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "С-реактивный белок (CRP)", "category_code": "L", "service_code": "L029", "price": 40000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Антистрептолизин-О (ASlO)", "category_code": "L", "service_code": "L030", "price": 45000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Бруцеллез (Rose Bengal)", "category_code": "L", "service_code": "L031", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # Гормоны щитовидной железы
    {"name": "ТТГ (тиреотропный гормон)", "category_code": "L", "service_code": "L032", "price": 60000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Т4 (тироксин)", "category_code": "L", "service_code": "L033", "price": 60000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Т3 (трийодтиронин)", "category_code": "L", "service_code": "L034", "price": 60000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "АТ-ТПО (аутоантитело к тиреопероксидазе)", "category_code": "L", "service_code": "L035", "price": 70000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Тестостерон", "category_code": "L", "service_code": "L036", "price": 70000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # Микробиология
    {"name": "Нити грибки", "category_code": "L", "service_code": "L037", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Malassezia furfur", "category_code": "L", "service_code": "L038", "price": 40000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Демодекоз", "category_code": "L", "service_code": "L039", "price": 35000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Мазок на степень чистоты", "category_code": "L", "service_code": "L040", "price": 30000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Кал на яйца глистов", "category_code": "L", "service_code": "L041", "price": 25000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Иммуноглобулин Е", "category_code": "L", "service_code": "L042", "price": 80000, "queue_tag": "lab", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # ===== КАРДИОЛОГИЯ (K) =====
    {"name": "Консультация кардиолога", "category_code": "K", "service_code": "K01", "price": 150000, "queue_tag": "cardiology_common", "requires_doctor": True, "is_consultation": True, "allow_doctor_price_override": False},
    {"name": "ЭКГ", "category_code": "K", "service_code": "K10", "price": 50000, "queue_tag": "ecg", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "ЭхоКГ", "category_code": "K", "service_code": "K11", "price": 200000, "queue_tag": "cardiology_common", "requires_doctor": True, "is_consultation": False, "allow_doctor_price_override": False},
    
    # ===== СТОМАТОЛОГИЯ (S) =====
    {"name": "Консультация стоматолога", "category_code": "S", "service_code": "S001", "price": 100000, "queue_tag": "stomatology", "requires_doctor": True, "is_consultation": True, "allow_doctor_price_override": True},
    {"name": "Рентгенография зуба", "category_code": "S", "service_code": "S002", "price": 80000, "queue_tag": "stomatology", "requires_doctor": True, "is_consultation": False, "allow_doctor_price_override": True},
    
    # ===== ДЕРМАТОЛОГИЯ (D) =====
    {"name": "Консультация дерматолога", "category_code": "D", "service_code": "D001", "price": 120000, "queue_tag": "dermatology", "requires_doctor": True, "is_consultation": True, "allow_doctor_price_override": False},
    {"name": "Криодеструкция бородавок", "category_code": "D", "service_code": "D002", "price": 80000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Криодеструкция папиллом", "category_code": "D", "service_code": "D003", "price": 70000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Мезотерапия келлоидных рубцов", "category_code": "D", "service_code": "D004", "price": 150000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    
    # Физиотерапия дерматологическая
    {"name": "Дарсонваль", "category_code": "D", "service_code": "D005", "price": 40000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "УФО терапия", "category_code": "D", "service_code": "D006", "price": 45000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Диодная маска лица", "category_code": "D", "service_code": "D007", "price": 60000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Биоптрон - светотерапия", "category_code": "D", "service_code": "D008", "price": 50000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    {"name": "Эксимер лазер", "category_code": "D", "service_code": "D009", "price": 100000, "queue_tag": "dermatology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": False},
    
    # ===== КОСМЕТОЛОГИЯ (C) =====
    {"name": "Консультация косметолога", "category_code": "C", "service_code": "C001", "price": 100000, "queue_tag": "cosmetology", "requires_doctor": True, "is_consultation": True, "allow_doctor_price_override": False},
    {"name": "Плазмолифтинг лица", "category_code": "C", "service_code": "C002", "price": 300000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Плазмолифтинг волос", "category_code": "C", "service_code": "C003", "price": 250000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Мезотерапия", "category_code": "C", "service_code": "C004", "price": 200000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Чистка лица", "category_code": "C", "service_code": "C005", "price": 150000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Безоперационная блефаропластика", "category_code": "C", "service_code": "C006", "price": 400000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Удаление жировиков", "category_code": "C", "service_code": "C007", "price": 120000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Лазерное удаление татуажа", "category_code": "C", "service_code": "C008", "price": 180000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Лазерное удаление татуировок", "category_code": "C", "service_code": "C009", "price": 200000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
    {"name": "Карбоновый пилинг", "category_code": "C", "service_code": "C010", "price": 180000, "queue_tag": "cosmetology", "requires_doctor": False, "is_consultation": False, "allow_doctor_price_override": True},
]

# Категории услуг
CATEGORIES_DATA = [
    {"code": "K", "name_ru": "Кардиология", "name_uz": "Kardiologiya", "specialty": "cardiology"},
    {"code": "D", "name_ru": "Дерматология", "name_uz": "Dermatologiya", "specialty": "dermatology"},
    {"code": "C", "name_ru": "Косметология", "name_uz": "Kosmetologiya", "specialty": "cosmetology"},
    {"code": "L", "name_ru": "Лабораторные анализы", "name_uz": "Laboratoriya tahlillari", "specialty": "laboratory"},
    {"code": "S", "name_ru": "Стоматология", "name_uz": "Stomatologiya", "specialty": "stomatology"},
    {"code": "O", "name_ru": "Прочие процедуры", "name_uz": "Boshqa protseduralar", "specialty": "other"},
]


def seed_services():
    """Заполнение справочника услуг"""
    require_seed_services_wizard_confirmation()
    require_postgres_database_url()

    from app.db.session import SessionLocal
    from app.models.clinic import ServiceCategory
    from app.models.service import Service

    db = SessionLocal()
    try:
        print("🔄 Начинаем заполнение справочника услуг...")
        
        # 1. Создаем категории
        print("📁 Создание категорий услуг...")
        for cat_data in CATEGORIES_DATA:
            existing_cat = db.query(ServiceCategory).filter(ServiceCategory.code == cat_data["code"]).first()
            if not existing_cat:
                category = ServiceCategory(**cat_data)
                db.add(category)
                print(f"  ✅ Создана категория: {cat_data['name_ru']} ({cat_data['code']})")
            else:
                print(f"  ⏭️  Категория уже существует: {cat_data['name_ru']} ({cat_data['code']})")
        
        db.commit()
        
        # 2. Создаем услуги
        print("🏥 Создание услуг...")
        for service_data in SERVICES_DATA:
            existing_service = db.query(Service).filter(Service.service_code == service_data["service_code"]).first()
            if not existing_service:
                # Найдем категорию
                category = db.query(ServiceCategory).filter(ServiceCategory.code == service_data["category_code"]).first()
                
                service = Service(
                    name=service_data["name"],
                    code=service_data["service_code"],
                    price=Decimal(str(service_data["price"])),
                    currency="UZS",
                    active=True,
                    category_code=service_data["category_code"],
                    service_code=service_data["service_code"],
                    requires_doctor=service_data["requires_doctor"],
                    queue_tag=service_data["queue_tag"],
                    is_consultation=service_data["is_consultation"],
                    allow_doctor_price_override=service_data["allow_doctor_price_override"],
                    category_id=category.id if category else None,
                    duration_minutes=30,  # По умолчанию 30 минут
                )
                db.add(service)
                print(f"  ✅ Создана услуга: {service_data['name']} ({service_data['service_code']}) - {service_data['price']} сум")
            else:
                print(f"  ⏭️  Услуга уже существует: {service_data['name']} ({service_data['service_code']})")
        
        db.commit()
        
        # 3. Статистика
        total_services = db.query(Service).count()
        total_categories = db.query(ServiceCategory).count()
        
        print(f"\n📊 Статистика:")
        print(f"  📁 Всего категорий: {total_categories}")
        print(f"  🏥 Всего услуг: {total_services}")
        
        # Статистика по категориям
        for cat_data in CATEGORIES_DATA:
            count = db.query(Service).filter(Service.category_code == cat_data["code"]).count()
            print(f"  {cat_data['code']}: {cat_data['name_ru']} - {count} услуг")
        
        print("\n✅ Заполнение справочника завершено успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка при заполнении справочника: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_services()
