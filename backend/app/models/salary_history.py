"""
Salary History Model
Модель для хранения истории изменений зарплат сотрудников
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Numeric,
    Boolean,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from decimal import Decimal

from app.db.base_class import Base


class SalaryHistory(Base):
    """История изменений зарплаты сотрудника"""
    
    __tablename__ = "salary_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связь с пользователем (сотрудником)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Зарплата
    old_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    new_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    # Валюта
    currency: Mapped[str] = mapped_column(String(3), default="UZS")  # UZS, USD, etc.
    
    # Тип изменения
    change_type: Mapped[str] = mapped_column(String(50), default="adjustment")
    # adjustment - корректировка
    # promotion - повышение
    # annual_review - годовой пересмотр
    # bonus_increase - увеличение с бонусом
    # demotion - понижение
    # other - прочее
    
    # Процент изменения
    change_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    
    # Причина изменения
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Дата вступления в силу
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Кто изменил
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # Подтверждение
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="salary_history")
    changed_by = relationship("User", foreign_keys=[changed_by_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_id])
    
    def __repr__(self):
        return f"<SalaryHistory(id={self.id}, user_id={self.user_id}, {self.old_salary}->{self.new_salary})>"
    
    @property
    def change_amount(self) -> Decimal:
        """Сумма изменения"""
        if self.old_salary is None:
            return self.new_salary
        return self.new_salary - self.old_salary
    
    @property
    def is_increase(self) -> bool:
        """Является ли изменение повышением"""
        if self.old_salary is None:
            return True
        return self.new_salary > self.old_salary


class SalaryPayment(Base):
    """Записи о выплатах зарплаты"""
    
    __tablename__ = "salary_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Период
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Суммы
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    bonuses: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    taxes: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    
    # Статус выплаты
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending - ожидает
    # approved - одобрено
    # paid - выплачено
    # cancelled - отменено
    
    # Дата выплаты
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Комментарии
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User", backref="salary_payments")
    
    def __repr__(self):
        return f"<SalaryPayment(id={self.id}, user_id={self.user_id}, amount={self.net_amount})>"
