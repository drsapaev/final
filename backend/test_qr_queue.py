#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки QR-записей
"""
import json
import sys
from datetime import date, datetime
from app.db.session import SessionLocal
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service

# Фикс для Windows консоли
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_qr_entries():
    db = SessionLocal()
    try:
        print("="*80)
        print("PROVERKA QR-ZAPISEY")
        print("="*80)

        # 1. Проверяем последние 3 записи
        print("\n[1] POSLEDNIE 3 ZAPISI V OCHEREDI")
        print("-"*80)
        entries = db.query(OnlineQueueEntry).order_by(
            OnlineQueueEntry.id.desc()
        ).limit(3).all()

        for entry in entries:
            print(f"\nID: {entry.id}")
            print(f"  Пациент: {entry.patient_name}")
            print(f"  Телефон: {entry.phone}")
            print(f"  Источник: {entry.source}")
            print(f"  Статус: {entry.status}")
            print(f"  Время: {entry.queue_time}")

            # Парсим услуги
            if entry.services:
                try:
                    services = json.loads(entry.services) if isinstance(entry.services, str) else entry.services
                    print(f"  Услуги ({len(services)}):")
                    for svc in services:
                        print(f"    - {svc.get('name', 'N/A')} ({svc.get('code', 'N/A')}): {svc.get('price', 0)}")
                except Exception as e:
                    print(f"  Uslugi (error): {str(e)}")
            else:
                print(f"  Uslugi: [!] PUSTO")

            print(f"  Summa: {entry.total_amount}")

        # 2. Проверяем доступные queue_tags
        print("\n\n[2] DOSTUPNYE QUEUE_TAGS")
        print("-"*80)
        tags = db.query(DailyQueue.queue_tag).distinct().filter(
            DailyQueue.queue_tag.isnot(None)
        ).all()
        queue_tags = [t[0] for t in tags]
        print(f"Naydeno {len(queue_tags)} tegov: {queue_tags}")

        # 3. Проверяем маппинг услуг
        print("\n\n[3] MAPPING USLUG (first service in each category)")
        print("-"*80)

        service_codes = {
            'D01': 'Dermatologiya',
            'K01': 'Kardiologiya',
            'K10': 'EKG',  # ✅ ISPRAVLENO
            'S01': 'Stomatologiya',
            'L01': 'Laboratoriya',
            'P03': 'Procedury (UFO terapiya)',  # ✅ ISPRAVLENO
            'C03': 'Kosmetologiya (mezoterapiya)',
            'O10': 'UZI',
        }

        for code, category in service_codes.items():
            service = db.query(Service).filter(Service.code == code).first()
            if service:
                print(f"  [OK] {code} ({category}): {service.name} - {service.price}")
            else:
                print(f"  [X] {code} ({category}): NE NAYDENA")

        # 4. Проверяем записи БЕЗ услуг (потенциальные проблемы)
        print("\n\n[4] ZAPISI BEZ USLUG (potencialnye problemy)")
        print("-"*80)
        entries_without_services = db.query(OnlineQueueEntry).filter(
            (OnlineQueueEntry.services.is_(None)) | (OnlineQueueEntry.services == '[]')
        ).order_by(OnlineQueueEntry.id.desc()).limit(5).all()

        if entries_without_services:
            print(f"[!] Naydeno {len(entries_without_services)} zapisey bez uslug:")
            for entry in entries_without_services:
                # Получаем queue_tag для этой записи
                queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
                queue_tag = queue.queue_tag if queue else "N/A"
                print(f"  ID:{entry.id}, pacient:{entry.patient_name}, queue_tag:{queue_tag}")
        else:
            print("[OK] Vse zapisi imeyut uslugi!")

        print("\n" + "="*80)
        print("PROVERKA ZAVERSHENA")
        print("="*80)

    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    test_qr_entries()
