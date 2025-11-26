"""
Сервис для экспорта и импорта EMR данных
"""
import json
import zipfile
import io
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from app.schemas.emr import EMRBase, EMRUpdate
from app.schemas.emr_template import EMRTemplateBase
from app.schemas.emr_version import EMRVersionBase


class EMRExportService:
    """Сервис для экспорта и импорта EMR данных"""
    
    def __init__(self):
        self.supported_formats = ['json', 'xml', 'csv', 'pdf', 'docx', 'zip']
    
    async def export_emr_to_json(
        self,
        emr_data: Dict[str, Any],
        include_versions: bool = False,
        include_templates: bool = False,
        include_attachments: bool = False
    ) -> Dict[str, Any]:
        """Экспорт EMR в JSON формат"""
        try:
            export_data = {
                "metadata": {
                    "export_date": datetime.utcnow().isoformat(),
                    "format_version": "1.0",
                    "export_type": "emr",
                    "includes": {
                        "versions": include_versions,
                        "templates": include_templates,
                        "attachments": include_attachments
                    }
                },
                "emr": emr_data
            }
            
            if include_versions and 'versions' in emr_data:
                export_data["versions"] = emr_data['versions']
            
            if include_templates and 'template' in emr_data:
                export_data["template"] = emr_data['template']
            
            if include_attachments and 'attachments' in emr_data:
                export_data["attachments"] = emr_data['attachments']
            
            return export_data
            
        except Exception as e:
            raise Exception(f"Ошибка экспорта в JSON: {str(e)}")
    
    async def export_emr_to_xml(
        self,
        emr_data: Dict[str, Any],
        include_versions: bool = False
    ) -> str:
        """Экспорт EMR в XML формат"""
        try:
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_content += '<emr_export>\n'
            xml_content += f'  <metadata>\n'
            xml_content += f'    <export_date>{datetime.utcnow().isoformat()}</export_date>\n'
            xml_content += f'    <format_version>1.0</format_version>\n'
            xml_content += f'    <export_type>emr</export_type>\n'
            xml_content += f'  </metadata>\n'
            
            xml_content += '  <emr_data>\n'
            for key, value in emr_data.items():
                if isinstance(value, dict):
                    xml_content += f'    <{key}>\n'
                    for sub_key, sub_value in value.items():
                        xml_content += f'      <{sub_key}>{sub_value}</{sub_key}>\n'
                    xml_content += f'    </{key}>\n'
                else:
                    xml_content += f'    <{key}>{value}</{key}>\n'
            xml_content += '  </emr_data>\n'
            
            if include_versions and 'versions' in emr_data:
                xml_content += '  <versions>\n'
                for version in emr_data['versions']:
                    xml_content += '    <version>\n'
                    for key, value in version.items():
                        xml_content += f'      <{key}>{value}</{key}>\n'
                    xml_content += '    </version>\n'
                xml_content += '  </versions>\n'
            
            xml_content += '</emr_export>'
            
            return xml_content
            
        except Exception as e:
            raise Exception(f"Ошибка экспорта в XML: {str(e)}")
    
    async def export_emr_to_csv(
        self,
        emr_data: Dict[str, Any],
        fields: List[str] = None
    ) -> str:
        """Экспорт EMR в CSV формат"""
        try:
            if fields is None:
                fields = list(emr_data.keys())
            
            csv_content = ','.join(fields) + '\n'
            
            row_data = []
            for field in fields:
                value = emr_data.get(field, '')
                if isinstance(value, (dict, list)):
                    value = str(value)
                row_data.append(f'"{value}"')
            
            csv_content += ','.join(row_data) + '\n'
            
            return csv_content
            
        except Exception as e:
            raise Exception(f"Ошибка экспорта в CSV: {str(e)}")
    
    async def export_emr_to_zip(
        self,
        emr_data: Dict[str, Any],
        include_attachments: bool = True
    ) -> bytes:
        """Экспорт EMR в ZIP архив"""
        try:
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Добавляем JSON файл с данными EMR
                json_data = await self.export_emr_to_json(emr_data, include_versions=True)
                zip_file.writestr('emr_data.json', json.dumps(json_data, ensure_ascii=False, indent=2))
                
                # Добавляем XML файл
                xml_data = await self.export_emr_to_xml(emr_data, include_versions=True)
                zip_file.writestr('emr_data.xml', xml_data)
                
                # Добавляем CSV файл
                csv_data = await self.export_emr_to_csv(emr_data)
                zip_file.writestr('emr_data.csv', csv_data)
                
                # Добавляем вложения если есть
                if include_attachments and 'attachments' in emr_data:
                    for attachment in emr_data['attachments']:
                        if 'content' in attachment and 'filename' in attachment:
                            zip_file.writestr(f"attachments/{attachment['filename']}", attachment['content'])
            
            zip_buffer.seek(0)
            return zip_buffer.getvalue()
            
        except Exception as e:
            raise Exception(f"Ошибка экспорта в ZIP: {str(e)}")
    
    async def import_emr_from_json(
        self,
        json_data: Union[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Импорт EMR из JSON формата"""
        try:
            if isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data
            
            # Валидируем структуру
            if 'emr' not in data:
                raise ValueError("Отсутствуют данные EMR в импортируемом файле")
            
            emr_data = data['emr']
            
            # Проверяем версию формата
            if 'metadata' in data:
                format_version = data['metadata'].get('format_version', '1.0')
                if format_version != '1.0':
                    print(f"Предупреждение: Неподдерживаемая версия формата {format_version}")
            
            return emr_data
            
        except Exception as e:
            raise Exception(f"Ошибка импорта из JSON: {str(e)}")
    
    async def import_emr_from_xml(
        self,
        xml_data: str
    ) -> Dict[str, Any]:
        """Импорт EMR из XML формата"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(xml_data)
            
            emr_data = {}
            
            # Извлекаем данные EMR
            emr_element = root.find('emr_data')
            if emr_element is not None:
                for child in emr_element:
                    if len(child) == 0:
                        emr_data[child.tag] = child.text
                    else:
                        emr_data[child.tag] = {}
                        for sub_child in child:
                            emr_data[child.tag][sub_child.tag] = sub_child.text
            
            return emr_data
            
        except Exception as e:
            raise Exception(f"Ошибка импорта из XML: {str(e)}")
    
    async def import_emr_from_zip(
        self,
        zip_data: bytes
    ) -> Dict[str, Any]:
        """Импорт EMR из ZIP архива"""
        try:
            zip_buffer = io.BytesIO(zip_data)
            
            with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                # Ищем JSON файл с данными EMR
                json_files = [f for f in zip_file.namelist() if f.endswith('.json')]
                
                if not json_files:
                    raise ValueError("JSON файл с данными EMR не найден в архиве")
                
                # Читаем первый JSON файл
                json_content = zip_file.read(json_files[0]).decode('utf-8')
                return await self.import_emr_from_json(json_content)
                
        except Exception as e:
            raise Exception(f"Ошибка импорта из ZIP: {str(e)}")
    
    async def validate_import_data(
        self,
        data: Union[str, Dict[str, Any], bytes],
        format_type: str = 'json'
    ) -> Dict[str, Any]:
        """Валидация импортируемых данных"""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "data_type": None,
                "format_version": None
            }
            
            if format_type == 'json':
                if isinstance(data, str):
                    json_data = json.loads(data)
                else:
                    json_data = data
                
                validation_result["data_type"] = "json"
                
                if 'metadata' in json_data:
                    validation_result["format_version"] = json_data['metadata'].get('format_version')
                
                if 'emr' not in json_data:
                    validation_result["errors"].append("Отсутствуют данные EMR")
                    validation_result["is_valid"] = False
                
                # Проверяем обязательные поля EMR
                if 'emr' in json_data:
                    emr_data = json_data['emr']
                    required_fields = ['patient_id', 'doctor_id', 'complaints']
                    
                    for field in required_fields:
                        if field not in emr_data:
                            validation_result["errors"].append(f"Отсутствует обязательное поле: {field}")
                            validation_result["is_valid"] = False
            
            elif format_type == 'xml':
                import xml.etree.ElementTree as ET
                
                try:
                    root = ET.fromstring(data)
                    validation_result["data_type"] = "xml"
                    
                    if root.tag != 'emr_export':
                        validation_result["errors"].append("Неправильный корневой элемент XML")
                        validation_result["is_valid"] = False
                    
                    if root.find('emr_data') is None:
                        validation_result["errors"].append("Отсутствуют данные EMR в XML")
                        validation_result["is_valid"] = False
                        
                except ET.ParseError as e:
                    validation_result["errors"].append(f"Ошибка парсинга XML: {str(e)}")
                    validation_result["is_valid"] = False
            
            elif format_type == 'zip':
                try:
                    zip_buffer = io.BytesIO(data)
                    with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                        validation_result["data_type"] = "zip"
                        
                        json_files = [f for f in zip_file.namelist() if f.endswith('.json')]
                        if not json_files:
                            validation_result["errors"].append("JSON файл не найден в архиве")
                            validation_result["is_valid"] = False
                        
                except zipfile.BadZipFile:
                    validation_result["errors"].append("Неправильный формат ZIP архива")
                    validation_result["is_valid"] = False
            
            return validation_result
            
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"Ошибка валидации: {str(e)}"],
                "warnings": [],
                "data_type": None,
                "format_version": None
            }
    
    async def get_export_formats(self) -> List[str]:
        """Получить список поддерживаемых форматов экспорта"""
        return self.supported_formats
    
    async def get_import_formats(self) -> List[str]:
        """Получить список поддерживаемых форматов импорта"""
        return ['json', 'xml', 'zip']
    
    async def estimate_export_size(
        self,
        emr_data: Dict[str, Any],
        format_type: str = 'json'
    ) -> Dict[str, Any]:
        """Оценить размер экспортируемых данных"""
        try:
            if format_type == 'json':
                json_data = await self.export_emr_to_json(emr_data, include_versions=True)
                size = len(json.dumps(json_data, ensure_ascii=False).encode('utf-8'))
            elif format_type == 'xml':
                xml_data = await self.export_emr_to_xml(emr_data, include_versions=True)
                size = len(xml_data.encode('utf-8'))
            elif format_type == 'zip':
                zip_data = await self.export_emr_to_zip(emr_data, include_attachments=True)
                size = len(zip_data)
            else:
                size = 0
            
            return {
                "format": format_type,
                "size_bytes": size,
                "size_kb": round(size / 1024, 2),
                "size_mb": round(size / (1024 * 1024), 2),
                "estimated_download_time": f"{round(size / (1024 * 1024), 1)} сек" if size > 1024 * 1024 else "< 1 сек"
            }
            
        except Exception as e:
            return {
                "format": format_type,
                "size_bytes": 0,
                "size_kb": 0,
                "size_mb": 0,
                "estimated_download_time": "неизвестно",
                "error": str(e)
            }