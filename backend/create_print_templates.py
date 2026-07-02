"""
Создание шаблонов печати в БД
"""
import os

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.print_config import PrinterConfig, PrintTemplate
from app.crud import print_config as crud_print

def _require_confirmation():
    if os.getenv("CONFIRM_CREATE_PRINT_TEMPLATES") != "1":
        raise RuntimeError(
            "Refusing to create print templates. "
            "Set CONFIRM_CREATE_PRINT_TEMPLATES=1 only for an explicit print setup run."
        )


def _require_postgres_database_url():
    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before creating print templates.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("create_print_templates.py requires PostgreSQL; SQLite is not allowed.")


def create_templates():
    """Создать стандартные шаблоны"""
    _require_confirmation()
    _require_postgres_database_url()

    print('📄 Создание шаблонов печати в БД...')

    db = SessionLocal()
    try:
        # Получаем принтер по умолчанию
        printer = db.query(PrinterConfig).filter(PrinterConfig.is_default == True).first()
        
        if not printer:
            print('❌ Принтер по умолчанию не найден')
            return
        
        print(f'✅ Найден принтер: {printer.display_name}')
        
        # Шаблон талона для ESC/POS
        ticket_template = """========================================
      {{ clinic_name | upper }}
========================================
ТАЛОН ОЧЕРЕДИ № {{ queue_number }}

Дата: {{ date.strftime('%d.%m.%Y') }}
Время: {{ time.strftime('%H:%M') }}

Врач: {{ doctor_name }}
Специальность: {{ specialty_name }}
{% if cabinet %}Кабинет: {{ cabinet }}{% endif %}

Пациент: {{ patient_name or 'Не указан' }}

{% if source == 'online' %}
🌐 Онлайн запись
{% else %}
🏥 Регистратура  
{% endif %}

Спасибо за обращение!
{% if clinic_phone %}{{ clinic_phone }}{% endif %}
========================================"""
        
        # Проверяем есть ли уже шаблон
        existing = db.query(PrintTemplate).filter(
            PrintTemplate.name == 'default_ticket',
            PrintTemplate.printer_id == printer.id
        ).first()
        
        if not existing:
            template = PrintTemplate(
                printer_id=printer.id,
                name='default_ticket',
                display_name='Стандартный талон очереди',
                template_type='ticket',
                template_content=ticket_template.strip(),
                language='ru',
                font_size=12,
                char_per_line=40,
                active=True
            )
            db.add(template)
            db.commit()
            print('✅ Создан шаблон талона')
        else:
            print('✅ Шаблон талона уже существует')
        
        # Получаем все шаблоны
        templates = crud_print.get_print_templates(db)
        print(f'✅ Всего шаблонов в БД: {len(templates)}')
        
        for template in templates:
            print(f'   • {template.display_name} ({template.template_type})')
        
        print('🎯 Шаблоны готовы!')
        
    finally:
        db.close()

if __name__ == "__main__":
    create_templates()
