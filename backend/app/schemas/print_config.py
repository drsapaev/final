"""
Pydantic схемы для системы печати
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ===================== КОНФИГУРАЦИЯ ПРИНТЕРОВ =====================

class PrinterConfigBase(BaseModel):
    name: str = Field(..., max_length=100, description="Уникальное имя принтера")
    display_name: str = Field(..., max_length=150, description="Отображаемое имя")
    printer_type: str = Field(..., max_length=50, description="ESC/POS, A5, A4")
    connection_type: str = Field("network", max_length=20, description="network, usb, serial")
    
    # Подключение
    ip_address: Optional[str] = Field(None, max_length=45, description="IP адрес для network")
    port: Optional[int] = Field(None, ge=1, le=65535, description="Порт для network")
    device_path: Optional[str] = Field(None, max_length=200, description="Путь устройства для USB/serial")
    
    # Настройки печати
    paper_width: Optional[int] = Field(None, ge=1, description="Ширина бумаги в мм")
    paper_height: Optional[int] = Field(None, ge=1, description="Высота бумаги в мм")
    margins: Optional[Dict[str, int]] = Field(None, description="Отступы: top, bottom, left, right")
    encoding: str = Field("utf-8", max_length=20, description="Кодировка")
    
    active: bool = True
    is_default: bool = False


class PrinterConfigCreate(PrinterConfigBase):
    pass


class PrinterConfigUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=150)
    printer_type: Optional[str] = Field(None, max_length=50)
    connection_type: Optional[str] = Field(None, max_length=20)
    ip_address: Optional[str] = Field(None, max_length=45)
    port: Optional[int] = Field(None, ge=1, le=65535)
    device_path: Optional[str] = Field(None, max_length=200)
    paper_width: Optional[int] = Field(None, ge=1)
    paper_height: Optional[int] = Field(None, ge=1)
    margins: Optional[Dict[str, int]] = None
    encoding: Optional[str] = Field(None, max_length=20)
    active: Optional[bool] = None
    is_default: Optional[bool] = None


class PrinterConfigOut(PrinterConfigBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ===================== ШАБЛОНЫ ПЕЧАТИ =====================

class PrintTemplateBase(BaseModel):
    printer_id: int
    name: str = Field(..., max_length=100, description="Уникальное имя шаблона")
    display_name: str = Field(..., max_length=150, description="Отображаемое имя")
    template_type: str = Field(..., max_length=50, description="ticket, prescription, memo, receipt")
    template_content: str = Field(..., description="Jinja2 шаблон")
    language: str = Field("ru", max_length=5, description="Язык: ru, uz, en")
    
    # Настройки форматирования
    font_size: int = Field(12, ge=6, le=72, description="Размер шрифта")
    line_spacing: int = Field(1, ge=1, le=5, description="Межстрочный интервал")
    char_per_line: Optional[int] = Field(None, ge=10, le=100, description="Символов в строке для ESC/POS")
    
    active: bool = True


class PrintTemplateCreate(PrintTemplateBase):
    pass


class PrintTemplateUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=150)
    template_content: Optional[str] = None
    language: Optional[str] = Field(None, max_length=5)
    font_size: Optional[int] = Field(None, ge=6, le=72)
    line_spacing: Optional[int] = Field(None, ge=1, le=5)
    char_per_line: Optional[int] = Field(None, ge=10, le=100)
    active: Optional[bool] = None


class PrintTemplateOut(PrintTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    printer: Optional[Dict[str, Any]] = None


# ===================== ЗАДАНИЯ ПЕЧАТИ =====================

class PrintJobBase(BaseModel):
    printer_id: int
    template_id: Optional[int] = None
    document_type: str = Field(..., max_length=50, description="ticket, prescription, memo, receipt")
    document_id: Optional[str] = Field(None, max_length=100, description="ID связанного документа")
    print_data: Optional[Dict[str, Any]] = Field(None, description="Данные для шаблона")


class PrintJobCreate(PrintJobBase):
    pass


class PrintJobOut(PrintJobBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ===================== ТЕСТИРОВАНИЕ ПЕЧАТИ =====================

class PrintTestRequest(BaseModel):
    """Запрос на тестирование принтера"""
    printer_id: int
    test_type: str = Field("test_page", description="test_page, sample_ticket, sample_prescription")
    test_data: Optional[Dict[str, Any]] = Field(None, description="Тестовые данные")


class PrintTestResult(BaseModel):
    """Результат тестирования принтера"""
    success: bool
    message: str
    printer_info: Dict[str, Any] = {}
    error_details: Optional[str] = None


# ===================== НАСТРОЙКИ СИСТЕМЫ ПЕЧАТИ =====================

class PrintSystemSettings(BaseModel):
    """Общие настройки системы печати"""
    enabled: bool = Field(True, description="Включена ли система печати")
    default_language: str = Field("ru", description="Язык по умолчанию для шаблонов")
    auto_print_tickets: bool = Field(True, description="Автоматически печатать талоны")
    auto_print_receipts: bool = Field(True, description="Автоматически печатать чеки")
    
    # Настройки качества
    print_quality: str = Field("normal", description="draft, normal, high")
    color_printing: bool = Field(False, description="Цветная печать")
    
    # Резервные копии
    backup_failed_jobs: bool = Field(True, description="Сохранять неудачные задания")
    retry_failed_jobs: bool = Field(True, description="Повторять неудачные задания")
    max_retries: int = Field(3, ge=1, le=10, description="Максимум попыток")


# ===================== СТАТИСТИКА ПЕЧАТИ =====================

class PrintStatsResponse(BaseModel):
    """Статистика системы печати"""
    total_jobs: int
    successful_jobs: int
    failed_jobs: int
    pending_jobs: int
    
    # По типам документов
    by_document_type: Dict[str, Dict[str, Any]]
    
    # По принтерам
    by_printer: Dict[str, Dict[str, Any]]
    
    # За период
    period_start: datetime
    period_end: datetime
