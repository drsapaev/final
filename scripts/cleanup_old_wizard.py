#!/usr/bin/env python3
"""
Скрипт для безопасного удаления старого мастера регистрации
Использовать только после полного тестирования нового мастера!

Запуск: python scripts/cleanup_old_wizard.py --dry-run
        python scripts/cleanup_old_wizard.py --execute
"""

import os
import sys
import argparse
import shutil
from pathlib import Path

EXECUTE_CONFIRM_ENV = "CONFIRM_CLEANUP_OLD_WIZARD_EXECUTE"


def require_execute_confirmation():
    if os.getenv(EXECUTE_CONFIRM_ENV) != "1":
        raise SystemExit(
            f"Refusing destructive old-wizard cleanup. Set {EXECUTE_CONFIRM_ENV}=1 "
            "only after a reviewed dry-run and frontend route/import verification."
        )


class WizardCleanup:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.files_to_remove = []
        self.files_to_modify = []
        self.backup_created = False
        
    def log(self, message, level="INFO"):
        prefix = "[DRY-RUN] " if self.dry_run else "[EXECUTE] "
        print(f"{prefix}{level}: {message}")
        
    def create_backup(self):
        """Создать резервную копию важных файлов"""
        backup_dir = self.project_root / "backup_old_wizard"
        
        if self.dry_run:
            self.log(f"Создание резервной копии в {backup_dir}")
            return True
            
        try:
            backup_dir.mkdir(exist_ok=True)
            
            # Файлы для резервного копирования
            files_to_backup = [
                "frontend/src/components/wizard/AppointmentWizard.jsx",
                "frontend/src/pages/RegistrarPanel.jsx",
                "frontend/src/components/admin/WizardSettings.jsx",
                "frontend/src/hooks/useWizardSettings.js"
            ]
            
            for file_path in files_to_backup:
                src = self.project_root / file_path
                if src.exists():
                    dst = backup_dir / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    self.log(f"Скопирован в резерв: {file_path}")
                    
            self.backup_created = True
            self.log("Резервная копия создана успешно")
            return True
            
        except Exception as e:
            self.log(f"Ошибка создания резервной копии: {e}", "ERROR")
            return False
    
    def identify_files_to_remove(self):
        """Определить файлы для удаления"""
        files_to_check = [
            # Старый мастер
            "frontend/src/components/wizard/AppointmentWizard.jsx",
            
            # Настройки A/B теста (после подтверждения стабильности)
            "frontend/src/components/admin/WizardSettings.jsx",
            "frontend/src/hooks/useWizardSettings.js",
            
            # Тестовые файлы (опционально)
            "frontend/src/utils/wizardTester.js",
        ]
        
        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.files_to_remove.append(full_path)
                self.log(f"Файл для удаления: {file_path}")
                
    def identify_files_to_modify(self):
        """Определить файлы для модификации"""
        files_to_check = [
            # Убрать условный рендеринг
            "frontend/src/pages/RegistrarPanel.jsx",
            
            # Убрать настройки из админ-панели
            "frontend/src/pages/AdminPanel.jsx",
            
            # Убрать маршруты
            "frontend/src/App.jsx",
            
            # Переименовать V2 в основной
            "frontend/src/components/wizard/AppointmentWizardV2.jsx",
            "frontend/src/components/wizard/AppointmentWizardV2.css",
        ]
        
        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if full_path.exists():
                self.files_to_modify.append(full_path)
                self.log(f"Файл для модификации: {file_path}")
    
    def remove_old_wizard_import(self, file_path):
        """Удалить импорт старого мастера из файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Удаляем импорт старого мастера
            lines = content.split('\n')
            new_lines = []
            
            for line in lines:
                # Пропускаем строки с импортом старого мастера
                if "import AppointmentWizard from '../components/wizard/AppointmentWizard'" in line:
                    self.log(f"Удаляем импорт: {line.strip()}")
                    continue
                if "import useWizardSettings" in line:
                    self.log(f"Удаляем импорт: {line.strip()}")
                    continue
                new_lines.append(line)
            
            new_content = '\n'.join(new_lines)
            
            if not self.dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                    
            self.log(f"Обновлён файл: {file_path}")
            return True
            
        except Exception as e:
            self.log(f"Ошибка обновления {file_path}: {e}", "ERROR")
            return False
    
    def rename_v2_to_main(self):
        """Переименовать V2 файлы в основные"""
        renames = [
            (
                "frontend/src/components/wizard/AppointmentWizardV2.jsx",
                "frontend/src/components/wizard/AppointmentWizard.jsx"
            ),
            (
                "frontend/src/components/wizard/AppointmentWizardV2.css",
                "frontend/src/components/wizard/AppointmentWizard.css"
            )
        ]
        
        for old_path, new_path in renames:
            old_full = self.project_root / old_path
            new_full = self.project_root / new_path
            
            if old_full.exists():
                if self.dry_run:
                    self.log(f"Переименование: {old_path} → {new_path}")
                else:
                    # Удаляем целевой файл если существует
                    if new_full.exists():
                        new_full.unlink()
                    old_full.rename(new_full)
                    self.log(f"Переименован: {old_path} → {new_path}")
    
    def remove_wizard_settings_from_admin(self):
        """Удалить настройки мастера из админ-панели"""
        admin_panel_path = self.project_root / "frontend/src/pages/AdminPanel.jsx"
        
        if not admin_panel_path.exists():
            return
            
        try:
            with open(admin_panel_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Удаляем импорт WizardSettings
            content = content.replace(
                "import WizardSettings from '../components/admin/WizardSettings';\n", 
                ""
            )
            
            # Удаляем пункт меню
            content = content.replace(
                "        { to: '/admin/wizard-settings', label: 'Настройки мастера', icon: Monitor }\n",
                ""
            )
            
            # Удаляем case в switch
            content = content.replace(
                "      case 'wizard-settings':\n        return <WizardSettings />;\n",
                ""
            )
            
            if not self.dry_run:
                with open(admin_panel_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            self.log("Удалены настройки мастера из админ-панели")
            
        except Exception as e:
            self.log(f"Ошибка обновления AdminPanel.jsx: {e}", "ERROR")
    
    def remove_wizard_routes(self):
        """Удалить маршруты настроек мастера"""
        app_path = self.project_root / "frontend/src/App.jsx"
        
        if not app_path.exists():
            return
            
        try:
            with open(app_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Удаляем маршрут настроек мастера
            content = content.replace(
                '          <Route path="admin/wizard-settings" element={<RequireAuth roles={[\'Admin\']}><AdminPanel /></RequireAuth>} />\n',
                ""
            )
            
            if not self.dry_run:
                with open(app_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            self.log("Удалён маршрут настроек мастера")
            
        except Exception as e:
            self.log(f"Ошибка обновления App.jsx: {e}", "ERROR")
    
    def cleanup_registrar_panel(self):
        """Очистить RegistrarPanel от условной логики"""
        panel_path = self.project_root / "frontend/src/pages/RegistrarPanel.jsx"
        
        if not panel_path.exists():
            return
            
        try:
            with open(panel_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Удаляем импорты
            content = content.replace(
                "import AppointmentWizard from '../components/wizard/AppointmentWizard';\n", ""
            )
            content = content.replace(
                "import AppointmentWizardV2 from '../components/wizard/AppointmentWizardV2';\n",
                "import AppointmentWizard from '../components/wizard/AppointmentWizard';\n"
            )
            content = content.replace(
                "import useWizardSettings from '../hooks/useWizardSettings';\n", ""
            )
            
            # Удаляем хук
            content = content.replace(
                "  // Настройки мастера регистрации (A/B тест)\n  const { useNewWizard, loading: wizardSettingsLoading } = useWizardSettings();\n",
                ""
            )
            
            # Упрощаем рендеринг мастера (это сложная замена, нужно делать осторожно)
            self.log("ВНИМАНИЕ: Ручная очистка RegistrarPanel требуется для условного рендеринга")
            
            if not self.dry_run:
                with open(panel_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            self.log("Частично очищен RegistrarPanel (требуется ручная доработка)")
            
        except Exception as e:
            self.log(f"Ошибка обновления RegistrarPanel.jsx: {e}", "ERROR")
    
    def remove_backend_wizard_settings(self):
        """Удалить backend endpoints для настроек мастера"""
        wizard_api_path = self.project_root / "backend/app/api/v1/endpoints/registrar_wizard.py"
        
        if not wizard_api_path.exists():
            return
            
        self.log("ВНИМАНИЕ: Удаление wizard-settings endpoints из backend требует ручной работы")
        self.log("Найдите и удалите секцию '# ==================== НАСТРОЙКИ МАСТЕРА РЕГИСТРАЦИИ =='")
    
    def execute_cleanup(self):
        """Выполнить полную очистку"""
        self.log("Начинаем очистку старого мастера регистрации")
        
        # 1. Создаём резервную копию
        if not self.create_backup():
            self.log("Не удалось создать резервную копию. Прерываем операцию.", "ERROR")
            return False
        
        # 2. Определяем файлы
        self.identify_files_to_remove()
        self.identify_files_to_modify()
        
        # 3. Переименовываем V2 в основные файлы
        self.rename_v2_to_main()
        
        # 4. Удаляем настройки из админ-панели
        self.remove_wizard_settings_from_admin()
        
        # 5. Удаляем маршруты
        self.remove_wizard_routes()
        
        # 6. Очищаем RegistrarPanel
        self.cleanup_registrar_panel()
        
        # 7. Удаляем файлы
        for file_path in self.files_to_remove:
            if self.dry_run:
                self.log(f"Удаление файла: {file_path}")
            else:
                try:
                    file_path.unlink()
                    self.log(f"Удалён файл: {file_path}")
                except Exception as e:
                    self.log(f"Ошибка удаления {file_path}: {e}", "ERROR")
        
        # 8. Backend очистка
        self.remove_backend_wizard_settings()
        
        self.log("Очистка завершена")
        
        if not self.dry_run:
            self.log("ВАЖНО: Выполните тестирование системы!")
            self.log("ВАЖНО: Проверьте, что все импорты корректны!")
            self.log("ВАЖНО: Возможно потребуется ручная доработка некоторых файлов!")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="Очистка старого мастера регистрации")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        default=True,
        help="Показать что будет сделано без выполнения (по умолчанию)"
    )
    parser.add_argument(
        "--execute", 
        action="store_true",
        help="Выполнить очистку (ОСТОРОЖНО!)"
    )
    
    args = parser.parse_args()
    
    if args.execute:
        require_execute_confirmation()

        print("⚠️  ВНИМАНИЕ: Вы собираетесь удалить старый мастер регистрации!")
        print("⚠️  Убедитесь, что новый мастер работает стабильно в продакшене!")
        print("⚠️  Создана резервная копия важных файлов!")
        
        confirm = input("Продолжить? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Операция отменена.")
            return
            
        cleanup = WizardCleanup(dry_run=False)
    else:
        print("🔍 Режим предварительного просмотра (dry-run)")
        print("Для выполнения используйте: --execute")
        cleanup = WizardCleanup(dry_run=True)
    
    cleanup.execute_cleanup()

if __name__ == "__main__":
    main()
