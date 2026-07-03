# 🤖 НАСТРОЙКА ИИ-АГЕНТА ДЛЯ ПРОЕКТА

## 🎯 Как обеспечить соблюдение правил ИИ-агентом

### 1. **АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ПРАВИЛ**

#### В Cursor IDE:
```
Файл .cursorrules автоматически загружается при открытии проекта
```

#### В других IDE:
```
Добавить в системный промпт:
"Перед началом работы ОБЯЗАТЕЛЬНО прочитать docs/AUTHENTICATION_LAWS_FOR_AI.md"
```

### 2. **НАСТРОЙКА ПАМЯТИ АГЕНТА**

#### Добавить в системную память:
```
КРИТИЧЕСКИЕ ПРАВИЛА ПРОЕКТА:
- НЕ нарушать блокирующий 2FA флоу
- НЕ дублировать модели ролей  
- ИСПОЛЬЗОВАТЬ только LoginFormStyled.jsx
- ЧИТАТЬ docs/AUTHENTICATION_LAWS_FOR_AI.md перед работой
```

#### Команда для обновления памяти:
```
Система аутентификации модернизирована с блокирующим 2FA флоу и унифицированными моделями ролей. 
КРИТИЧЕСКИЕ ПРАВИЛА: НЕ нарушать блокирующий 2FA флоу, НЕ дублировать модели ролей, 
ИСПОЛЬЗОВАТЬ только LoginFormStyled.jsx. Полная документация в docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md
```

### 3. **АВТОМАТИЧЕСКИЕ ПРОВЕРКИ**

#### Pre-commit хуки:
```bash
# .git/hooks/pre-commit
#!/bin/bash
cd backend
python test_role_routing.py
if [ $? -ne 0 ]; then
    echo "❌ Тесты ролей не прошли! Коммит отклонен."
    exit 1
fi
```

#### GitHub Actions:
```yaml
# .github/workflows/auth-check.yml
name: Authentication System Check
on: [push, pull_request]
jobs:
  check-auth:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check Authentication Rules
        run: |
          cd backend
          python test_role_routing.py
          python check_system_integrity.py
```

### 4. **ИНТЕГРАЦИЯ В WORKFLOW**

#### Добавить в package.json:
```json
{
  "scripts": {
    "check-auth": "cd backend && python test_role_routing.py",
    "check-system": "cd backend && python check_system_integrity.py",
    "pre-commit": "npm run check-auth && npm run check-system"
  }
}
```

#### Добавить в README.md:
```markdown
## ⚠️ ВАЖНО ДЛЯ РАЗРАБОТЧИКОВ

Перед работой с системой аутентификации ОБЯЗАТЕЛЬНО прочитать:
- `docs/AUTHENTICATION_LAWS_FOR_AI.md` - Законы для ИИ-агентов
- `docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md` - Полное руководство
```

### 5. **НАСТРОЙКА CURSOR IDE**

#### В настройках Cursor:
```json
{
  "cursor.general.enableRules": true,
  "cursor.rules.autoLoad": true,
  "cursor.rules.enforceStrict": true
}
```

#### Добавить в workspace settings:
```json
{
  "files.watcherExclude": {
    "docs/AUTHENTICATION_LAWS_FOR_AI.md": false
  },
  "files.associations": {
    ".cursorrules": "markdown"
  }
}
```

### 6. **СОЗДАНИЕ АЛИАСОВ КОМАНД**

#### Для Windows (PowerShell):
```powershell
# В профиле PowerShell
function Check-Auth { cd C:\final\backend; python test_role_routing.py }
function Check-System { cd C:\final\backend; python check_system_integrity.py }
function Read-AuthLaws { Get-Content C:\final\docs\AUTHENTICATION_LAWS_FOR_AI.md }
```

#### Для Linux/Mac:
```bash
# В .bashrc или .zshrc
alias check-auth='cd /path/to/final/backend && python test_role_routing.py'
alias check-system='cd /path/to/final/backend && python check_system_integrity.py'
alias read-auth-laws='cat /path/to/final/docs/AUTHENTICATION_LAWS_FOR_AI.md'
```

### 7. **АВТОМАТИЧЕСКОЕ НАПОМИНАНИЕ**

#### Создать скрипт напоминания:
```python
# scripts/remind_auth_rules.py
import os
import sys

def remind_auth_rules():
    print("🚨 НАПОМИНАНИЕ: Перед работой с аутентификацией:")
    print("📖 Прочитать: docs/AUTHENTICATION_LAWS_FOR_AI.md")
    print("🧪 Запустить: python test_role_routing.py")
    print("🛡️ Соблюдать: Блокирующий 2FA флоу")
    
if __name__ == "__main__":
    remind_auth_rules()
```

#### Добавить в .bashrc:
```bash
# Показывать напоминание при входе в директорию проекта
if [[ $PWD == *"final"* ]]; then
    python scripts/remind_auth_rules.py
fi
```

### 8. **ИНТЕГРАЦИЯ С СИСТЕМОЙ КОНТРОЛЯ ВЕРСИЙ**

#### Добавить в .gitignore исключения:
```
# Важные файлы документации - НЕ игнорировать
!docs/AUTHENTICATION_LAWS_FOR_AI.md
!docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md
!.cursorrules
```

#### Создать git hook для проверки:
```bash
#!/bin/bash
# .git/hooks/pre-push
echo "🔍 Проверка соблюдения правил аутентификации..."
cd backend
python test_role_routing.py
if [ $? -ne 0 ]; then
    echo "❌ Правила аутентификации нарушены! Push отклонен."
    exit 1
fi
echo "✅ Правила соблюдены. Push разрешен."
```

### 9. **МОНИТОРИНГ И АЛЕРТЫ**

#### Создать скрипт мониторинга:
```python
# scripts/monitor_auth_integrity.py
import subprocess
import smtplib
from datetime import datetime

def check_auth_integrity():
    try:
        result = subprocess.run(['python', 'test_role_routing.py'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            send_alert(f"Нарушение правил аутентификации: {result.stderr}")
    except Exception as e:
        send_alert(f"Ошибка проверки: {e}")

def send_alert(message):
    # Отправить уведомление команде
    print(f"🚨 АЛЕРТ: {message}")
```

### 10. **ДОКУМЕНТАЦИЯ ДЛЯ КОМАНДЫ**

#### Создать ONBOARDING.md:
```markdown
# 🚀 ОНБОРДИНГ РАЗРАБОТЧИКА

## Первые шаги:
1. Прочитать docs/AUTHENTICATION_LAWS_FOR_AI.md
2. Запустить python test_role_routing.py
3. Изучить архитектуру в docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md
4. Настроить pre-commit хуки
5. Добавить алиасы команд

## Ежедневная работа:
- Перед изменениями: читать документацию
- После изменений: запускать тесты
- Перед коммитом: проверять целостность
```

## 🎯 РЕЗУЛЬТАТ

После выполнения этих шагов:
- ✅ ИИ-агент автоматически загружает правила
- ✅ Система напоминает о критических требованиях
- ✅ Автоматические проверки предотвращают нарушения
- ✅ Команда знает и соблюдает правила
- ✅ Архитектура защищена от случайных изменений

**СИСТЕМА ПОЛНОСТЬЮ ЗАЩИЩЕНА ОТ НАРУШЕНИЙ!** 🛡️

