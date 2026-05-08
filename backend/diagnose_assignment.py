#!/usr/bin/env python3
"""
Диагностика проблемы в MorningAssignmentService
"""
import sys
import os
sys.path.append('/c/final/backend')

from datetime import date


def require_assignment_diagnostic_confirmation():
    if os.getenv("CONFIRM_DIAGNOSE_ASSIGNMENT") != "1":
        raise RuntimeError(
            "Refusing to run queue assignment diagnostic. "
            "It can create queue entries through MorningAssignmentService. "
            "Set CONFIRM_DIAGNOSE_ASSIGNMENT=1 only for an explicit local diagnostic run."
        )


def require_postgres_database_url():
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before running assignment diagnostics.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("diagnose_assignment.py requires PostgreSQL; SQLite is not allowed.")


def diagnose_morning_assignment():
    require_assignment_diagnostic_confirmation()
    require_postgres_database_url()

    from app.db.session import SessionLocal
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit, VisitService
    from app.services.morning_assignment import MorningAssignmentService

    print("🔍 Диагностика MorningAssignmentService")
    
    db = SessionLocal()
    
    try:
        # Создаем тестовый визит (последний созданный)
        latest_visit = db.query(Visit).filter(
            Visit.visit_date == date.today(),
            Visit.status == "confirmed"
        ).order_by(Visit.id.desc()).first()
        
        if not latest_visit:
            print("❌ Нет подтвержденных визитов на сегодня для тестирования")
            return
            
        print(f"📋 Тестируем визит ID {latest_visit.id}")
        print(f"   Patient ID: {latest_visit.patient_id}")
        print(f"   Department: {latest_visit.department}")
        print(f"   Doctor ID: {latest_visit.doctor_id}")
        print(f"   Status: {latest_visit.status}")
        
        # Проверяем услуги визита
        visit_services = db.query(VisitService).filter(VisitService.visit_id == latest_visit.id).all()
        print(f"📋 Услуги визита ({len(visit_services)}):")
        
        for vs in visit_services:
            service = db.query(Service).filter(Service.id == vs.service_id).first()
            if service:
                print(f"   - Service ID: {service.id}, Code: {service.code}, Name: {service.name}")
                print(f"     Queue tag: {service.queue_tag}")
            else:
                print(f"   - ❌ Service ID {vs.service_id} НЕ НАЙДЕНА!")
        
        # Тестируем _get_visit_queue_tags
        with MorningAssignmentService() as service:
            service.db = db
            
            print("\n🔍 Тестируем _get_visit_queue_tags:")
            try:
                queue_tags = service._get_visit_queue_tags(latest_visit)
                print(f"✅ Queue tags: {queue_tags}")
            except Exception as e:
                print(f"❌ Ошибка в _get_visit_queue_tags: {e}")
                import traceback
                traceback.print_exc()
                return
            
            if not queue_tags:
                print("⚠️ Нет queue_tags для услуг визита")
                return
            
            # Тестируем _assign_single_queue для каждого queue_tag
            print(f"\n🔍 Тестируем _assign_single_queue для каждого queue_tag:")
            for queue_tag in queue_tags:
                print(f"\n--- Тестируем queue_tag: {queue_tag} ---")
                try:
                    assignment = service._assign_single_queue(latest_visit, queue_tag, date.today())
                    if assignment:
                        print(f"✅ Присвоение успешно: {assignment}")
                    else:
                        print(f"⚠️ Присвоение не удалось (вернул None)")
                except Exception as e:
                    print(f"❌ Ошибка в _assign_single_queue для {queue_tag}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Тестируем полный _assign_queues_for_visit
            print(f"\n🔍 Тестируем полный _assign_queues_for_visit:")
            try:
                assignments = service._assign_queues_for_visit(latest_visit, date.today())
                print(f"✅ Результат: {assignments}")
            except Exception as e:
                print(f"❌ Ошибка в _assign_queues_for_visit: {e}")
                import traceback
                traceback.print_exc()
        
        # Проверяем ресурс-врачей
        print(f"\n🔍 Проверяем ресурс-врачей:")
        ecg_resource = db.query(User).filter(
            User.username == "ecg_resource",
            User.is_active == True
        ).first()
        print(f"ЭКГ ресурс: {'✅ найден' if ecg_resource else '❌ не найден'}")
        
        lab_resource = db.query(User).filter(
            User.username == "lab_resource", 
            User.is_active == True
        ).first()
        print(f"Лаб ресурс: {'✅ найден' if lab_resource else '❌ не найден'}")
        
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_morning_assignment()
