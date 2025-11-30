"""
Модели для конфигурации системы печати
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class PrinterConfig(Base):
    """Конфигурация принтеров"""

    __tablename__ = "printer_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String(100), unique=True, nullable=False
    )  # ticket_printer, prescription_printer
    display_name = Column(String(150), nullable=False)  # "Принтер талонов"
    printer_type = Column(String(50), nullable=False)  # ESC/POS, A5, A4

    # Подключение
    connection_type = Column(
        String(20), nullable=False, default="network"
    )  # network, usb, serial
    ip_address = Column(String(45), nullable=True)  # Для network
    port = Column(Integer, nullable=True)  # Для network
    device_path = Column(String(200), nullable=True)  # Для USB/serial

    # Настройки печати
    paper_width = Column(Integer, nullable=True)  # Ширина бумаги в мм
    paper_height = Column(Integer, nullable=True)  # Высота бумаги в мм
    margins = Column(
        JSON, nullable=True
    )  # {"top": 5, "bottom": 5, "left": 5, "right": 5}
    encoding = Column(String(20), default="utf-8", nullable=False)

    active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    templates = relationship("PrintTemplate", back_populates="printer")


class PrintTemplate(Base):
    """Шаблоны для печати"""

    __tablename__ = "print_templates"

    id = Column(Integer, primary_key=True, index=True)
    printer_id = Column(Integer, ForeignKey("printer_configs.id"), nullable=False)
    name = Column(String(100), nullable=False)  # ticket_template, prescription_template
    display_name = Column(String(150), nullable=False)  # "Шаблон талона"
    template_type = Column(
        String(50), nullable=False
    )  # ticket, prescription, memo, receipt

    # Шаблон (Jinja2)
    template_content = Column(Text, nullable=False)

    # Локализация
    language = Column(String(5), default="ru", nullable=False)  # ru, uz, en

    # Настройки форматирования
    font_size = Column(Integer, default=12, nullable=False)
    line_spacing = Column(Integer, default=1, nullable=False)
    char_per_line = Column(Integer, nullable=True)  # Для ESC/POS

    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    printer = relationship("PrinterConfig", back_populates="templates")


class PrintJob(Base):
    """Задания печати (лог)"""

    __tablename__ = "print_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    printer_id = Column(Integer, ForeignKey("printer_configs.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("print_templates.id"), nullable=True)

    # Тип документа
    document_type = Column(
        String(50), nullable=False
    )  # ticket, prescription, memo, receipt
    document_id = Column(String(100), nullable=True)  # ID визита/платежа и т.д.

    # Статус
    status = Column(
        String(20), default="pending", nullable=False
    )  # pending, printing, completed, failed
    error_message = Column(Text, nullable=True)

    # Данные для печати
    print_data = Column(JSON, nullable=True)  # Данные переданные в шаблон

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    printer = relationship("PrinterConfig", foreign_keys=[printer_id])
    template = relationship("PrintTemplate", foreign_keys=[template_id])
