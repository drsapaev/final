"""
Модели для конфигурации системы печати
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class PrinterConfig(Base):
    """Конфигурация принтеров"""

    __tablename__ = "printer_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )  # ticket_printer, prescription_printer
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)  # "Принтер талонов"
    printer_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ESC/POS, A5, A4

    # Подключение
    connection_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="network"
    )  # network, usb, serial
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # Для network
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Для network
    device_path: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Для USB/serial

    # Настройки печати
    paper_width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Ширина бумаги в мм
    paper_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Высота бумаги в мм
    margins: Mapped[Optional[Dict[str, int]]] = mapped_column(
        JSON, nullable=True
    )  # {"top": 5, "bottom": 5, "left": 5, "right": 5}
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8", nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    templates: Mapped[List["PrintTemplate"]] = relationship(
        "PrintTemplate", back_populates="printer"
    )


class PrintTemplate(Base):
    """Шаблоны для печати"""

    __tablename__ = "print_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    printer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("printer_configs.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # ticket_template, prescription_template
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)  # "Шаблон талона"
    template_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ticket, prescription, memo, receipt

    # Шаблон (Jinja2)
    template_content: Mapped[str] = mapped_column(Text, nullable=False)

    # Локализация
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)  # ru, uz, en

    # Настройки форматирования
    font_size: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    line_spacing: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    char_per_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Для ESC/POS

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    printer: Mapped["PrinterConfig"] = relationship("PrinterConfig", back_populates="templates")


class PrintJob(Base):
    """Задания печати (лог)"""

    __tablename__ = "print_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    printer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("printer_configs.id"), nullable=False
    )
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("print_templates.id"), nullable=True
    )

    # Тип документа
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ticket, prescription, memo, receipt
    document_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # ID визита/платежа и т.д.

    # Статус
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, printing, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Данные для печати
    print_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # Данные переданные в шаблон

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    printer: Mapped["PrinterConfig"] = relationship("PrinterConfig", foreign_keys=[printer_id])
    template: Mapped[Optional["PrintTemplate"]] = relationship(
        "PrintTemplate", foreign_keys=[template_id]
    )
