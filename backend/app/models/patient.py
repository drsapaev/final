from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, name="gender"
    )  # M|F|X

    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    doc_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    doc_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Связь с пользователем
    user: Mapped[Optional["User"]] = relationship("User", back_populates="patient")

    def short_name(self) -> str:
        """
        Возвращает короткое имя пациента в формате "Фамилия Имя [Отчество]".
        Гарантирует, что всегда возвращается непустая строка.
        """
        # ✅ ЗАЩИТА: Проверяем, что поля не пустые
        last_name = (self.last_name or "").strip()
        first_name = (self.first_name or "").strip()
        middle_name = (self.middle_name or "").strip() if self.middle_name else ""
        
        # Если оба поля пустые - это ошибка данных, но возвращаем fallback
        if not last_name and not first_name:
            return f"Пациент ID={self.id}" if self.id else "Неизвестный пациент"
        
        # Если одно из полей пустое - используем другое для обоих
        if not last_name and first_name:
            last_name = first_name
        elif last_name and not first_name:
            first_name = last_name
        
        # Формируем имя
        mid = f" {middle_name}" if middle_name else ""
        result = f"{last_name} {first_name}{mid}".strip()
        
        # Финальная проверка - если все еще пустое (не должно произойти)
        return result if result else f"Пациент ID={self.id}" if self.id else "Неизвестный пациент"
