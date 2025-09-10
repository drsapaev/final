"""
Сервис для экспорта аналитических отчетов
"""
import json
import csv
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from io import BytesIO, StringIO
import zipfile

logger = logging.getLogger(__name__)


class AnalyticsExportService:
    """Сервис для экспорта аналитических отчетов"""

    def __init__(self):
        self.supported_formats = ["json", "csv", "pdf", "excel", "zip"]

    async def export_to_json(
        self, 
        data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Экспорт данных в JSON формат"""
        try:
            if not filename:
                filename = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Добавляем метаданные экспорта
            export_data = {
                "export_metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "export_format": "json",
                    "export_version": "1.0",
                    "filename": filename
                },
                "data": data
            }
            
            return {
                "content": json.dumps(export_data, ensure_ascii=False, indent=2),
                "filename": filename,
                "mime_type": "application/json",
                "size": len(json.dumps(export_data, ensure_ascii=False))
            }
            
        except Exception as e:
            logger.error(f"Ошибка экспорта в JSON: {e}")
            raise

    async def export_to_csv(
        self, 
        data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Экспорт данных в CSV формат"""
        try:
            if not filename:
                filename = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Создаем CSV данные
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            
            # Записываем метаданные
            writer.writerow(["Analytics Report"])
            writer.writerow(["Exported at", datetime.utcnow().isoformat()])
            writer.writerow(["Export format", "CSV"])
            writer.writerow([])
            
            # Записываем основные данные
            self._write_dict_to_csv(writer, data, "")
            
            csv_content = csv_buffer.getvalue()
            
            return {
                "content": csv_content,
                "filename": filename,
                "mime_type": "text/csv",
                "size": len(csv_content)
            }
            
        except Exception as e:
            logger.error(f"Ошибка экспорта в CSV: {e}")
            raise

    async def export_to_pdf(
        self, 
        data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Экспорт данных в PDF формат"""
        try:
            if not filename:
                filename = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Здесь будет интеграция с библиотекой для создания PDF
            # Пока возвращаем текстовую версию
            pdf_content = self._generate_text_report(data)
            
            return {
                "content": pdf_content.encode('utf-8'),
                "filename": filename,
                "mime_type": "application/pdf",
                "size": len(pdf_content)
            }
            
        except Exception as e:
            logger.error(f"Ошибка экспорта в PDF: {e}")
            raise

    async def export_to_excel(
        self, 
        data: Dict[str, Any],
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Экспорт данных в Excel формат"""
        try:
            if not filename:
                filename = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # Здесь будет интеграция с openpyxl или xlsxwriter
            # Пока возвращаем CSV как заглушку
            csv_data = await self.export_to_csv(data, filename.replace('.xlsx', '.csv'))
            
            return {
                "content": csv_data["content"],
                "filename": filename,
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": csv_data["size"]
            }
            
        except Exception as e:
            logger.error(f"Ошибка экспорта в Excel: {e}")
            raise

    async def export_to_zip(
        self, 
        data: Dict[str, Any],
        include_all_formats: bool = True,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Экспорт данных в ZIP архив"""
        try:
            if not filename:
                filename = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            
            zip_buffer = BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # JSON версия
                json_data = await self.export_to_json(data)
                zip_file.writestr("analytics_report.json", json_data["content"])
                
                # CSV версия
                csv_data = await self.export_to_csv(data)
                zip_file.writestr("analytics_report.csv", csv_data["content"])
                
                if include_all_formats:
                    # PDF версия
                    pdf_data = await self.export_to_pdf(data)
                    zip_file.writestr("analytics_report.pdf", pdf_data["content"])
                    
                    # Excel версия
                    excel_data = await self.export_to_excel(data)
                    zip_file.writestr("analytics_report.xlsx", excel_data["content"])
                
                # README файл
                readme_content = f"""
                АНАЛИТИЧЕСКИЙ ОТЧЕТ - ЭКСПОРТ
                
                Содержимое архива:
                - analytics_report.json - данные в JSON формате
                - analytics_report.csv - данные в CSV формате
                - analytics_report.pdf - отчет в PDF формате (если включен)
                - analytics_report.xlsx - отчет в Excel формате (если включен)
                
                Дата экспорта: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                Формат данных: Аналитические отчеты клиники
                """
                
                zip_file.writestr("README.txt", readme_content)
            
            zip_buffer.seek(0)
            zip_content = zip_buffer.getvalue()
            
            return {
                "content": zip_content,
                "filename": filename,
                "mime_type": "application/zip",
                "size": len(zip_content)
            }
            
        except Exception as e:
            logger.error(f"Ошибка экспорта в ZIP: {e}")
            raise

    def _write_dict_to_csv(self, writer, data, prefix=""):
        """Рекурсивно записывает словарь в CSV"""
        for key, value in data.items():
            if isinstance(value, dict):
                writer.writerow([f"{prefix}{key}", ""])
                self._write_dict_to_csv(writer, value, f"{prefix}{key}.")
            elif isinstance(value, list):
                writer.writerow([f"{prefix}{key}", f"List with {len(value)} items"])
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._write_dict_to_csv(writer, item, f"{prefix}{key}[{i}].")
                    else:
                        writer.writerow([f"{prefix}{key}[{i}]", str(item)])
            else:
                writer.writerow([f"{prefix}{key}", str(value)])

    def _generate_text_report(self, data: Dict[str, Any]) -> str:
        """Генерирует текстовый отчет для PDF"""
        report = f"""
        АНАЛИТИЧЕСКИЙ ОТЧЕТ КЛИНИКИ
        =============================
        
        Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        """
        
        # Добавляем основные метрики
        if "kpi_metrics" in data:
            kpi = data["kpi_metrics"]
            report += f"""
        КЛЮЧЕВЫЕ ПОКАЗАТЕЛИ ЭФФЕКТИВНОСТИ
        ===================================
        
        Общее количество записей: {kpi.get('total_appointments', 0)}
        Завершенные записи: {kpi.get('completed_appointments', 0)}
        Отмененные записи: {kpi.get('cancelled_appointments', 0)}
        Новые пациенты: {kpi.get('new_patients', 0)}
        Общий доход: {kpi.get('total_revenue', 0)} руб.
        Средний чек: {kpi.get('avg_revenue_per_visit', 0)} руб.
        Среднее время ожидания: {kpi.get('avg_wait_time_minutes', 0)} мин.
        Процент заполненности расписания: {kpi.get('schedule_utilization_percent', 0)}%
        Процент повторных визитов: {kpi.get('repeat_visit_rate_percent', 0)}%
        Процент отмен: {kpi.get('cancellation_rate_percent', 0)}%
        Процент завершения: {kpi.get('completion_rate_percent', 0)}%
        
        """
        
        # Добавляем показатели врачей
        if "doctor_performance" in data:
            doctors = data["doctor_performance"].get("doctor_performance", [])
            if doctors:
                report += f"""
        ПОКАЗАТЕЛИ ЭФФЕКТИВНОСТИ ВРАЧЕЙ
        ================================
        
        """
                for doctor in doctors[:5]:  # Топ 5 врачей
                    report += f"""
        {doctor.get('doctor_name', 'N/A')} ({doctor.get('specialty', 'N/A')})
        - Всего записей: {doctor.get('total_appointments', 0)}
        - Завершенных: {doctor.get('completed_appointments', 0)}
        - Процент завершения: {doctor.get('completion_rate_percent', 0)}%
        - Оценка эффективности: {doctor.get('performance_score', 0)}
        
        """
        
        # Добавляем аналитику доходов
        if "revenue_analytics" in data:
            revenue = data["revenue_analytics"]
            report += f"""
        АНАЛИТИКА ДОХОДОВ
        ==================
        
        Общий доход: {revenue.get('revenue_metrics', {}).get('total_revenue', 0)} руб.
        Средний дневной доход: {revenue.get('revenue_metrics', {}).get('avg_daily_revenue', 0)} руб.
        
        """
        
        report += f"""
        
        Отчет сгенерирован автоматически системой аналитики клиники.
        """
        
        return report

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
                "format": "csv",
                "name": "CSV",
                "description": "Табличные данные в CSV формате",
                "mime_type": "text/csv",
                "extension": ".csv"
            },
            {
                "format": "pdf",
                "name": "PDF",
                "description": "Отчет в PDF формате для печати",
                "mime_type": "application/pdf",
                "extension": ".pdf"
            },
            {
                "format": "excel",
                "name": "Excel",
                "description": "Табличные данные в Excel формате",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "extension": ".xlsx"
            },
            {
                "format": "zip",
                "name": "ZIP",
                "description": "Архив со всеми форматами",
                "mime_type": "application/zip",
                "extension": ".zip"
            }
        ]


# Глобальный экземпляр сервиса
analytics_export_service = AnalyticsExportService()

async def get_analytics_export_service() -> AnalyticsExportService:
    """Получить экземпляр сервиса экспорта аналитики"""
    return analytics_export_service
