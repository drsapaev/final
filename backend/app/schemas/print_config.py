"""
Pydantic схемы для системы печати
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ===================== ПРИНТЕРЫ =====================


class PrinterConfigBase(BaseModel):
    name: str = Field(..., description="Уникальное имя принтера")
    display_name: str = Field(..., description="Отображаемое имя")
    printer_type: str = Field(..., description="Тип принтера: ESC/POS, A4, A5")
    connection_type: str = Field(default="network", description="Тип подключения")
    ip_address: str | None = Field(
        None, description="IP адрес для сетевого подключения"
    )
    port: int | None = Field(None, description="Порт для сетевого подключения")
    device_path: str | None = Field(
        None, description="Путь к устройству для USB/Serial"
    )
    paper_width: int | None = Field(None, description="Ширина бумаги в мм")
    paper_height: int | None = Field(None, description="Высота бумаги в мм")
    margins: dict[str, int] | None = Field(None, description="Отступы")
    encoding: str = Field(default="utf-8", description="Кодировка")
    active: bool = Field(default=True, description="Активен ли принтер")
    is_default: bool = Field(default=False, description="Принтер по умолчанию")


class PrinterConfigCreate(PrinterConfigBase):
    pass


class PrinterConfigUpdate(BaseModel):
    display_name: str | None = None
    printer_type: str | None = None
    connection_type: str | None = None
    ip_address: str | None = None
    port: int | None = None
    device_path: str | None = None
    paper_width: int | None = None
    paper_height: int | None = None
    margins: dict[str, int] | None = None
    encoding: str | None = None
    active: bool | None = None
    is_default: bool | None = None


class PrinterConfigOut(PrinterConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


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
    char_per_line: int | None = Field(
        None, description="Символов в строке для ESC/POS"
    )
    active: bool = Field(default=True, description="Активен ли шаблон")


class PrintTemplateCreate(PrintTemplateBase):
    pass


class PrintTemplateUpdate(BaseModel):
    printer_id: int | None = None
    name: str | None = None
    display_name: str | None = None
    template_type: str | None = None
    template_content: str | None = None
    language: str | None = None
    font_size: int | None = None
    line_spacing: int | None = None
    char_per_line: int | None = None
    active: bool | None = None


class PrintTemplateOut(PrintTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ===================== ЗАДАНИЯ ПЕЧАТИ =====================


class PrintJobBase(BaseModel):
    user_id: int | None = None
    printer_id: int = Field(..., description="ID принтера")
    template_id: int | None = Field(None, description="ID шаблона")
    document_type: str = Field(..., description="Тип документа")
    document_id: str | None = Field(None, description="ID документа")
    status: str = Field(default="pending", description="Статус задания")
    error_message: str | None = Field(None, description="Сообщение об ошибке")
    print_data: dict[str, Any] | None = Field(None, description="Данные для печати")


class PrintJobCreate(PrintJobBase):
    pass


class PrintJobUpdate(BaseModel):
    status: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None


class PrintJobOut(PrintJobBase):
    id: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ===================== API СХЕМЫ =====================


class PrintRequest(BaseModel):
    """Базовая схема для запросов печати"""

    printer_name: str | None = Field(None, description="Имя принтера")
    document_data: dict[str, Any] = Field(..., description="Данные документа")


class PrintTicketRequest(BaseModel):
    """Схема для печати талона"""

    clinic_name: str | None = None
    queue_number: str = Field(..., description="Номер в очереди")
    doctor_name: str = Field(..., description="Имя врача")
    specialty_name: str = Field(..., description="Специальность")
    cabinet: str | None = None
    patient_name: str | None = None
    source: str = Field(default="desk", description="Источник записи")
    time_window: str | None = None
    printer_name: str | None = None


class PrintPrescriptionRequest(BaseModel):
    """Схема для печати рецепта"""

    prescription: dict[str, Any] = Field(..., description="Данные рецепта")
    patient: dict[str, Any] = Field(..., description="Данные пациента")
    clinic: dict[str, Any] | None = None
    printer_name: str | None = None


class PrintCertificateRequest(BaseModel):
    """Схема для печати справки"""

    certificate: dict[str, Any] = Field(..., description="Данные справки")
    patient: dict[str, Any] = Field(..., description="Данные пациента")
    visit: dict[str, Any] | None = None
    clinic: dict[str, Any] | None = None
    printer_name: str | None = None


class PrintReceiptRequest(BaseModel):
    """Схема для печати чека"""

    payment: dict[str, Any] = Field(..., description="Данные платежа")
    patient: dict[str, Any] = Field(..., description="Данные пациента")
    services: list[dict[str, Any]] = Field(..., description="Список услуг")
    clinic: dict[str, Any] | None = None
    printer_name: str | None = None


class PrintLabResultsRequest(BaseModel):
    """Схема для печати результатов анализов"""

    lab_order: dict[str, Any] = Field(..., description="Данные заказа")
    lab_results: list[dict[str, Any]] = Field(..., description="Результаты анализов")
    patient: dict[str, Any] = Field(..., description="Данные пациента")
    clinic: dict[str, Any] | None = None
    printer_name: str | None = None


class PrintResponse(BaseModel):
    """Схема ответа печати"""

    success: bool = Field(..., description="Успешность операции")
    job_id: int | None = Field(None, description="ID задания печати")
    message: str = Field(..., description="Сообщение")
    printer: str | None = Field(None, description="Имя принтера")
    error: str | None = Field(None, description="Ошибка")
    result: dict[str, Any] | None = Field(None, description="Дополнительные данные")


class QuickTicketRequest(BaseModel):
    """Схема для быстрой печати талона"""

    queue_number: str = Field(..., description="Номер в очереди")
    doctor_name: str = Field(..., description="Имя врача")
    specialty: str = Field(..., description="Специальность")
    patient_name: str | None = None
    cabinet: str | None = None
    source: str = Field(default="desk", description="Источник записи")


class QuickReceiptRequest(BaseModel):
    """Схема для быстрой печати чека"""

    patient_name: str = Field(..., description="ФИО пациента")
    services: list[dict[str, Any]] = Field(..., description="Список услуг")
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

    printers: list[dict[str, Any]]
    total: int


class TestPrintResponse(BaseModel):
    """Схема ответа тестовой печати"""

    printer_name: str
    test_time: str
    success: bool
    message: str
