#!/usr/bin/env python3
"""
🤖 Скрипт настройки ИИ-агента для соблюдения правил проекта
"""

import os
import sys
import json
from pathlib import Path

def setup_cursor_rules():
    """Создать .cursorrules файл с правилами для ИИ-агентов"""
    rules_content = """# 🤖 ПРАВИЛА ДЛЯ ИИ-АГЕНТОВ В CURSOR

## 🚨 КРИТИЧЕСКИ ВАЖНО - ЧИТАТЬ ПЕРЕД ЛЮБОЙ РАБОТОЙ!

### 📖 ОБЯЗАТЕЛЬНАЯ ДОКУМЕНТАЦИЯ:
- `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md` - ПОЛНОЕ руководство по системе
- `docs/AUTHENTICATION_LAWS_FOR_AI.md` - ЗАКОНЫ для ИИ-агентов (ОБЯЗАТЕЛЬНО!)
- `docs/ROLE_SYSTEM_PROTECTION.md` - Правила защиты системы

### 🚨 АБСОЛЮТНЫЕ ЗАПРЕТЫ (НИКОГДА НЕ НАРУШАТЬ!):
1. **НЕ НАРУШАТЬ** блокирующий 2FA флоу - токены выдаются ТОЛЬКО после верификации
2. **НЕ ДУБЛИРОВАТЬ** модели ролей - использовать ТОЛЬКО `app/models/role_permission.py`
3. **НЕ СМЕШИВАТЬ** схемы хеширования паролей - только argon2 для новых
4. **НЕ ИСПОЛЬЗОВАТЬ** старую форму `Login.jsx` - только `LoginFormStyled.jsx`
5. **НЕ УДАЛЯТЬ** критических пользователей (admin, registrar, doctor, cardio, derma, dentist)

### ✅ ОБЯЗАТЕЛЬНЫЕ ДЕЙСТВИЯ:
1. **ЧИТАТЬ** `docs/AUTHENTICATION_LAWS_FOR_AI.md` перед работой с аутентификацией
2. **ЗАПУСКАТЬ** тесты: `python test_role_routing.py` после изменений ролей
3. **ИСПОЛЬЗОВАТЬ** только унифицированные модели из `role_permission.py`
4. **СЛЕДОВАТЬ** блокирующему 2FA флоу: login → pending_token → verify → access_token

**ПОМНИТЕ: Лучше спросить, чем сломать систему!** 🛡️
"""
    
    with open('.cursorrules', 'w', encoding='utf-8') as f:
        f.write(rules_content)
    print("✅ Создан .cursorrules файл")

def setup_git_hooks():
    """Настроить git хуки для проверки правил"""
    hooks_dir = Path('.git/hooks')
    if not hooks_dir.exists():
        print("⚠️ Директория .git/hooks не найдена. Инициализируйте git репозиторий.")
        return
    
    # Pre-commit hook
    pre_commit_content = """#!/bin/bash
echo "🔍 Проверка правил аутентификации..."
cd backend
python test_role_routing.py
if [ $? -ne 0 ]; then
    echo "❌ Тесты ролей не прошли! Коммит отклонен."
    echo "📖 Прочитайте: docs/AUTHENTICATION_LAWS_FOR_AI.md"
    exit 1
fi
echo "✅ Правила соблюдены. Коммит разрешен."
"""
    
    pre_commit_path = hooks_dir / 'pre-commit'
    with open(pre_commit_path, 'w', encoding='utf-8') as f:
        f.write(pre_commit_content)
    
    # Сделать исполняемым (Unix)
    if os.name != 'nt':
        os.chmod(pre_commit_path, 0o755)
    
    print("✅ Настроен pre-commit hook")

