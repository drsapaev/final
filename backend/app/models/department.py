"""
Department model for managing clinic departments/tabs
"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Department(Base):
    """
    Модель отделения клиники

    Представляет вкладку/отделение в панели регистратора:
    - cardio (Кардиология)
    - echokg (ЭКГ)
    - derma (Дерматология)
    - dental (Стоматология)
    - lab (Лаборатория)
    - procedures (Процедуры)
    """
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Уникальный ключ отделения (cardio, echokg, derma, dental, lab, procedures)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    # Название отделения (русский)
    name_ru: Mapped[str] = mapped_column(String(200), nullable=False)

    # Название отделения (узбекский)
    name_uz: Mapped[str] = mapped_column(String(200), nullable=True)

    # Иконка (lucide-react icon name)
    icon: Mapped[str] = mapped_column(String(50), nullable=True, default="folder")

    # Цвет для UI
    color: Mapped[str] = mapped_column(String(50), nullable=True)

    # Градиент для UI
    gradient: Mapped[str] = mapped_column(Text, nullable=True)

    # Порядок отображения
    display_order: Mapped[int] = mapped_column(Integer, default=999)

    # Активность отделения
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Описание
    description: Mapped[str] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<Department(key='{self.key}', name_ru='{self.name_ru}', active={self.active})>"
