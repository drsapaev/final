"""
Модели для системы скидок и льгот
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient
    from app.models.service import Service


class DiscountType(str, enum.Enum):
    """Типы скидок"""

    PERCENTAGE = "percentage"  # Процентная скидка
    FIXED_AMOUNT = "fixed_amount"  # Фиксированная сумма
    BUY_X_GET_Y = "buy_x_get_y"  # Купи X получи Y
    LOYALTY_POINTS = "loyalty_points"  # Бонусные баллы
    SEASONAL = "seasonal"  # Сезонная скидка
    REFERRAL = "referral"  # Реферальная скидка


class BenefitType(str, enum.Enum):
    """Типы льгот"""

    VETERAN = "veteran"  # Ветеран
    DISABLED = "disabled"  # Инвалид
    PENSIONER = "pensioner"  # Пенсионер
    STUDENT = "student"  # Студент
    CHILD = "child"  # Ребенок
    LARGE_FAMILY = "large_family"  # Многодетная семья
    LOW_INCOME = "low_income"  # Малообеспеченная семья
    EMPLOYEE = "employee"  # Сотрудник клиники


class DiscountStatus(str, enum.Enum):
    """Статусы скидок"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    PENDING = "pending"
    SUSPENDED = "suspended"


class Discount(Base):
    """Скидки"""

    __tablename__ = "discounts"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)  # Значение скидки (процент или сумма)
    min_amount: Mapped[float] = mapped_column(Float, default=0)  # Минимальная сумма для применения
    max_discount: Mapped[Optional[float]] = mapped_column(Float)  # Максимальная сумма скидки

    # Условия применения
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    usage_limit: Mapped[Optional[int]] = mapped_column(Integer)  # Лимит использований
    usage_count: Mapped[int] = mapped_column(Integer, default=0)  # Количество использований

    # Применимость
    applies_to_services: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_appointments: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_packages: Mapped[bool] = mapped_column(Boolean, default=True)

    # Комбинирование
    can_combine_with_others: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Приоритет применения

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    discount_services: Mapped[List["DiscountService"]] = relationship(
        "DiscountService", back_populates="discount"
    )
    discount_applications: Mapped[List["DiscountApplication"]] = relationship(
        "DiscountApplication", back_populates="discount"
    )


class Benefit(Base):
    """Льготы"""

    __tablename__ = "benefits"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    benefit_type: Mapped[BenefitType] = mapped_column(Enum(BenefitType), nullable=False)
    discount_percentage: Mapped[float] = mapped_column(Float, nullable=False)  # Процент льготы
    max_discount_amount: Mapped[Optional[float]] = mapped_column(Float)  # Максимальная сумма льготы

    # Условия получения
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_document: Mapped[bool] = mapped_column(Boolean, default=True)  # Требует документы
    document_types: Mapped[Optional[str]] = mapped_column(Text)  # JSON список типов документов
    age_min: Mapped[Optional[int]] = mapped_column(Integer)  # Минимальный возраст
    age_max: Mapped[Optional[int]] = mapped_column(Integer)  # Максимальный возраст

    # Применимость
    applies_to_services: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_appointments: Mapped[bool] = mapped_column(Boolean, default=True)

    # Лимиты
    monthly_limit: Mapped[Optional[float]] = mapped_column(Float)  # Месячный лимит льготы
    yearly_limit: Mapped[Optional[float]] = mapped_column(Float)  # Годовой лимит льготы

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    patient_benefits: Mapped[List["PatientBenefit"]] = relationship(
        "PatientBenefit", back_populates="benefit"
    )
    benefit_applications: Mapped[List["BenefitApplication"]] = relationship(
        "BenefitApplication", back_populates="benefit"
    )


class DiscountService(Base):
    """Связь скидок с услугами"""

    __tablename__ = "discount_services"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    discount_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discounts.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )

    # Связи
    discount: Mapped["Discount"] = relationship("Discount", back_populates="discount_services")
    service: Mapped["Service"] = relationship("Service")


class PatientBenefit(Base):
    """Льготы пациентов"""

    __tablename__ = "patient_benefits"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    benefit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("benefits.id", ondelete="CASCADE"), nullable=False
    )

    # Статус льготы
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Документы
    document_number: Mapped[Optional[str]] = mapped_column(String(100))
    document_issued_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    document_expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Использование
    monthly_used_amount: Mapped[float] = mapped_column(Float, default=0)
    yearly_used_amount: Mapped[float] = mapped_column(Float, default=0)
    last_used_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    patient: Mapped["Patient"] = relationship("Patient")
    benefit: Mapped["Benefit"] = relationship("Benefit", back_populates="patient_benefits")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    verifier: Mapped[Optional["User"]] = relationship("User", foreign_keys=[verified_by])