def setup_vscode_settings():
    """Настроить VS Code settings для проекта"""
    vscode_dir = Path('.vscode')
    vscode_dir.mkdir(exist_ok=True)
    
    settings = {
        "files.associations": {
            ".cursorrules": "markdown"
        },
        "files.watcherExclude": {
            "docs/AUTHENTICATION_LAWS_FOR_AI.md": False
        },
        "editor.rulers": [80, 120],
        "python.defaultInterpreterPath": "./backend/.venv/bin/python",
        "python.testing.pytestEnabled": True,
        "python.testing.pytestArgs": ["backend/tests"]
    }
    
    settings_path = vscode_dir / 'settings.json'
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    
    print("✅ Настроены VS Code settings")

def create_reminder_script():
    """Создать скрипт напоминания о правилах"""
    script_content = """#!/usr/bin/env python3
import os
import sys

def show_auth_reminder():
    print("\\n" + "="*60)
    print("🚨 НАПОМИНАНИЕ О ПРАВИЛАХ АУТЕНТИФИКАЦИИ")
    print("="*60)
    print("📖 Перед работой прочитать:")
    print("   - docs/AUTHENTICATION_LAWS_FOR_AI.md")
    print("   - docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md")
    print("\\n🧪 Перед коммитом запустить:")
    print("   cd backend && python test_role_routing.py")
    print("\\n🛡️ Критические правила:")
    print("   - НЕ нарушать блокирующий 2FA флоу")
    print("   - НЕ дублировать модели ролей")
    print("   - ИСПОЛЬЗОВАТЬ только LoginFormStyled.jsx")
    print("="*60 + "\\n")

if __name__ == "__main__":
    show_auth_reminder()
"""
    
    scripts_dir = Path('scripts')
    scripts_dir.mkdir(exist_ok=True)
    
    reminder_path = scripts_dir / 'remind_auth_rules.py'
    with open(reminder_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # Сделать исполняемым (Unix)
    if os.name != 'nt':
        os.chmod(reminder_path, 0o755)
    
    print("✅ Создан скрипт напоминания")

def setup_package_json_scripts():
    """Добавить скрипты в package.json"""
    package_json_path = Path('package.json')
    
    if package_json_path.exists():
        with open(package_json_path, 'r', encoding='utf-8') as f:
            package_data = json.load(f)
    else:
        package_data = {"name": "clinic-system", "version": "1.0.0"}
    
    if 'scripts' not in package_data:
        package_data['scripts'] = {}
    
    # Добавить новые скрипты
    new_scripts = {
        "check-auth": "cd backend && python test_role_routing.py",
        "check-system": "cd backend && python check_system_integrity.py",
        "remind-rules": "python scripts/remind_auth_rules.py",
        "pre-commit": "npm run check-auth && npm run check-system"
    }
    
    package_data['scripts'].update(new_scripts)
    
    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_data, f, indent=2, ensure_ascii=False)
    
    print("✅ Обновлен package.json со скриптами")

def main():
    """Основная функция настройки"""
    print("🤖 Настройка ИИ-агента для проекта...")
    print("="*50)
    
    try:
        setup_cursor_rules()
        setup_git_hooks()
        setup_vscode_settings()
        create_reminder_script()
        setup_package_json_scripts()
        
        print("\\n" + "="*50)
        print("✅ НАСТРОЙКА ЗАВЕРШЕНА УСПЕШНО!")
        print("="*50)
        print("\\n📋 Что было настроено:")
        print("   - .cursorrules - правила для Cursor IDE")
        print("   - Git hooks - автоматические проверки")
        print("   - VS Code settings - настройки редактора")
        print("   - Скрипт напоминания - scripts/remind_auth_rules.py")
        print("   - NPM скрипты - команды для проверки")
        print("\\n🎯 Следующие шаги:")
        print("   1. Перезапустить IDE")
        print("   2. Запустить: npm run remind-rules")
        print("   3. Прочитать: docs/AUTHENTICATION_LAWS_FOR_AI.md")
        print("\\n🛡️ СИСТЕМА ЗАЩИЩЕНА ОТ НАРУШЕНИЙ!")
        
    except Exception as e:
        print(f"❌ Ошибка настройки: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

