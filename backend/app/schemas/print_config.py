"""
Pydantic схемы для системы печати
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ===================== ПРИНТЕРЫ =====================


class PrinterConfigBase(BaseModel):
    name: str = Field(..., description="Уникальное имя принтера")
    display_name: str = Field(..., description="Отображаемое имя")
    printer_type: str = Field(..., description="Тип принтера: ESC/POS, A4, A5")
    connection_type: str = Field(default="network", description="Тип подключения")
    ip_address: Optional[str] = Field(
        None, description="IP адрес для сетевого подключения"
    )
    port: Optional[int] = Field(None, description="Порт для сетевого подключения")
    device_path: Optional[str] = Field(
        None, description="Путь к устройству для USB/Serial"
    )
    paper_width: Optional[int] = Field(None, description="Ширина бумаги в мм")
    paper_height: Optional[int] = Field(None, description="Высота бумаги в мм")
    margins: Optional[Dict[str, int]] = Field(None, description="Отступы")
    encoding: str = Field(default="utf-8", description="Кодировка")
    active: bool = Field(default=True, description="Активен ли принтер")
    is_default: bool = Field(default=False, description="Принтер по умолчанию")


class PrinterConfigCreate(PrinterConfigBase):
    pass


class PrinterConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    printer_type: Optional[str] = None
    connection_type: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    device_path: Optional[str] = None
    paper_width: Optional[int] = None
    paper_height: Optional[int] = None
    margins: Optional[Dict[str, int]] = None
    encoding: Optional[str] = None
    active: Optional[bool] = None
    is_default: Optional[bool] = None


class PrinterConfigOut(PrinterConfigBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== ШАБЛОНЫ =====================


class PrintTemplateBase(BaseModel):
    printer_id: int = Field(..., description="ID принтера")
    name: str = Field(..., description="Имя шаблона")
    display_name: str = Field(..., description="Отображаемое имя")
    template_type: str = Field(..., description="Тип шаблона")
    template_content: str = Field(..., description="Содержимое шаблона Jinja2")
    language: str = Field(default="ru", description="Язык шаблона")
    font_size: int = Field(default=12, description="Размер шрифта")
    line_spacing: int = Field(default=1, description="Межстрочный интервал")
    char_per_line: Optional[int] = Field(
        None, description="Символов в строке для ESC/POS"
    )
    active: bool = Field(default=True, description="Активен ли шаблон")


class PrintTemplateCreate(PrintTemplateBase):
    pass


class PrintTemplateUpdate(BaseModel):
    printer_id: Optional[int] = None
    name: Optional[str] = None
    display_name: Optional[str] = None
    template_type: Optional[str] = None
    template_content: Optional[str] = None
    language: Optional[str] = None
    font_size: Optional[int] = None
    line_spacing: Optional[int] = None
    char_per_line: Optional[int] = None
    active: Optional[bool] = None


class PrintTemplateOut(PrintTemplateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== ЗАДАНИЯ ПЕЧАТИ =====================


class PrintJobBase(BaseModel):
    user_id: Optional[int] = None
    printer_id: int = Field(..., description="ID принтера")
    template_id: Optional[int] = Field(None, description="ID шаблона")
    document_type: str = Field(..., description="Тип документа")
    document_id: Optional[str] = Field(None, description="ID документа")
    status: str = Field(default="pending", description="Статус задания")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке")
    print_data: Optional[Dict[str, Any]] = Field(None, description="Данные для печати")


class PrintJobCreate(PrintJobBase):
    pass


class PrintJobUpdate(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None


class PrintJobOut(PrintJobBase):
    id: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== API СХЕМЫ =====================


class PrintRequest(BaseModel):
    """Базовая схема для запросов печати"""

    printer_name: Optional[str] = Field(None, description="Имя принтера")
    document_data: Dict[str, Any] = Field(..., description="Данные документа")


class PrintTicketRequest(BaseModel):
    """Схема для печати талона"""

    clinic_name: Optional[str] = None
    queue_number: str = Field(..., description="Номер в очереди")
    doctor_name: str = Field(..., description="Имя врача")
    specialty_name: str = Field(..., description="Специальность")
    cabinet: Optional[str] = None
    patient_name: Optional[str] = None
    source: str = Field(default="desk", description="Источник записи")
    time_window: Optional[str] = None
    printer_name: Optional[str] = None


class PrintPrescriptionRequest(BaseModel):
    """Схема для печати рецепта"""

    prescription: Dict[str, Any] = Field(..., description="Данные рецепта")
    patient: Dict[str, Any] = Field(..., description="Данные пациента")
    clinic: Optional[Dict[str, Any]] = None
    printer_name: Optional[str] = None


class PrintCertificateRequest(BaseModel):
    """Схема для печати справки"""

    certificate: Dict[str, Any] = Field(..., description="Данные справки")
    patient: Dict[str, Any] = Field(..., description="Данные пациента")
    visit: Optional[Dict[str, Any]] = None
    clinic: Optional[Dict[str, Any]] = None
    printer_name: Optional[str] = None


class PrintReceiptRequest(BaseModel):
    """Схема для печати чека"""

    payment: Dict[str, Any] = Field(..., description="Данные платежа")
    patient: Dict[str, Any] = Field(..., description="Данные пациента")
    services: List[Dict[str, Any]] = Field(..., description="Список услуг")
    clinic: Optional[Dict[str, Any]] = None
    printer_name: Optional[str] = None


class PrintLabResultsRequest(BaseModel):
    """Схема для печати результатов анализов"""

    lab_order: Dict[str, Any] = Field(..., description="Данные заказа")
    lab_results: List[Dict[str, Any]] = Field(..., description="Результаты анализов")
    patient: Dict[str, Any] = Field(..., description="Данные пациента")
    clinic: Optional[Dict[str, Any]] = None
    printer_name: Optional[str] = None


class PrintResponse(BaseModel):
    """Схема ответа печати"""

    success: bool = Field(..., description="Успешность операции")
    job_id: Optional[int] = Field(None, description="ID задания печати")
    message: str = Field(..., description="Сообщение")
    printer: Optional[str] = Field(None, description="Имя принтера")
    error: Optional[str] = Field(None, description="Ошибка")
    result: Optional[Dict[str, Any]] = Field(None, description="Дополнительные данные")


class QuickTicketRequest(BaseModel):
    """Схема для быстрой печати талона"""

    queue_number: str = Field(..., description="Номер в очереди")
    doctor_name: str = Field(..., description="Имя врача")
    specialty: str = Field(..., description="Специальность")
    patient_name: Optional[str] = None
    cabinet: Optional[str] = None
    source: str = Field(default="desk", description="Источник записи")


class QuickReceiptRequest(BaseModel):
    """Схема для быстрой печати чека"""

    patient_name: str = Field(..., description="ФИО пациента")
    services: List[Dict[str, Any]] = Field(..., description="Список услуг")
    total_amount: float = Field(..., description="Общая сумма")
    payment_method: str = Field(..., description="Способ оплаты")


class PrinterStatusResponse(BaseModel):
    """Схема ответа статуса принтера"""

    printer_name: str
    timestamp: str
    status: str
    message: str


class PrintersListResponse(BaseModel):
    """Схема списка принтеров"""

    printers: List[Dict[str, Any]]
    total: int


class TestPrintResponse(BaseModel):
    """Схема ответа тестовой печати"""

    printer_name: str
    test_time: str
    success: bool
    message: str
