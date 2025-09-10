"""
Сервис для экспорта/импорта EMR
"""
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from io import BytesIO
import zipfile

logger = logging.getLogger(__name__)


class EMRExportService:
    """Сервис для экспорта и импорта EMR"""

    def __init__(self):
        self.supported_formats = ["json", "pdf", "docx", "zip"]

    async def export_emr_to_json(
        self, 
        emr_data: Dict[str, Any],
        include_versions: bool = False,
        versions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Экспорт EMR в JSON формат"""
        try:
            export_data = {
                "emr_id": emr_data.get("id"),
                "appointment_id": emr_data.get("appointment_id"),
                "patient_id": emr_data.get("patient_id"),
                "doctor_id": emr_data.get("doctor_id"),
                "specialty": emr_data.get("specialty"),
                "template_id": emr_data.get("template_id"),
                "created_at": emr_data.get("created_at"),
                "updated_at": emr_data.get("updated_at"),
                "saved_at": emr_data.get("saved_at"),
                "is_draft": emr_data.get("is_draft"),
                
                # Основные данные EMR
                "complaints": emr_data.get("complaints"),
                "anamnesis": emr_data.get("anamnesis"),
                "examination": emr_data.get("examination"),
                "diagnosis": emr_data.get("diagnosis"),
                "icd10": emr_data.get("icd10"),
                "recommendations": emr_data.get("recommendations"),
                "procedures": emr_data.get("procedures"),
                "attachments": emr_data.get("attachments"),
                
                # Расширенные поля
                "vital_signs": emr_data.get("vital_signs"),
                "lab_results": emr_data.get("lab_results"),
                "imaging_results": emr_data.get("imaging_results"),
                "medications": emr_data.get("medications"),
                "allergies": emr_data.get("allergies"),
                "family_history": emr_data.get("family_history"),
                "social_history": emr_data.get("social_history"),
                
                # AI данные
                "ai_suggestions": emr_data.get("ai_suggestions"),
                "ai_confidence": emr_data.get("ai_confidence"),
                
                # Метаданные экспорта
                "export_metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "export_format": "json",
                    "export_version": "1.0",
                    "include_versions": include_versions
                }
            }
            
            if include_versions and versions:
                export_data["versions"] = versions
            
            return export_data
            
        except Exception as e:
            logger.error(f"Ошибка экспорта EMR в JSON: {e}")
            raise

    async def export_emr_to_pdf(
        self, 
        emr_data: Dict[str, Any],
        template_data: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Экспорт EMR в PDF формат"""
        try:
            # Здесь будет интеграция с библиотекой для создания PDF
            # Пока возвращаем заглушку
            pdf_content = f"""
            ЭЛЕКТРОННАЯ МЕДИЦИНСКАЯ КАРТА
            
            ID: {emr_data.get('id', 'N/A')}
            Дата создания: {emr_data.get('created_at', 'N/A')}
            Специализация: {emr_data.get('specialty', 'N/A')}
            
            ЖАЛОБЫ:
            {emr_data.get('complaints', 'Не указаны')}
            
            АНАМНЕЗ:
            {emr_data.get('anamnesis', 'Не указан')}
            
            ОБЪЕКТИВНЫЙ ОСМОТР:
            {emr_data.get('examination', 'Не указан')}
            
            ДИАГНОЗ:
            {emr_data.get('diagnosis', 'Не указан')}
            Код МКБ-10: {emr_data.get('icd10', 'Не указан')}
            
            РЕКОМЕНДАЦИИ:
            {emr_data.get('recommendations', 'Не указаны')}
            
            Экспортировано: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            # В реальной реализации здесь будет создание PDF
            return pdf_content.encode('utf-8')
            
        except Exception as e:
            logger.error(f"Ошибка экспорта EMR в PDF: {e}")
            raise

    async def export_emr_to_zip(
        self, 
        emr_data: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """Экспорт EMR в ZIP архив"""
        try:
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Добавляем JSON данные EMR
                json_data = await self.export_emr_to_json(emr_data)
                zip_file.writestr(
                    f"emr_{emr_data.get('id', 'unknown')}.json",
                    json.dumps(json_data, ensure_ascii=False, indent=2)
                )
                
                # Добавляем PDF версию
                pdf_data = await self.export_emr_to_pdf(emr_data)
                zip_file.writestr(
                    f"emr_{emr_data.get('id', 'unknown')}.pdf",
                    pdf_data
                )
                
                # Добавляем вложения если есть
                if attachments:
                    for i, attachment in enumerate(attachments):
                        attachment_data = attachment.get('data', b'')
                        attachment_name = attachment.get('name', f'attachment_{i}')
                        zip_file.writestr(f"attachments/{attachment_name}", attachment_data)
                
                # Добавляем README файл
                readme_content = f"""
                ЭЛЕКТРОННАЯ МЕДИЦИНСКАЯ КАРТА - ЭКСПОРТ
                
                Содержимое архива:
                - emr_{emr_data.get('id', 'unknown')}.json - данные EMR в JSON формате
                - emr_{emr_data.get('id', 'unknown')}.pdf - данные EMR в PDF формате
                - attachments/ - прикрепленные файлы (если есть)
                
                Дата экспорта: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
                ID EMR: {emr_data.get('id', 'N/A')}
                Специализация: {emr_data.get('specialty', 'N/A')}
                """
                
                zip_file.writestr("README.txt", readme_content)
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Ошибка экспорта EMR в ZIP: {e}")
            raise

    async def import_emr_from_json(
        self, 
        json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Импорт EMR из JSON формата"""
        try:
            # Валидация структуры JSON
            required_fields = ["appointment_id", "complaints", "diagnosis"]
            for field in required_fields:
                if field not in json_data:
                    raise ValueError(f"Отсутствует обязательное поле: {field}")
            
            # Создаем структуру EMR для импорта
            emr_data = {
                "appointment_id": json_data.get("appointment_id"),
                "complaints": json_data.get("complaints"),
                "anamnesis": json_data.get("anamnesis"),
                "examination": json_data.get("examination"),
                "diagnosis": json_data.get("diagnosis"),
                "icd10": json_data.get("icd10"),
                "recommendations": json_data.get("recommendations"),
                "procedures": json_data.get("procedures"),
                "attachments": json_data.get("attachments"),
                "vital_signs": json_data.get("vital_signs"),
                "lab_results": json_data.get("lab_results"),
                "imaging_results": json_data.get("imaging_results"),
                "medications": json_data.get("medications"),
                "allergies": json_data.get("allergies"),
                "family_history": json_data.get("family_history"),
                "social_history": json_data.get("social_history"),
                "ai_suggestions": json_data.get("ai_suggestions"),
                "ai_confidence": json_data.get("ai_confidence"),
                "template_id": json_data.get("template_id"),
                "specialty": json_data.get("specialty"),
                "is_draft": True  # Импортированные EMR всегда черновики
            }
            
            return emr_data
            
        except Exception as e:
            logger.error(f"Ошибка импорта EMR из JSON: {e}")
            raise

    async def validate_import_data(
        self, 
        json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Валидация данных для импорта"""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": []
            }
            
            # Проверяем обязательные поля
            required_fields = ["appointment_id", "complaints", "diagnosis"]
            for field in required_fields:
                if field not in json_data or not json_data[field]:
                    validation_result["errors"].append(f"Отсутствует обязательное поле: {field}")
                    validation_result["is_valid"] = False
            
            # Проверяем формат данных
            if "appointment_id" in json_data and not isinstance(json_data["appointment_id"], int):
                validation_result["errors"].append("appointment_id должен быть числом")
                validation_result["is_valid"] = False
            
            # Проверяем коды МКБ-10
            if "icd10" in json_data and json_data["icd10"]:
                icd10_code = json_data["icd10"]
                if not self._validate_icd10_code(icd10_code):
                    validation_result["warnings"].append("Код МКБ-10 может быть некорректным")
            
            # Проверяем даты
            date_fields = ["created_at", "updated_at", "saved_at"]
            for field in date_fields:
                if field in json_data and json_data[field]:
                    try:
                        datetime.fromisoformat(json_data[field].replace('Z', '+00:00'))
                    except ValueError:
                        validation_result["warnings"].append(f"Некорректный формат даты в поле {field}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Ошибка валидации импорта: {e}")
            return {
                "is_valid": False,
                "errors": [f"Ошибка валидации: {str(e)}"],
                "warnings": [],
                "suggestions": []
            }

    def _validate_icd10_code(self, code: str) -> bool:
        """Валидация кода МКБ-10"""
        if not code:
            return False
        
        import re
        pattern = r'^[A-Z]\d{2,3}(\.\d{1,2})?$'
        return bool(re.match(pattern, code))

    async def get_export_formats(self) -> List[Dict[str, Any]]:
        """Получить список поддерживаемых форматов экспорта"""
        return [
            {
                "format": "json",
                "name": "JSON",
                "description": "Структурированные данные в JSON формате",
                "mime_type": "application/json",
                "extension": ".json"
            },
            {
                "format": "pdf",
                "name": "PDF",
                "description": "Документ в PDF формате для печати",
                "mime_type": "application/pdf",
                "extension": ".pdf"
            },
            {
                "format": "zip",
                "name": "ZIP",
                "description": "Архив с EMR и прикрепленными файлами",
                "mime_type": "application/zip",
                "extension": ".zip"
            }
        ]


# Глобальный экземпляр сервиса
emr_export_service = EMRExportService()

async def get_emr_export_service() -> EMRExportService:
    """Получить экземпляр сервиса экспорта EMR"""
    return emr_export_service
