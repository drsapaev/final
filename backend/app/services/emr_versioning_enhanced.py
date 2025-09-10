"""
Расширенная система версионирования EMR
"""
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.emr_template import EMRVersion
from app.crud.emr_template import emr_version
from app.schemas.emr_template import EMRVersionCreate

logger = logging.getLogger(__name__)


class EMRVersioningEnhancedService:
    """Расширенная система версионирования EMR"""

    def __init__(self):
        self.change_types = {
            "created": "Создание",
            "updated": "Обновление",
            "restored": "Восстановление",
            "field_added": "Добавлено поле",
            "field_removed": "Удалено поле",
            "field_modified": "Изменено поле",
            "ai_enhanced": "AI улучшение",
            "validated": "Валидация"
        }

    async def create_version_with_analysis(
        self,
        db: Session,
        emr_id: int,
        version_data: Dict[str, Any],
        change_type: str,
        change_description: Optional[str] = None,
        changed_by: Optional[int] = None,
        previous_version: Optional[Dict[str, Any]] = None
    ) -> EMRVersion:
        """Создать версию с анализом изменений"""
        try:
            # Анализируем изменения если есть предыдущая версия
            if previous_version:
                changes_analysis = await self._analyze_changes(
                    previous_version, version_data
                )
                change_description = await self._generate_change_description(
                    changes_analysis, change_type
                )
            
            # Получаем следующий номер версии
            from app.crud.emr_version import get_next_version_number
            version_number = get_next_version_number(db, emr_id)
            
            # Создаем данные для версии
            from app.schemas.emr_version import EMRVersionCreate
            version_create = EMRVersionCreate(
                emr_id=emr_id,
                version_number=version_number,
                data=version_data,
                change_type=change_type,
                change_description=change_description,
                changed_by=changed_by or 1,
                is_current=True
            )
            
            # Создаем версию
            from app.crud.emr_version import create_version
            version = create_version(db, version_create)
            
            return version
            
        except Exception as e:
            logger.error(f"Ошибка создания версии с анализом: {e}")
            raise

    async def get_version_comparison(
        self,
        db: Session,
        emr_id: int,
        version1_id: int,
        version2_id: int
    ) -> Dict[str, Any]:
        """Получить сравнение двух версий EMR"""
        try:
            # Получаем версии
            from app.crud.emr_version import get_version
            version1 = get_version(db, version1_id)
            version2 = get_version(db, version2_id)
            
            if not version1 or not version2:
                raise ValueError("Одна или обе версии не найдены")
            
            # Сравниваем данные
            comparison = await self._compare_versions(
                version1.data,
                version2.data
            )
            
            return {
                "emr_id": emr_id,
                "version1": {
                    "id": version1.id,
                    "version_number": version1.version_number,
                    "created_at": version1.created_at,
                    "change_type": version1.change_type,
                    "changed_by": version1.changed_by
                },
                "version2": {
                    "id": version2.id,
                    "version_number": version2.version_number,
                    "created_at": version2.created_at,
                    "change_type": version2.change_type,
                    "changed_by": version2.changed_by
                },
                "comparison": comparison
            }
            
        except Exception as e:
            logger.error(f"Ошибка сравнения версий: {e}")
            raise

    async def get_version_timeline(
        self,
        db: Session,
        emr_id: int,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получить временную линию версий EMR"""
        try:
            from app.crud.emr_version import get_versions_by_emr
            versions = get_versions_by_emr(db, emr_id=emr_id, limit=limit)
            
            timeline = []
            for version in versions:
                timeline.append({
                    "id": version.id,
                    "version_number": version.version_number,
                    "change_type": version.change_type,
                    "change_type_label": self.change_types.get(
                        version.change_type, version.change_type
                    ),
                    "change_description": version.change_description,
                    "changed_by": version.changed_by,
                    "created_at": version.created_at,
                    "data_summary": await self._get_data_summary(version.data)
                })
            
            return timeline
            
        except Exception as e:
            logger.error(f"Ошибка получения временной линии: {e}")
            raise

    async def restore_version_with_backup(
        self,
        db: Session,
        emr_id: int,
        version_id: int,
        restored_by: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Восстановить версию с созданием резервной копии"""
        try:
            # Получаем текущую версию EMR
            current_emr = await self._get_current_emr_data(db, emr_id)
            
            # Получаем версию для восстановления
            target_version = emr_version.get(db, id=version_id)
            if not target_version:
                raise ValueError("Версия не найдена")
            
            # Создаем резервную копию текущего состояния
            backup_version = emr_version.create_version(
                db=db,
                emr_id=emr_id,
                version_data=current_emr,
                change_type="backup",
                change_description=f"Резервная копия перед восстановлением версии {target_version.version_number}",
                changed_by=restored_by
            )
            
            # Восстанавливаем целевую версию
            restored_version = emr_version.create_version(
                db=db,
                emr_id=emr_id,
                version_data=target_version.data,
                change_type="restored",
                change_description=reason or f"Восстановление версии {target_version.version_number}",
                changed_by=restored_by
            )
            
            return {
                "emr_id": emr_id,
                "restored_version": {
                    "id": restored_version.id,
                    "version_number": restored_version.version_number,
                    "original_version_id": version_id
                },
                "backup_version": {
                    "id": backup_version.id,
                    "version_number": backup_version.version_number
                },
                "restored_at": restored_version.created_at
            }
            
        except Exception as e:
            logger.error(f"Ошибка восстановления версии: {e}")
            raise

    async def get_version_statistics(
        self,
        db: Session,
        emr_id: int
    ) -> Dict[str, Any]:
        """Получить статистику версий EMR"""
        try:
            from app.crud.emr_version import get_versions_by_emr
            versions = get_versions_by_emr(db, emr_id=emr_id, limit=1000)
            
            if not versions:
                return {"total_versions": 0}
            
            # Подсчитываем статистику
            total_versions = len(versions)
            change_type_counts = {}
            changes_by_user = {}
            changes_by_month = {}
            
            for version in versions:
                # Типы изменений
                change_type = version.change_type
                change_type_counts[change_type] = change_type_counts.get(change_type, 0) + 1
                
                # Изменения по пользователям
                if version.changed_by:
                    changes_by_user[version.changed_by] = changes_by_user.get(version.changed_by, 0) + 1
                
                # Изменения по месяцам
                month_key = version.created_at.strftime("%Y-%m")
                changes_by_month[month_key] = changes_by_month.get(month_key, 0) + 1
            
            return {
                "total_versions": total_versions,
                "change_type_counts": change_type_counts,
                "changes_by_user": changes_by_user,
                "changes_by_month": changes_by_month,
                "first_version": versions[-1].created_at,
                "last_version": versions[0].created_at,
                "most_active_user": max(changes_by_user.items(), key=lambda x: x[1])[0] if changes_by_user else None
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики версий: {e}")
            raise

    async def _analyze_changes(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ изменений между версиями"""
        import json
        
        # Парсим JSON если это строки
        if isinstance(old_data, str):
            old_data = json.loads(old_data)
        if isinstance(new_data, str):
            new_data = json.loads(new_data)
        
        changes = {
            "added_fields": [],
            "removed_fields": [],
            "modified_fields": [],
            "unchanged_fields": []
        }
        
        all_keys = set(old_data.keys()) | set(new_data.keys())
        
        for key in all_keys:
            old_value = old_data.get(key)
            new_value = new_data.get(key)
            
            if key not in old_data:
                changes["added_fields"].append({
                    "field": key,
                    "new_value": new_value
                })
            elif key not in new_data:
                changes["removed_fields"].append({
                    "field": key,
                    "old_value": old_value
                })
            elif old_value != new_value:
                changes["modified_fields"].append({
                    "field": key,
                    "old_value": old_value,
                    "new_value": new_value
                })
            else:
                changes["unchanged_fields"].append(key)
        
        return changes

    async def _generate_change_description(
        self,
        changes_analysis: Dict[str, Any],
        change_type: str
    ) -> str:
        """Генерация описания изменений"""
        description_parts = []
        
        if changes_analysis["added_fields"]:
            fields = [change["field"] for change in changes_analysis["added_fields"]]
            description_parts.append(f"Добавлены поля: {', '.join(fields)}")
        
        if changes_analysis["removed_fields"]:
            fields = [change["field"] for change in changes_analysis["removed_fields"]]
            description_parts.append(f"Удалены поля: {', '.join(fields)}")
        
        if changes_analysis["modified_fields"]:
            fields = [change["field"] for change in changes_analysis["modified_fields"]]
            description_parts.append(f"Изменены поля: {', '.join(fields)}")
        
        if not description_parts:
            description_parts.append("Изменения не обнаружены")
        
        return "; ".join(description_parts)

    async def _compare_versions(
        self,
        data1: Dict[str, Any],
        data2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Сравнение двух версий данных"""
        import json
        
        # Парсим JSON если это строки
        if isinstance(data1, str):
            data1 = json.loads(data1)
        if isinstance(data2, str):
            data2 = json.loads(data2)
        
        comparison = {
            "fields_changed": 0,
            "fields_added": 0,
            "fields_removed": 0,
            "changes": []
        }
        
        all_keys = set(data1.keys()) | set(data2.keys())
        
        for key in all_keys:
            value1 = data1.get(key)
            value2 = data2.get(key)
            
            if key not in data1:
                comparison["fields_added"] += 1
                comparison["changes"].append({
                    "field": key,
                    "type": "added",
                    "value": value2
                })
            elif key not in data2:
                comparison["fields_removed"] += 1
                comparison["changes"].append({
                    "field": key,
                    "type": "removed",
                    "value": value1
                })
            elif value1 != value2:
                comparison["fields_changed"] += 1
                comparison["changes"].append({
                    "field": key,
                    "type": "modified",
                    "old_value": value1,
                    "new_value": value2
                })
        
        return comparison

    async def _get_data_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Получить краткое описание данных версии"""
        import json
        
        # Парсим JSON если это строка
        if isinstance(data, str):
            data = json.loads(data)
        
        summary = {
            "fields_count": len(data),
            "has_complaints": bool(data.get("complaints")),
            "has_diagnosis": bool(data.get("diagnosis")),
            "has_icd10": bool(data.get("icd10")),
            "has_recommendations": bool(data.get("recommendations")),
            "is_draft": data.get("is_draft", False)
        }
        
        return summary

    async def _get_current_emr_data(self, db: Session, emr_id: int) -> Dict[str, Any]:
        """Получить текущие данные EMR"""
        # Здесь должен быть запрос к базе данных для получения текущих данных EMR
        # Пока возвращаем заглушку
        return {
            "id": emr_id,
            "complaints": "",
            "diagnosis": "",
            "updated_at": datetime.utcnow()
        }


# Создаем экземпляр сервиса
emr_versioning_enhanced = EMRVersioningEnhancedService()
