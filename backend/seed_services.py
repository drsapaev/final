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
            'code': 'physiotherapy',
            'name_ru': 'Физиотерапия',
            'name_uz': 'Fizioterapiya',
            'name_en': 'Physiotherapy',
            'specialty': 'physiotherapy',
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
            'active': True,
            'category_code': 'K',
            'service_code': 'K01'
        },
        {
            'code': 'echo.cardiography',
            'name': 'ЭхоКГ',
            'department': 'cardiology',
            'unit': 'исследование',
            'price': 80000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True,
            'category_code': 'K',
            'service_code': 'K11'
        },
        {
            'code': 'ecg',
            'name': 'ЭКГ',
            'department': 'cardiology',
            'unit': 'исследование',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 15,
            'active': True,
            'category_code': 'K',
            'service_code': 'K10'
        },
        
        # Дерматология
        {
            'code': 'consultation.dermatology',
            'name': 'Консультация дерматолога-косметолога',
            'department': 'dermatology',
            'unit': 'консультация',
            'price': 40000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True,
            'category_code': 'D',
            'service_code': 'D01'
        },
        {
            'code': 'derm.skin_diagnostics',
            'name': 'Дерматоскопия',
            'department': 'dermatology',
            'unit': 'исследование',
            'price': 30000.00,
            'currency': 'UZS',
            'duration_minutes': 20,
            'active': True,
            'category_code': 'D',
            'service_code': 'D02'
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
            'active': True,
            'category_code': 'S',
            'service_code': 'S01'
        },
        {
            'code': 'dentistry.xray',
            'name': 'Рентгенография зубов',
            'department': 'dentistry',
            'unit': 'исследование',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 15,
            'active': True,
            'category_code': 'S',
            'service_code': 'S10'
        },
        
        # Лаборатория - полный список согласно требованиям
        {
            'code': 'lab.cbc',
            'name': 'Общий анализ крови',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L01'
        },
        {
            'code': 'lab.coag',
            'name': 'Время свертываемости крови',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 20000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L03'
        },
        {
            'code': 'lab.urine',
            'name': 'Общий анализ мочи',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L25'
        },
        {
            'code': 'lab.glucose_express',
            'name': 'Глюкоза экспресс тест',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 8000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L35'
        },
        {
            'code': 'lab.hbsag',
            'name': 'HBsAg Экспресс тест',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 12000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L30'
        },
        {
            'code': 'lab.hcv',
            'name': 'HCV Экспресс тест',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 12000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L31'
        },
        {
            'code': 'lab.hiv',
            'name': 'HIV Экспресс тест',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 12000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L32'
        },
        {
            'code': 'lab.rw',
            'name': 'RW Экспресс тест',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 12000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L33'
        },
        {
            'code': 'lab.protein',
            'name': 'Общий белок',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 18000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L10'
        },
        {
            'code': 'lab.glucose',
            'name': 'Глюкоза',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 8000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L11'
        },
        {
            'code': 'lab.cholesterol',
            'name': 'Холестерин',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 12000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L12'
        },
        {
            'code': 'lab.urea',
            'name': 'Мочевина',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L13'
        },
        {
            'code': 'lab.creatinine',
            'name': 'Креатинин',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L14'
        },
        {
            'code': 'lab.alt',
            'name': 'АлАТ - аланинаминотрансфераза',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L15'
        },
        {
            'code': 'lab.ast',
            'name': 'АсАТ - аспартатаминотрансфераза',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L16'
        },
        {
            'code': 'lab.bilirubin',
            'name': 'Билирубин (общ, прям, непрям)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 20000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L17'
        },
        {
            'code': 'lab.alkaline',
            'name': 'Щелочная фосфатаза',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 18000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L18'
        },
        {
            'code': 'lab.amylase',
            'name': 'Альфа-амилаза',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 18000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L19'
        },
        {
            'code': 'lab.potassium',
            'name': 'Калий',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L20'
        },
        {
            'code': 'lab.calcium',
            'name': 'Кальций',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L21'
        },
        {
            'code': 'lab.sodium',
            'name': 'Натрий',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 10000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L22'
        },
        {
            'code': 'lab.vitamin_d',
            'name': 'Витамин Д',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L23'
        },
        {
            'code': 'lab.immunoglobulin',
            'name': 'Иммуноглобулин Е',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 22000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L65'
        },
        {
            'code': 'lab.spermogram',
            'name': 'Спермограмма',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 30000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L34'
        },
        {
            'code': 'lab.rheumatoid',
            'name': 'Ревматоидный фактор (RF)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 18000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L40'
        },
        {
            'code': 'lab.crp',
            'name': 'С-реактивный белок (CRP)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 18000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L41'
        },
        {
            'code': 'lab.aslo',
            'name': 'Антистрептолизин-О (ASlO)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 18000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L42'
        },
        {
            'code': 'lab.brucellosis',
            'name': 'Бруцеллез (Rose Bengal)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 20000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L43'
        },
        {
            'code': 'lab.tsh',
            'name': 'ТТГ (тиреотропный гормон)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 22000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L50'
        },
        {
            'code': 'lab.t4',
            'name': 'Т4 (тироксин)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 22000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L51'
        },
        {
            'code': 'lab.t3',
            'name': 'Т3 (трийодтиронин)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 22000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L52'
        },
        {
            'code': 'lab.at_tpo',
            'name': 'АТ-ТПО (аутоантитело к тиреопероксидазе)',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L53'
        },
        {
            'code': 'lab.testosterone',
            'name': 'Тестостерон',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 22000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L54'
        },
        {
            'code': 'lab.fungi',
            'name': 'Нити грибки',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L60'
        },
        {
            'code': 'lab.malassezia',
            'name': 'Malassezia furfur',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L61'
        },
        {
            'code': 'lab.demodex',
            'name': 'Демодекоз',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L62'
        },
        {
            'code': 'lab.smear',
            'name': 'Мазок на степень чистоты',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 12000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L63'
        },
        {
            'code': 'lab.stool',
            'name': 'Кал на я/г',
            'department': 'laboratory',
            'unit': 'анализ',
            'price': 15000.00,
            'currency': 'UZS',
            'duration_minutes': 5,
            'active': True,
            'category_code': 'L',
            'service_code': 'L64'
        },

        # Физиотерапия (дерматологическая)
        {
            'code': 'physio.darsonval',
            'name': 'Дарсонваль',
            'department': 'physiotherapy',
            'unit': 'процедура',
            'price': 30000.00,
            'currency': 'UZS',
            'duration_minutes': 20,
            'active': True,
            'category_code': 'P',
            'service_code': 'P01'
        },
        {
            'code': 'physio.ufo',
            'name': 'УФО терапия',
            'department': 'physiotherapy',
            'unit': 'процедура',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 15,
            'active': True,
            'category_code': 'P',
            'service_code': 'P02'
        },
        {
            'code': 'physio.diode_mask',
            'name': 'Диодная маска лица',
            'department': 'physiotherapy',
            'unit': 'процедура',
            'price': 40000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True,
            'category_code': 'P',
            'service_code': 'P03'
        },
        {
            'code': 'physio.bioptron',
            'name': 'Биоптрон - светотерапия',
            'department': 'physiotherapy',
            'unit': 'процедура',
            'price': 35000.00,
            'currency': 'UZS',
            'duration_minutes': 25,
            'active': True,
            'category_code': 'P',
            'service_code': 'P04'
        },
        {
            'code': 'physio.excimer_laser',
            'name': 'Эксимер лазер',
            'department': 'physiotherapy',
            'unit': 'процедура',
            'price': 50000.00,
            'currency': 'UZS',
            'duration_minutes': 20,
            'active': True,
            'category_code': 'P',
            'service_code': 'P05'
        },

        # Косметологические процедуры
        {
            'code': 'cosmetology.plasmolifting_face',
            'name': 'Плазмолифтинг лица',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 120000.00,
            'currency': 'UZS',
            'duration_minutes': 60,
            'active': True,
            'category_code': 'C',
            'service_code': 'C01'
        },
        {
            'code': 'cosmetology.plasmolifting_hair',
            'name': 'Плазмолифтинг волос',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 100000.00,
            'currency': 'UZS',
            'duration_minutes': 45,
            'active': True,
            'category_code': 'C',
            'service_code': 'C02'
        },
        {
            'code': 'cosmetology.mesotherapy_cosmetology',
            'name': 'Мезотерапия (косметологическая)',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 80000.00,
            'currency': 'UZS',
            'duration_minutes': 45,
            'active': True,
            'category_code': 'C',
            'service_code': 'C03'
        },
        {
            'code': 'cosmetology.face_cleaning',
            'name': 'Чистка лица',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 60000.00,
            'currency': 'UZS',
            'duration_minutes': 60,
            'active': True,
            'category_code': 'C',
            'service_code': 'C04'
        },
        {
            'code': 'cosmetology.blepharoplasty',
            'name': 'Безоперационная блефаропластика',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 150000.00,
            'currency': 'UZS',
            'duration_minutes': 45,
            'active': True,
            'category_code': 'C',
            'service_code': 'C05'
        },
        {
            'code': 'cosmetology.wen_removal',
            'name': 'Удаление жировик',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 30000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True,
            'category_code': 'C',
            'service_code': 'C06'
        },
        {
            'code': 'cosmetology.tattoo_removal',
            'name': 'Лазерное удаление татуаж и татуировок',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 80000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True,
            'category_code': 'C',
            'service_code': 'C07'
        },
        {
            'code': 'cosmetology.carbon_peeling',
            'name': 'Карбоновый пилинг',
            'department': 'cosmetology',
            'unit': 'процедура',
            'price': 70000.00,
            'currency': 'UZS',
            'duration_minutes': 45,
            'active': True,
            'category_code': 'C',
            'service_code': 'C08'
        },

        # Дерматологические процедуры
        {
            'code': 'derm_proc.cryodestruction_warts',
            'name': 'Криодеструкция бородавок',
            'department': 'dermatology',
            'unit': 'процедура',
            'price': 25000.00,
            'currency': 'UZS',
            'duration_minutes': 15,
            'active': True,
            'category_code': 'D_PROC',
            'service_code': 'D_PROC01'
        },
        {
            'code': 'derm_proc.cryodestruction_papillomas',
            'name': 'Криодеструкция папиллом',
            'department': 'dermatology',
            'unit': 'процедура',
            'price': 20000.00,
            'currency': 'UZS',
            'duration_minutes': 15,
            'active': True,
            'category_code': 'D_PROC',
            'service_code': 'D_PROC02'
        },
        {
            'code': 'derm_proc.mesotherapy_scars',
            'name': 'Мезотерапия келлоидных рубцов',
            'department': 'dermatology',
            'unit': 'процедура',
            'price': 50000.00,
            'currency': 'UZS',
            'duration_minutes': 30,
            'active': True,
            'category_code': 'D_PROC',
            'service_code': 'D_PROC03'
        },

        # Прочие процедуры
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
