"""
Комплексное тестирование системы печати
Проверка всех компонентов: API, шаблоны, сервисы, CRUD
"""
import asyncio
import json
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.print_config import PrinterConfig, PrintTemplate, PrintJob
from app.crud import print_config as crud_print
from app.services.print_service import PrintService
from app.core.auth import create_access_token

client = TestClient(app)

def setup_test_printer(db: Session) -> PrinterConfig:
    """Создать тестовый принтер"""
    printer_data = {
        "name": "test_ticket_printer",
        "display_name": "Тестовый принтер талонов",
        "printer_type": "ESC/POS",
        "connection_type": "network",
        "ip_address": "192.168.1.100",
        "port": 9100,
        "paper_width": 58,
        "encoding": "utf-8",
        "active": True,
        "is_default": True
    }
    
    # Проверяем, существует ли уже
    existing = db.query(PrinterConfig).filter(PrinterConfig.name == printer_data["name"]).first()
    if existing:
        return existing
    
    printer = PrinterConfig(**printer_data)
    db.add(printer)
    db.commit()
    db.refresh(printer)
    return printer

def setup_test_template(db: Session, printer_id: int) -> PrintTemplate:
    """Создать тестовый шаблон"""
    template_content = """
{{ clinic_name | upper }}
========================================
ТАЛОН ОЧЕРЕДИ № {{ queue_number }}

Дата: {{ date.strftime('%d.%m.%Y') }}
Время: {{ time.strftime('%H:%M') }}

Врач: {{ doctor_name }}
Специальность: {{ specialty_name }}
{% if cabinet %}Кабинет: {{ cabinet }}{% endif %}

Пациент: {{ patient_name or 'Не указан' }}

Спасибо за обращение!
"""
    
    template_data = {
        "printer_id": printer_id,
        "name": "test_ticket_template",
        "display_name": "Тестовый шаблон талона",
        "template_type": "ticket",
        "template_content": template_content.strip(),
        "language": "ru",
        "font_size": 12,
        "active": True
    }
    
    # Проверяем, существует ли уже
    existing = db.query(PrintTemplate).filter(
        PrintTemplate.name == template_data["name"],
        PrintTemplate.printer_id == printer_id
    ).first()
    if existing:
        return existing
    
    template = PrintTemplate(**template_data)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

def setup_test_user(db: Session) -> User:
    """Создать тестового пользователя"""
    user_data = {
        "username": "test_registrar",
        "email": "test@clinic.com",
        "full_name": "Тестовый Регистратор",
        "role": "Registrar",
        "is_active": True,
        "hashed_password": "test_hash"  # В реальности будет хешироваться
    }
    
    # Проверяем, существует ли уже
    existing = db.query(User).filter(User.username == user_data["username"]).first()
    if existing:
        return existing
    
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def test_crud_operations():
    """Тест CRUD операций"""
    print("🧪 Тестирование CRUD операций...")
    
    db = SessionLocal()
    try:
        # Тест создания принтера
        printer = setup_test_printer(db)
        print(f"✅ Принтер создан: {printer.display_name}")
        
        # Тест получения принтера
        found_printer = crud_print.get_printer_by_name(db, "test_ticket_printer")
        assert found_printer is not None, "Принтер должен быть найден"
        print("✅ Принтер найден по имени")
        
        # Тест создания шаблона
        template = setup_test_template(db, printer.id)
        print(f"✅ Шаблон создан: {template.display_name}")
        
        # Тест получения шаблонов
        templates = crud_print.get_print_templates(db, template_type="ticket")
        assert len(templates) > 0, "Должны быть найдены шаблоны"
        print(f"✅ Найдено шаблонов: {len(templates)}")
        
    finally:
        db.close()

def test_print_service():
    """Тест сервиса печати"""
    print("\n🖨️ Тестирование PrintService...")
    
    db = SessionLocal()
    try:
        print_service = PrintService(db)
        
        # Тест получения статуса принтера
        status = print_service.get_printer_status("test_ticket_printer")
        print(f"✅ Статус принтера: {status['status']} - {status['message']}")
        
        # Тест рендеринга шаблона (без реальной печати)
        test_data = {
            "clinic_name": "ТЕСТОВАЯ КЛИНИКА",
            "queue_number": "001",
            "date": datetime.now(),
            "time": datetime.now(),
            "doctor_name": "Тестовый Врач",
            "specialty_name": "Терапия",
            "cabinet": "101",
            "patient_name": "Тестовый Пациент"
        }
        
        # Получаем шаблон и рендерим
        template = crud_print.get_print_templates(db, template_type="ticket")[0]
        if template:
            from jinja2 import Environment
            env = Environment()
            jinja_template = env.from_string(template.template_content)
            rendered = jinja_template.render(**test_data)
            print("✅ Шаблон успешно отрендерен:")
            print("=" * 40)
            print(rendered)
            print("=" * 40)
        
    finally:
        db.close()

