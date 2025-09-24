#!/usr/bin/env python3
"""
Скрипт для инициализации базового справочника услуг
Создает категории услуг и базовые услуги согласно утвержденному плану
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.session import _get_db_url_from_env_or_settings
from app.models.clinic import ServiceCategory
from app.models.service import Service
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_service_categories():
    """Создание категорий услуг"""
    categories = [
        {
            'code': 'cardiology',
            'name_ru': 'Кардиология',
            'name_uz': 'Kardiologiya',
            'name_en': 'Cardiology',
            'specialty': 'cardiology',
            'active': True
        },
        {
            'code': 'dermatology',
            'name_ru': 'Дерматология',
            'name_uz': 'Dermatologiya',
            'name_en': 'Dermatology',
            'specialty': 'dermatology',
            'active': True
        },
        {
            'code': 'cosmetology',
            'name_ru': 'Косметология',
            'name_uz': 'Kosmetologiya',
            'name_en': 'Cosmetology',
            'specialty': 'cosmetology',
            'active': True
        },
        {
            'code': 'dentistry',
            'name_ru': 'Стоматология',
            'name_uz': 'Stomatologiya',
            'name_en': 'Dentistry',
            'specialty': 'dentistry',
            'active': True
        },
        {
            'code': 'laboratory',
            'name_ru': 'Лаборатория',
            'name_uz': 'Laboratoriya',
            'name_en': 'Laboratory',
            'specialty': 'laboratory',
            'active': True
        },
        {
            'code': 'other',
            'name_ru': 'Прочие услуги',
            'name_uz': 'Boshqa xizmatlar',
            'name_en': 'Other services',
            'specialty': 'other',
            'active': True
        }
    ]
    
    return categories

def seed_services():
    """Создание базовых услуг"""
    services = [
        # Кардиология
        {
            'code': 'consultation.cardiology',
            'name': 'Консультация кардиолога',
            'department': 'cardiology',
            'unit': 'консультация',
            'price': 50000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        },
        {
            'code': 'echo.cardiography',
            'name': 'ЭхоКГ',
            'department': 'cardiology',
            'unit': 'исследование',
            'price': 80000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        },
        {
            'code': 'ecg',
            'name': 'ЭКГ',
            'department': 'cardiology',
            'unit': 'исследование',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 15,
            'active': True
        },
        
        # Дерматология
        {
            'code': 'consultation.dermatology',
            'name': 'Консультация дерматолога',
            'department': 'dermatology',
            'unit': 'консультация',
            'price': 40000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        },
        {
            'code': 'derm.skin_diagnostics',
            'name': 'Дерматоскопия',
            'department': 'dermatology',
            'unit': 'исследование',
            'price': 30000.00,
            'currency': 'UZS',
            'duration_minutes': 20,
            'active': True
        },
        
        # Косметология
        {
            'code': 'cosmetology.botox',
            'name': 'Ботулотоксин',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 150000.00,
            'currency': 'UZS',
            'duration_minutes': 60,
            'active': True
        },
        {
            'code': 'cosmetology.mesotherapy',
            'name': 'Мезотерапия',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 120000.00,
            'currency': 'UZS',
            'duration_minutes': 45,
            'active': True
        },
        {
            'code': 'cosmetology.peel',
            'name': 'Пилинг',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 40000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        },
        {
            'code': 'cosmetology.laser',
            'name': 'Лазерные процедуры',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 80000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        },
        
        # Стоматология
        {
            'code': 'consultation.dentistry',
            'name': 'Консультация стоматолога',
            'department': 'dentistry',
            'unit': 'консультация',
            'price': 35000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        },
        
        # Лаборатория
        {
            'code': 'lab.cbc',
            'name': 'Общий анализ крови',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True
        },
        {
            'code': 'lab.biochem',
            'name': 'Биохимический анализ крови',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True
        },
        {
            'code': 'lab.urine',
            'name': 'Общий анализ мочи',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True
        },
        {
            'code': 'lab.coag',
            'name': 'Коагулограмма',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 20000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True
        },
        {
            'code': 'lab.hormones',
            'name': 'Гормоны',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 30000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True
        },
        {
            'code': 'lab.infection',
            'name': 'Инфекции/серология',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True
        },
        
        # Прочие
        {
            'code': 'other.general',
            'name': 'Прочие процедуры',
            'department': 'other',
            'unit': 'процедура',
            'price': 20000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True
        }
    ]
    
    return services

def main():
    """Основная функция инициализации"""
    try:
        # Создаем подключение к базе данных
        db_url = _get_db_url_from_env_or_settings()
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as db:
            logger.info("🚀 Начинаем инициализацию справочника услуг...")
            
            # Проверяем существование таблиц
            with engine.connect() as conn:
                # Проверяем таблицу service_categories
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='service_categories'"))
                if not result.fetchone():
                    logger.error("❌ Таблица service_categories не найдена. Запустите миграции.")
                    return False
                
                # Проверяем таблицу services
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='services'"))
                if not result.fetchone():
                    logger.error("❌ Таблица services не найдена. Запустите миграции.")
                    return False
            
            # Создаем категории услуг
            logger.info("📂 Создаем категории услуг...")
            categories_data = seed_service_categories()
            categories_created = 0
            
            for cat_data in categories_data:
                # Проверяем существование категории
                existing = db.query(ServiceCategory).filter(ServiceCategory.code == cat_data['code']).first()
                if not existing:
                    category = ServiceCategory(**cat_data)
                    db.add(category)
                    categories_created += 1
                    logger.info(f"  ✅ Создана категория: {cat_data['name_ru']} ({cat_data['code']})")
                else:
                    logger.info(f"  ⏭️ Категория уже существует: {cat_data['name_ru']} ({cat_data['code']})")
            
            db.commit()
            logger.info(f"📂 Создано категорий: {categories_created}")
            
            # Создаем услуги
            logger.info("🛠️ Создаем базовые услуги...")
            services_data = seed_services()
            services_created = 0
            
            for service_data in services_data:
                # Проверяем существование услуги
                existing = db.query(Service).filter(Service.code == service_data['code']).first()
                if not existing:
                    service = Service(**service_data)
                    db.add(service)
                    services_created += 1
                    logger.info(f"  ✅ Создана услуга: {service_data['name']} ({service_data['code']})")
                else:
                    logger.info(f"  ⏭️ Услуга уже существует: {service_data['name']} ({service_data['code']})")
            
            db.commit()
            logger.info(f"🛠️ Создано услуг: {services_created}")
            
            # Статистика
            total_categories = db.query(ServiceCategory).count()
            total_services = db.query(Service).count()
            
            logger.info("📊 Итоговая статистика:")
            logger.info(f"  📂 Всего категорий в БД: {total_categories}")
            logger.info(f"  🛠️ Всего услуг в БД: {total_services}")
            logger.info("✅ Инициализация справочника услуг завершена успешно!")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации справочника услуг: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
