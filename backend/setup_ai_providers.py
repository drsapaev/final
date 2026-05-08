"""
Настройка стандартных AI провайдеров и промпт-шаблонов
Основа: passport.md стр. 3325-3888
"""
import os


def require_ai_setup_confirmation():
    if os.getenv("CONFIRM_SETUP_AI_PROVIDERS") != "1":
        raise RuntimeError(
            "Refusing to setup AI providers. "
            "Set CONFIRM_SETUP_AI_PROVIDERS=1 only for an explicit AI catalog setup run."
        )


def require_postgres_database_url():
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before setting up AI providers.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("setup_ai_providers.py requires PostgreSQL; SQLite is not allowed.")


def create_ai_providers():
    require_postgres_database_url()

    from app.crud import ai_config as crud_ai
    from app.db.session import SessionLocal
    from app.models.ai_config import AIProvider

    """Создать стандартных AI провайдеров"""
    print('🤖 Создание AI провайдеров...')

    db = SessionLocal()
    try:
        # 1. OpenAI GPT-4
        openai_provider = {
            "name": "openai",
            "display_name": "OpenAI GPT-4",
            "api_url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 1500,
            "active": False,  # Будет активирован при добавлении API ключа
            "is_default": False,
            "capabilities": ["text", "vision", "ocr"],
            "limits": {
                "requests_per_minute": 60,
                "tokens_per_day": 50000
            }
        }

        existing = db.query(AIProvider).filter(AIProvider.name == "openai").first()
        if not existing:
            provider = AIProvider(**openai_provider)
            db.add(provider)
            print("✅ Создан провайдер OpenAI")
        else:
            print("✅ Провайдер OpenAI уже существует")

        # 2. Anthropic Claude
        anthropic_provider = {
            "name": "anthropic",
            "display_name": "Anthropic Claude",
            "api_url": "https://api.anthropic.com/v1/messages",
            "model": "claude-3-sonnet-20240229",
            "temperature": 0.3,
            "max_tokens": 2000,
            "active": False,
            "is_default": False,
            "capabilities": ["text", "vision"],
            "limits": {
                "requests_per_minute": 50,
                "tokens_per_day": 40000
            }
        }

        existing = db.query(AIProvider).filter(AIProvider.name == "anthropic").first()
        if not existing:
            provider = AIProvider(**anthropic_provider)
            db.add(provider)
            print("✅ Создан провайдер Anthropic")
        else:
            print("✅ Провайдер Anthropic уже существует")

        # 3. Yandex GPT
        yandex_provider = {
            "name": "yandex_gpt",
            "display_name": "Yandex GPT",
            "api_url": "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            "model": "yandexgpt-lite",
            "temperature": 0.2,
            "max_tokens": 1000,
            "active": False,
            "is_default": True,  # По умолчанию для российского рынка
            "capabilities": ["text"],
            "limits": {
                "requests_per_minute": 30,
                "tokens_per_day": 20000
            }
        }

        existing = db.query(AIProvider).filter(AIProvider.name == "yandex_gpt").first()
        if not existing:
            provider = AIProvider(**yandex_provider)
            db.add(provider)
            print("✅ Создан провайдер Yandex GPT (по умолчанию)")
        else:
            print("✅ Провайдер Yandex GPT уже существует")

        db.commit()
        
        # Получаем все провайдеры
        providers = crud_ai.get_ai_providers(db)
        print(f"✅ Всего AI провайдеров: {len(providers)}")
        
        for provider in providers:
            status = "🟢 Активен" if provider.active else "🔴 Неактивен"
            default = " (По умолчанию)" if provider.is_default else ""
            print(f"   • {provider.display_name}: {status}{default}")

    finally:
        db.close()