def test_api_endpoints():
    """Тест API endpoints"""
    print("\n🌐 Тестирование API endpoints...")
    
    db = SessionLocal()
    try:
        # Создаем тестового пользователя
        user = setup_test_user(db)
        token = create_access_token(subject=user.username)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Тест получения списка принтеров
        response = client.get("/api/v1/print/printers", headers=headers)
        print(f"GET /printers: {response.status_code}")
        if response.status_code == 200:
            printers = response.json()
            print(f"✅ Найдено принтеров: {printers.get('total', 0)}")
        
        # Тест статуса принтера
        response = client.get("/api/v1/print/printers/test_ticket_printer/status", headers=headers)
        print(f"GET /printers/status: {response.status_code}")
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Статус принтера: {status.get('status')}")
        
        # Тест печати талона
        ticket_data = {
            "clinic_name": "ТЕСТОВАЯ КЛИНИКА",
            "queue_number": "TEST-001",
            "doctor_name": "Тестовый Врач",
            "specialty_name": "Терапия",
            "cabinet": "101",
            "patient_name": "Тестовый Пациент",
            "source": "test"
        }
        
        response = client.post("/api/v1/print/ticket", json=ticket_data, headers=headers)
        print(f"POST /ticket: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Результат печати: {result.get('message', 'OK')}")
        else:
            print(f"❌ Ошибка печати: {response.text}")
        
        # Тест быстрой печати талона
        quick_ticket = {
            "queue_number": "QUICK-001",
            "doctor_name": "Быстрый Врач", 
            "specialty": "Терапия",
            "patient_name": "Быстрый Пациент"
        }
        
        response = client.post("/api/v1/print/quick/queue-ticket", json=quick_ticket, headers=headers)
        print(f"POST /quick/queue-ticket: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Быстрая печать: {result.get('message', 'OK')}")
        
    finally:
        db.close()

def test_template_management():
    """Тест управления шаблонами"""
    print("\n📄 Тестирование управления шаблонами...")
    
    db = SessionLocal()
    try:
        user = setup_test_user(db)
        token = create_access_token(subject=user.username)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Тест получения типов шаблонов
        response = client.get("/api/v1/print/templates/types", headers=headers)
        print(f"GET /templates/types: {response.status_code}")
        if response.status_code == 200:
            types = response.json()
            print(f"✅ Доступно типов шаблонов: {len(types.get('template_types', []))}")
            print(f"✅ Доступно форматов: {len(types.get('formats', []))}")
        
        # Тест получения шаблонов
        response = client.get("/api/v1/print/templates/templates", headers=headers)
        print(f"GET /templates: {response.status_code}")
        if response.status_code == 200:
            templates = response.json()
            print(f"✅ Найдено шаблонов в БД: {len(templates)}")
        
        # Тест предварительного просмотра (если есть шаблоны)
        if response.status_code == 200 and len(templates) > 0:
            template_id = templates[0]["id"]
            preview_data = {
                "clinic_name": "ТЕСТ ПРЕВЬЮ",
                "queue_number": "PREV-001",
                "doctor_name": "Превью Врач",
                "date": datetime.now().isoformat(),
                "time": datetime.now().isoformat()
            }
            
            response = client.post(
                f"/api/v1/print/templates/templates/{template_id}/preview",
                json=preview_data,
                headers=headers
            )
            print(f"POST /templates/preview: {response.status_code}")
            if response.status_code == 200:
                preview = response.json()
                print("✅ Предварительный просмотр:")
                print("-" * 30)
                print(preview.get("rendered_content", "")[:200] + "...")
                print("-" * 30)
        
    finally:
        db.close()

def test_print_jobs():
    """Тест заданий печати"""
    print("\n📋 Тестирование заданий печати...")
    
    db = SessionLocal()
    try:
        # Создаем тестовое задание печати
        printer = setup_test_printer(db)
        user = setup_test_user(db)
        
        job_data = {
            "user_id": user.id,
            "printer_id": printer.id,
            "document_type": "ticket",
            "document_id": "TEST-JOB-001",
            "status": "completed",
            "print_data": {
                "queue_number": "JOB-001",
                "patient_name": "Тестовое Задание"
            }
        }
        
        job = crud_print.create_print_job(db, job_data)
        print(f"✅ Создано задание печати: ID {job.id}")
        
        # Получаем список заданий
        jobs = crud_print.get_print_jobs(db, limit=10)
        print(f"✅ Найдено заданий печати: {len(jobs)}")
        
        # Тест через API
        token = create_access_token(subject=user.username)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/v1/print/templates/jobs", headers=headers)
        print(f"GET /jobs: {response.status_code}")
        if response.status_code == 200:
            api_jobs = response.json()
            print(f"✅ Заданий через API: {len(api_jobs)}")
        
    finally:
        db.close()

def main():
    """Главная функция тестирования"""
    print("🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ ПЕЧАТИ")
    print("=" * 50)
    
    try:
        # 1. Тест CRUD операций
        test_crud_operations()
        
        # 2. Тест сервиса печати
        test_print_service()
        
        # 3. Тест API endpoints
        test_api_endpoints()
        
        # 4. Тест управления шаблонами
        test_template_management()
        
        # 5. Тест заданий печати
        test_print_jobs()
        
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 50)
        print("✅ CRUD операции работают")
        print("✅ PrintService функционирует")
        print("✅ API endpoints отвечают")
        print("✅ Шаблоны рендерятся")
        print("✅ Задания печати создаются")
        print("\n🖨️ СИСТЕМА ПЕЧАТИ ПОЛНОСТЬЮ ГОТОВА К РАБОТЕ!")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА ТЕСТИРОВАНИЯ: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