class DiscountApplication(Base):
    """Применение скидок"""

    __tablename__ = "discount_applications"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    discount_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("discounts.id", ondelete="CASCADE"), nullable=False
    )

    # Связанные объекты
    appointment_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока
    visit_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока
    invoice_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока

    # Расчеты
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False)
    final_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Метаданные
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    applied_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Связи
    discount: Mapped["Discount"] = relationship("Discount", back_populates="discount_applications")
    applier: Mapped[Optional["User"]] = relationship("User", foreign_keys=[applied_by])


class BenefitApplication(Base):
    """Применение льгот"""

    __tablename__ = "benefit_applications"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_benefit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient_benefits.id", ondelete="CASCADE"), nullable=False
    )
    benefit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("benefits.id", ondelete="CASCADE"), nullable=False
    )

    # Связанные объекты
    appointment_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока
    visit_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока
    invoice_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока

    # Расчеты
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)
    benefit_amount: Mapped[float] = mapped_column(Float, nullable=False)
    final_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Метаданные
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    applied_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Связи
    patient_benefit: Mapped["PatientBenefit"] = relationship("PatientBenefit")
    benefit: Mapped["Benefit"] = relationship("Benefit", back_populates="benefit_applications")
    applier: Mapped[Optional["User"]] = relationship("User", foreign_keys=[applied_by])


class LoyaltyProgram(Base):
    """Программа лояльности"""

    __tablename__ = "loyalty_programs"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Настройки начисления баллов
    points_per_ruble: Mapped[float] = mapped_column(Float, default=1.0)  # Баллов за рубль
    min_purchase_for_points: Mapped[float] = mapped_column(
        Float, default=0
    )  # Минимальная покупка для начисления

    # Настройки списания баллов
    ruble_per_point: Mapped[float] = mapped_column(Float, default=1.0)  # Рублей за балл
    min_points_to_redeem: Mapped[int] = mapped_column(Integer, default=100)  # Минимум баллов для списания
    max_points_per_purchase: Mapped[Optional[int]] = mapped_column(Integer)  # Максимум баллов за покупку

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    patient_loyalty: Mapped[List["PatientLoyalty"]] = relationship(
        "PatientLoyalty", back_populates="program"
    )


class PatientLoyalty(Base):
    """Баллы лояльности пациентов"""

    __tablename__ = "patient_loyalty"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("loyalty_programs.id", ondelete="CASCADE"), nullable=False
    )

    # Баллы
    total_points_earned: Mapped[int] = mapped_column(Integer, default=0)
    total_points_redeemed: Mapped[int] = mapped_column(Integer, default=0)
    current_balance: Mapped[int] = mapped_column(Integer, default=0)

    # Статистика
    total_purchases: Mapped[int] = mapped_column(Integer, default=0)
    total_amount_spent: Mapped[float] = mapped_column(Float, default=0)
    last_activity_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())

    # Связи
    patient: Mapped["Patient"] = relationship("Patient")
    program: Mapped["LoyaltyProgram"] = relationship("LoyaltyProgram", back_populates="patient_loyalty")
    point_transactions: Mapped[List["LoyaltyPointTransaction"]] = relationship(
        "LoyaltyPointTransaction", back_populates="patient_loyalty"
    )


class LoyaltyPointTransaction(Base):
    """Транзакции баллов лояльности"""

    __tablename__ = "loyalty_point_transactions"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_loyalty_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient_loyalty.id", ondelete="CASCADE"), nullable=False
    )

    # Тип транзакции
    transaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # earned, redeemed, expired, bonus
    points: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Положительное для начисления, отрицательное для списания

    # Связанные объекты
    appointment_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока
    visit_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока
    invoice_id: Mapped[Optional[int]] = mapped_column(Integer)  # ForeignKey убран пока

    # Детали
    description: Mapped[Optional[str]] = mapped_column(Text)
    amount_related: Mapped[Optional[float]] = mapped_column(Float)  # Сумма, связанная с транзакцией

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    patient_loyalty: Mapped["PatientLoyalty"] = relationship(
        "PatientLoyalty", back_populates="point_transactions"
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
