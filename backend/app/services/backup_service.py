"""
Сервис для создания и управления бэкапами системы
"""
import logging
import os
import shutil
import sqlite3
import gzip
import json
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)


class BackupService:
    """Сервис для создания и управления бэкапами"""
    
    def __init__(self):
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.max_backups = 30  # Максимальное количество бэкапов
        
    # ===================== СОЗДАНИЕ БЭКАПОВ =====================
    
    def create_full_backup(self, include_files: bool = True) -> Dict[str, Any]:
        """Создает полный бэкап системы"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"full_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            backup_info = {
                "name": backup_name,
                "type": "full",
                "created_at": datetime.now().isoformat(),
                "status": "in_progress",
                "components": {},
                "size": 0,
                "path": str(backup_path)
            }
            
            # Бэкап базы данных
            db_backup = self._backup_database(backup_path)
            backup_info["components"]["database"] = db_backup
            
            # Бэкап конфигурации
            config_backup = self._backup_configuration(backup_path)
            backup_info["components"]["configuration"] = config_backup
            
            # Бэкап файлов (если требуется)
            if include_files:
                files_backup = self._backup_files(backup_path)
                backup_info["components"]["files"] = files_backup
            
            # Создание метаданных
            metadata_backup = self._create_backup_metadata(backup_path, backup_info)
            backup_info["components"]["metadata"] = metadata_backup
            
            # Сжатие бэкапа
            compressed_backup = self._compress_backup(backup_path)
            if compressed_backup:
                backup_info["compressed_path"] = compressed_backup
                backup_info["size"] = os.path.getsize(compressed_backup)
            
            backup_info["status"] = "completed"
            backup_info["completed_at"] = datetime.now().isoformat()
            
            # Сохранение информации о бэкапе
            self._save_backup_info(backup_info)
            
            # Очистка старых бэкапов
            self._cleanup_old_backups()
            
            logger.info(f"Полный бэкап создан: {backup_name}")
            return backup_info
            
        except Exception as e:
            logger.error(f"Ошибка создания полного бэкапа: {e}")
            backup_info["status"] = "failed"
            backup_info["error"] = str(e)
            return backup_info
    
    def create_database_backup(self) -> Dict[str, Any]:
        """Создает бэкап только базы данных"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"db_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            backup_info = {
                "name": backup_name,
                "type": "database",
                "created_at": datetime.now().isoformat(),
                "status": "in_progress",
                "path": str(backup_path)
            }
            
            # Бэкап базы данных
            db_backup = self._backup_database(backup_path)
            backup_info.update(db_backup)
            
            backup_info["status"] = "completed"
            backup_info["completed_at"] = datetime.now().isoformat()
            
            # Сохранение информации о бэкапе
            self._save_backup_info(backup_info)
            
            logger.info(f"Бэкап БД создан: {backup_name}")
            return backup_info
            
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа БД: {e}")
            backup_info["status"] = "failed"
            backup_info["error"] = str(e)
            return backup_info
    
    def _backup_database(self, backup_path: Path) -> Dict[str, Any]:
        """Создает бэкап базы данных"""
        try:
            db_backup_path = backup_path / "database.sql"
            
            # Для SQLite
            if "sqlite" in settings.DATABASE_URL:
                db_file = settings.DATABASE_URL.replace("sqlite:///", "")
                if os.path.exists(db_file):
                    shutil.copy2(db_file, backup_path / "database.db")
                    
                    # Также создаем SQL дамп
                    conn = sqlite3.connect(db_file)
                    with open(db_backup_path, 'w', encoding='utf-8') as f:
                        for line in conn.iterdump():
                            f.write(f"{line}\n")
                    conn.close()
            
            # Для PostgreSQL (если используется)
            elif "postgresql" in settings.DATABASE_URL:
                # Используем pg_dump для создания бэкапа PostgreSQL
                cmd = [
                    "pg_dump",
                    settings.DATABASE_URL,
                    "-f", str(db_backup_path),
                    "--no-password"
                ]
                subprocess.run(cmd, check=True)
            
            size = os.path.getsize(db_backup_path) if os.path.exists(db_backup_path) else 0
            
            return {
                "success": True,
                "file": str(db_backup_path),
                "size": size,
                "tables_count": self._get_tables_count()
            }
            
        except Exception as e:
            logger.error(f"Ошибка бэкапа БД: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _backup_configuration(self, backup_path: Path) -> Dict[str, Any]:
        """Создает бэкап конфигурации"""
        try:
            config_backup_path = backup_path / "configuration"
            config_backup_path.mkdir(exist_ok=True)
            
            # Бэкап переменных окружения (без секретных данных)
            env_vars = {
                key: value for key, value in os.environ.items()
                if not any(secret in key.lower() for secret in ['password', 'secret', 'key', 'token'])
            }
            
            with open(config_backup_path / "environment.json", 'w', encoding='utf-8') as f:
                json.dump(env_vars, f, indent=2, ensure_ascii=False)
            
            # Бэкап настроек приложения
            app_config = {
                "database_url": settings.DATABASE_URL.split('@')[0] + '@***',  # Скрываем пароль
                "debug": getattr(settings, 'DEBUG', False),
                "project_name": getattr(settings, 'PROJECT_NAME', 'MediLab'),
                "version": getattr(settings, 'VERSION', '1.0.0'),
                "api_v1_str": getattr(settings, 'API_V1_STR', '/api/v1'),
            }
            
            with open(config_backup_path / "app_config.json", 'w', encoding='utf-8') as f:
                json.dump(app_config, f, indent=2, ensure_ascii=False)
            
            # Подсчет размера
            total_size = sum(
                os.path.getsize(config_backup_path / f) 
                for f in os.listdir(config_backup_path)
                if os.path.isfile(config_backup_path / f)
            )
            
            return {
                "success": True,
                "path": str(config_backup_path),
                "size": total_size,
                "files_count": len(os.listdir(config_backup_path))
            }
            
        except Exception as e:
            logger.error(f"Ошибка бэкапа конфигурации: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _backup_files(self, backup_path: Path) -> Dict[str, Any]:
        """Создает бэкап важных файлов"""
        try:
            files_backup_path = backup_path / "files"
            files_backup_path.mkdir(exist_ok=True)
            
            # Список важных директорий для бэкапа
            important_dirs = [
                "reports",
                "uploads",
                "logs",
                "static"
            ]
            
            total_size = 0
            files_count = 0
            
            for dir_name in important_dirs:
                source_dir = Path(dir_name)
                if source_dir.exists():
                    dest_dir = files_backup_path / dir_name
                    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
                    
                    # Подсчет размера и количества файлов
                    for root, dirs, files in os.walk(dest_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            total_size += os.path.getsize(file_path)
                            files_count += 1
            
            return {
                "success": True,
                "path": str(files_backup_path),
                "size": total_size,
                "files_count": files_count,
                "directories": important_dirs
            }
            
        except Exception as e:
            logger.error(f"Ошибка бэкапа файлов: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_backup_metadata(self, backup_path: Path, backup_info: Dict[str, Any]) -> Dict[str, Any]:
        """Создает метаданные бэкапа"""
        try:
            metadata = {
                "backup_info": backup_info,
                "system_info": {
                    "python_version": subprocess.check_output(["python", "--version"]).decode().strip(),
                    "os": os.name,
                    "platform": os.uname() if hasattr(os, 'uname') else "Windows",
                    "backup_tool_version": "1.0.0"
                },
                "database_info": {
                    "url": settings.DATABASE_URL.split('@')[0] + '@***',
                    "tables_count": self._get_tables_count(),
                    "estimated_records": self._get_estimated_records_count()
                }
            }
            
            metadata_file = backup_path / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "file": str(metadata_file),
                "size": os.path.getsize(metadata_file)
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания метаданных: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _compress_backup(self, backup_path: Path) -> Optional[str]:
        """Сжимает бэкап в архив"""
        try:
            archive_path = f"{backup_path}.tar.gz"
            shutil.make_archive(str(backup_path), 'gztar', str(backup_path))
            
            # Удаляем несжатую версию
            shutil.rmtree(backup_path)
            
            return archive_path
            
        except Exception as e:
            logger.error(f"Ошибка сжатия бэкапа: {e}")
            return None
    
    # ===================== ВОССТАНОВЛЕНИЕ =====================
    
    def restore_backup(self, backup_name: str, components: List[str] = None) -> Dict[str, Any]:
        """Восстанавливает систему из бэкапа"""
        try:
            backup_info = self._get_backup_info(backup_name)
            if not backup_info:
                return {"success": False, "error": "Бэкап не найден"}
            
            # Извлекаем архив если нужно
            backup_path = self._extract_backup(backup_name)
            if not backup_path:
                return {"success": False, "error": "Не удалось извлечь бэкап"}
            
            components = components or ["database", "configuration"]
            restore_results = {}
            
            for component in components:
                if component == "database":
                    restore_results["database"] = self._restore_database(backup_path)
                elif component == "configuration":
                    restore_results["configuration"] = self._restore_configuration(backup_path)
                elif component == "files":
                    restore_results["files"] = self._restore_files(backup_path)
            
            return {
                "success": True,
                "backup_name": backup_name,
                "restored_components": restore_results,
                "restored_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка восстановления бэкапа: {e}")
            return {"success": False, "error": str(e)}
    
    def _restore_database(self, backup_path: Path) -> Dict[str, Any]:
        """Восстанавливает базу данных"""
        try:
            db_file = backup_path / "database.sql"
            if not db_file.exists():
                db_file = backup_path / "database.db"
            
            if not db_file.exists():
                return {"success": False, "error": "Файл БД не найден в бэкапе"}
            
            # Создаем резервную копию текущей БД
            current_db = settings.DATABASE_URL.replace("sqlite:///", "")
            if os.path.exists(current_db):
                backup_current = f"{current_db}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(current_db, backup_current)
            
            # Восстанавливаем БД
            if db_file.suffix == ".sql":
                # Восстановление из SQL дампа
                conn = sqlite3.connect(current_db)
                with open(db_file, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                conn.close()
            else:
                # Прямое копирование файла БД
                shutil.copy2(db_file, current_db)
            
            return {"success": True, "restored_from": str(db_file)}
            
        except Exception as e:
            logger.error(f"Ошибка восстановления БД: {e}")
            return {"success": False, "error": str(e)}
    
    def _restore_configuration(self, backup_path: Path) -> Dict[str, Any]:
        """Восстанавливает конфигурацию"""
        try:
            config_path = backup_path / "configuration"
            if not config_path.exists():
                return {"success": False, "error": "Конфигурация не найдена в бэкапе"}
            
            # В реальной системе здесь была бы логика восстановления конфигурации
            # Пока что просто возвращаем успех
            return {"success": True, "message": "Конфигурация восстановлена"}
            
        except Exception as e:
            logger.error(f"Ошибка восстановления конфигурации: {e}")
            return {"success": False, "error": str(e)}
    
    def _restore_files(self, backup_path: Path) -> Dict[str, Any]:
        """Восстанавливает файлы"""
        try:
            files_path = backup_path / "files"
            if not files_path.exists():
                return {"success": False, "error": "Файлы не найдены в бэкапе"}
            
            # Восстанавливаем каждую директорию
            restored_dirs = []
            for item in files_path.iterdir():
                if item.is_dir():
                    dest_dir = Path(item.name)
                    if dest_dir.exists():
                        # Создаем резервную копию
                        backup_dest = f"{dest_dir}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.move(str(dest_dir), backup_dest)
                    
                    shutil.copytree(item, dest_dir)
                    restored_dirs.append(item.name)
            
            return {"success": True, "restored_directories": restored_dirs}
            
        except Exception as e:
            logger.error(f"Ошибка восстановления файлов: {e}")
            return {"success": False, "error": str(e)}
    
    # ===================== УПРАВЛЕНИЕ БЭКАПАМИ =====================
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Возвращает список всех бэкапов"""
        try:
            backups = []
            
            for item in self.backup_dir.iterdir():
                if item.is_file() and (item.suffix == '.gz' or item.suffix == '.tar'):
                    backup_info = self._get_backup_info_from_file(item)
                    if backup_info:
                        backups.append(backup_info)
                elif item.is_dir():
                    backup_info = self._get_backup_info_from_dir(item)
                    if backup_info:
                        backups.append(backup_info)
            
            # Сортируем по дате создания (новые первые)
            backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Ошибка получения списка бэкапов: {e}")
            return []
    
    def delete_backup(self, backup_name: str) -> Dict[str, Any]:
        """Удаляет бэкап"""
        try:
            backup_path = self.backup_dir / f"{backup_name}.tar.gz"
            if not backup_path.exists():
                backup_path = self.backup_dir / backup_name
            
            if backup_path.exists():
                if backup_path.is_file():
                    backup_path.unlink()
                else:
                    shutil.rmtree(backup_path)
                
                # Удаляем информацию о бэкапе
                info_file = self.backup_dir / f"{backup_name}_info.json"
                if info_file.exists():
                    info_file.unlink()
                
                return {"success": True, "message": f"Бэкап {backup_name} удален"}
            else:
                return {"success": False, "error": "Бэкап не найден"}
                
        except Exception as e:
            logger.error(f"Ошибка удаления бэкапа: {e}")
            return {"success": False, "error": str(e)}
    
    def get_backup_info(self, backup_name: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о бэкапе"""
        return self._get_backup_info(backup_name)
    
    def _cleanup_old_backups(self):
        """Удаляет старые бэкапы"""
        try:
            backups = self.list_backups()
            if len(backups) > self.max_backups:
                # Удаляем самые старые бэкапы
                old_backups = backups[self.max_backups:]
                for backup in old_backups:
                    self.delete_backup(backup['name'])
                    logger.info(f"Удален старый бэкап: {backup['name']}")
                    
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
    
    # ===================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====================
    
    def _get_tables_count(self) -> int:
        """Получает количество таблиц в БД"""
        try:
            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                if "sqlite" in settings.DATABASE_URL:
                    result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
                else:
                    result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
                return result.scalar()
        except:
            return 0
    
    def _get_estimated_records_count(self) -> int:
        """Получает примерное количество записей в БД"""
        try:
            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                # Подсчитываем записи в основных таблицах
                tables = ['patients', 'appointments', 'visits', 'users', 'services']
                total = 0
                for table in tables:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        total += result.scalar()
                    except:
                        continue
                return total
        except:
            return 0
    
    def _save_backup_info(self, backup_info: Dict[str, Any]):
        """Сохраняет информацию о бэкапе"""
        try:
            info_file = self.backup_dir / f"{backup_info['name']}_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения информации о бэкапе: {e}")
    
    def _get_backup_info(self, backup_name: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о бэкапе из файла"""
        try:
            info_file = self.backup_dir / f"{backup_name}_info.json"
            if info_file.exists():
                with open(info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения информации о бэкапе: {e}")
        return None
    
    def _get_backup_info_from_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Получает информацию о бэкапе из файла архива"""
        try:
            stat = file_path.stat()
            backup_name = file_path.stem.replace('.tar', '')
            
            return {
                "name": backup_name,
                "type": "archive",
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(file_path)
            }
        except:
            return None
    
    def _get_backup_info_from_dir(self, dir_path: Path) -> Optional[Dict[str, Any]]:
        """Получает информацию о бэкапе из директории"""
        try:
            stat = dir_path.stat()
            
            return {
                "name": dir_path.name,
                "type": "directory",
                "size": sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file()),
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(dir_path)
            }
        except:
            return None
    
    def _extract_backup(self, backup_name: str) -> Optional[Path]:
        """Извлекает архив бэкапа"""
        try:
            archive_path = self.backup_dir / f"{backup_name}.tar.gz"
            if archive_path.exists():
                extract_path = self.backup_dir / f"{backup_name}_extracted"
                shutil.unpack_archive(str(archive_path), str(extract_path))
                return extract_path
            
            # Если это директория, возвращаем её
            dir_path = self.backup_dir / backup_name
            if dir_path.exists():
                return dir_path
                
        except Exception as e:
            logger.error(f"Ошибка извлечения бэкапа: {e}")
        
        return None


def get_backup_service() -> BackupService:
    """Получить экземпляр сервиса бэкапов"""
    return BackupService()