def create_prompt_templates():
    require_postgres_database_url()

    from app.crud import ai_config as crud_ai
    from app.db.session import SessionLocal
    from app.models.ai_config import AIPromptTemplate, AIProvider

    """Создать базовые промпт-шаблоны"""
    print('\n📝 Создание промпт-шаблонов...')

    db = SessionLocal()
    try:
        # Получаем провайдер по умолчанию
        default_provider = db.query(AIProvider).filter(AIProvider.is_default == True).first()
        
        if not default_provider:
            print("❌ Провайдер по умолчанию не найден")
            return

        # 1. Шаблон анализа жалоб для кардиологии
        complaints_template = {
            "provider_id": default_provider.id,
            "task_type": "complaints_analysis",
            "specialty": "cardiology",
            "language": "ru",
            "version": "1.0",
            "system_prompt": """Ты опытный врач-кардиолог. Проанализируй жалобы пациента и предложи план обследования.
Отвечай структурированно на русском языке.""",
            "context_template": """Специальность: {{ specialty }}
Язык общения: {{ language }}""",
            "task_template": """Жалобы пациента: {{ complaints }}

Проанализируй жалобы и предложи:
1. Возможные диагнозы (3-5 наиболее вероятных)
2. План обследования (анализы, инструментальные исследования)
3. Неотложные меры (если требуются)
4. Рекомендации по образу жизни""",
            "examples": [
                "Пример: Боли в области сердца → ЭКГ, ЭхоКГ, анализы крови",
                "Пример: Одышка при нагрузке → Рентген грудной клетки, ЭхоКГ"
            ],
            "temperature": 0.3,
            "max_tokens": 1000,
            "response_schema": {
                "type": "object",
                "properties": {
                    "possible_diagnoses": {"type": "array"},
                    "examination_plan": {"type": "array"},
                    "urgent_actions": {"type": "array"},
                    "recommendations": {"type": "array"}
                }
            },
            "active": True
        }

        existing = db.query(AIPromptTemplate).filter(
            AIPromptTemplate.task_type == "complaints_analysis",
            AIPromptTemplate.specialty == "cardiology"
        ).first()
        
        if not existing:
            template = AIPromptTemplate(**complaints_template)
            db.add(template)
            print("✅ Создан шаблон анализа жалоб (кардиология)")
        else:
            print("✅ Шаблон анализа жалоб уже существует")

        # 2. Шаблон подбора МКБ-10
        icd10_template = {
            "provider_id": default_provider.id,
            "task_type": "icd10_lookup",
            "specialty": "general",
            "language": "ru",
            "version": "1.0",
            "system_prompt": """Ты эксперт по Международной классификации болезней (МКБ-10).
Найди наиболее подходящие коды МКБ-10 для указанного диагноза.""",
            "context_template": """Специальность: {{ specialty }}
Требуется точный подбор кода МКБ-10""",
            "task_template": """Диагноз: {{ diagnosis }}

Найди 3-5 наиболее подходящих кодов МКБ-10:
- Основной код (наиболее точный)
- Альтернативные коды
- Укажи полное описание каждого кода""",
            "examples": [
                "Пример: Стенокардия → I20.9 Стенокардия неуточненная",
                "Пример: Гипертония → I10 Эссенциальная гипертензия"
            ],
            "temperature": 0.1,
            "max_tokens": 800,
            "response_schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "description": {"type": "string"},
                        "confidence": {"type": "number"}
                    }
                }
            },
            "active": True
        }

        existing = db.query(AIPromptTemplate).filter(
            AIPromptTemplate.task_type == "icd10_lookup"
        ).first()
        
        if not existing:
            template = AIPromptTemplate(**icd10_template)
            db.add(template)
            print("✅ Создан шаблон подбора МКБ-10")
        else:
            print("✅ Шаблон МКБ-10 уже существует")

        # 3. Шаблон анализа лабораторных результатов
        lab_template = {
            "provider_id": default_provider.id,
            "task_type": "lab_interpretation",
            "specialty": "general",
            "language": "ru",
            "version": "1.0",
            "system_prompt": """Ты врач-лаборант с большим опытом интерпретации анализов.
Проанализируй результаты и дай медицинское заключение.""",
            "context_template": """Специальность направившего врача: {{ specialty }}
Возраст пациента: {{ patient_age }}
Пол: {{ patient_gender }}""",
            "task_template": """Результаты анализов:
{{ lab_results }}

Проанализируй результаты и укажи:
1. Отклонения от нормы
2. Клиническое значение
3. Рекомендации для лечащего врача""",
            "examples": [
                "Пример: Холестерин 6.8 → Гиперхолестеринемия, риск ИБС",
                "Пример: Глюкоза 12.5 → Гипергликемия, подозрение на диабет"
            ],
            "temperature": 0.2,
            "max_tokens": 1200,
            "active": True
        }

        existing = db.query(AIPromptTemplate).filter(
            AIPromptTemplate.task_type == "lab_interpretation"
        ).first()
        
        if not existing:
            template = AIPromptTemplate(**lab_template)
            db.add(template)
            print("✅ Создан шаблон интерпретации анализов")
        else:
            print("✅ Шаблон анализов уже существует")

        db.commit()
        
        # Получаем все шаблоны
        templates = crud_ai.get_prompt_templates(db)
        print(f"✅ Всего промпт-шаблонов: {len(templates)}")
        
        for template in templates:
            print(f"   • {template.task_type} ({template.specialty or 'general'})")

    finally:
        db.close()

def main():
    require_ai_setup_confirmation()
    require_postgres_database_url()

    """Основная функция настройки"""
    print("🚀 НАСТРОЙКА AI СИСТЕМЫ")
    print("=" * 50)
    
    try:
        # 1. Создаем провайдеров
        create_ai_providers()
        
        # 2. Создаем шаблоны
        create_prompt_templates()
        
        print("\n" + "=" * 50)
        print("🎉 AI СИСТЕМА НАСТРОЕНА!")
        print("\n✅ Созданные компоненты:")
        print("   • 3 AI провайдера (OpenAI, Anthropic, Yandex)")
        print("   • 3 промпт-шаблона (жалобы, МКБ-10, анализы)")
        print("   • Базовая конфигурация готова")
        
        print("\n🔧 Следующие шаги:")
        print("   1. Добавить API ключи в админ панели")
        print("   2. Активировать нужного провайдера")
        print("   3. Протестировать AI анализ")
        
    except Exception as e:
        print(f"\n❌ Ошибка настройки AI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
