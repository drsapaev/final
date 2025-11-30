"""
Модели для системы скидок и льгот
"""

import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


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

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    discount_type = Column(Enum(DiscountType), nullable=False)
    value = Column(Float, nullable=False)  # Значение скидки (процент или сумма)
    min_amount = Column(Float, default=0)  # Минимальная сумма для применения
    max_discount = Column(Float)  # Максимальная сумма скидки

    # Условия применения
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    usage_limit = Column(Integer)  # Лимит использований
    usage_count = Column(Integer, default=0)  # Количество использований

    # Применимость
    applies_to_services = Column(Boolean, default=True)
    applies_to_appointments = Column(Boolean, default=True)
    applies_to_packages = Column(Boolean, default=True)

    # Комбинирование
    can_combine_with_others = Column(Boolean, default=False)
    priority = Column(Integer, default=0)  # Приоритет применения

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    discount_services = relationship("DiscountService", back_populates="discount")
    discount_applications = relationship(
        "DiscountApplication", back_populates="discount"
    )


class Benefit(Base):
    """Льготы"""

    __tablename__ = "benefits"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    benefit_type = Column(Enum(BenefitType), nullable=False)
    discount_percentage = Column(Float, nullable=False)  # Процент льготы
    max_discount_amount = Column(Float)  # Максимальная сумма льготы

    # Условия получения
    is_active = Column(Boolean, default=True)
    requires_document = Column(Boolean, default=True)  # Требует документы
    document_types = Column(Text)  # JSON список типов документов
    age_min = Column(Integer)  # Минимальный возраст
    age_max = Column(Integer)  # Максимальный возраст

    # Применимость
    applies_to_services = Column(Boolean, default=True)
    applies_to_appointments = Column(Boolean, default=True)

    # Лимиты
    monthly_limit = Column(Float)  # Месячный лимит льготы
    yearly_limit = Column(Float)  # Годовой лимит льготы

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    patient_benefits = relationship("PatientBenefit", back_populates="benefit")
    benefit_applications = relationship("BenefitApplication", back_populates="benefit")


class DiscountService(Base):
    """Связь скидок с услугами"""

    __tablename__ = "discount_services"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    discount_id = Column(Integer, ForeignKey("discounts.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    # Связи
    discount = relationship("Discount", back_populates="discount_services")
    service = relationship("Service")


class PatientBenefit(Base):
    """Льготы пациентов"""

    __tablename__ = "patient_benefits"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    benefit_id = Column(Integer, ForeignKey("benefits.id"), nullable=False)

    # Статус льготы
    is_active = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)
    verification_date = Column(DateTime)
    verification_notes = Column(Text)

    # Документы
    document_number = Column(String(100))
    document_issued_date = Column(DateTime)
    document_expiry_date = Column(DateTime)

    # Использование
    monthly_used_amount = Column(Float, default=0)
    yearly_used_amount = Column(Float, default=0)
    last_used_date = Column(DateTime)

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    verified_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    patient = relationship("Patient")
    benefit = relationship("Benefit", back_populates="patient_benefits")
    creator = relationship("User", foreign_keys=[created_by])
    verifier = relationship("User", foreign_keys=[verified_by])


class DiscountApplication(Base):
    """Применение скидок"""

    __tablename__ = "discount_applications"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    discount_id = Column(Integer, ForeignKey("discounts.id"), nullable=False)

    # Связанные объекты
    appointment_id = Column(Integer)  # ForeignKey("appointments.id") - убираем пока
    visit_id = Column(Integer)  # ForeignKey("visits.id") - убираем пока
    invoice_id = Column(Integer)  # ForeignKey("invoices.id") - убираем пока

    # Расчеты
    original_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, nullable=False)
    final_amount = Column(Float, nullable=False)

    # Метаданные
    applied_at = Column(DateTime, default=func.now())
    applied_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)

    # Связи
    discount = relationship("Discount", back_populates="discount_applications")
    # appointment = relationship("Appointment")  # убираем пока
    # visit = relationship("Visit")  # убираем пока
    applier = relationship("User", foreign_keys=[applied_by])


class BenefitApplication(Base):
    """Применение льгот"""

    __tablename__ = "benefit_applications"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    patient_benefit_id = Column(
        Integer, ForeignKey("patient_benefits.id"), nullable=False
    )
    benefit_id = Column(Integer, ForeignKey("benefits.id"), nullable=False)

    # Связанные объекты
    appointment_id = Column(Integer)  # ForeignKey("appointments.id") - убираем пока
    visit_id = Column(Integer)  # ForeignKey("visits.id") - убираем пока
    invoice_id = Column(Integer)  # ForeignKey("invoices.id") - убираем пока

    # Расчеты
    original_amount = Column(Float, nullable=False)
    benefit_amount = Column(Float, nullable=False)
    final_amount = Column(Float, nullable=False)

    # Метаданные
    applied_at = Column(DateTime, default=func.now())
    applied_by = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)

    # Связи
    patient_benefit = relationship("PatientBenefit")
    benefit = relationship("Benefit", back_populates="benefit_applications")
    # appointment = relationship("Appointment")  # убираем пока
    # visit = relationship("Visit")  # убираем пока
    applier = relationship("User", foreign_keys=[applied_by])


class LoyaltyProgram(Base):
    """Программа лояльности"""

    __tablename__ = "loyalty_programs"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # Настройки начисления баллов
    points_per_ruble = Column(Float, default=1.0)  # Баллов за рубль
    min_purchase_for_points = Column(
        Float, default=0
    )  # Минимальная покупка для начисления

    # Настройки списания баллов
    ruble_per_point = Column(Float, default=1.0)  # Рублей за балл
    min_points_to_redeem = Column(Integer, default=100)  # Минимум баллов для списания
    max_points_per_purchase = Column(Integer)  # Максимум баллов за покупку

    # Статус
    is_active = Column(Boolean, default=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    patient_loyalty = relationship("PatientLoyalty", back_populates="program")


class PatientLoyalty(Base):
    """Баллы лояльности пациентов"""

    __tablename__ = "patient_loyalty"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("loyalty_programs.id"), nullable=False)

    # Баллы
    total_points_earned = Column(Integer, default=0)
    total_points_redeemed = Column(Integer, default=0)
    current_balance = Column(Integer, default=0)

    # Статистика
    total_purchases = Column(Integer, default=0)
    total_amount_spent = Column(Float, default=0)
    last_activity_date = Column(DateTime)

    # Статус
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=func.now())

    # Связи
    patient = relationship("Patient")
    program = relationship("LoyaltyProgram", back_populates="patient_loyalty")
    point_transactions = relationship(
        "LoyaltyPointTransaction", back_populates="patient_loyalty"
    )


class LoyaltyPointTransaction(Base):
    """Транзакции баллов лояльности"""

    __tablename__ = "loyalty_point_transactions"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    patient_loyalty_id = Column(
        Integer, ForeignKey("patient_loyalty.id"), nullable=False
    )

    # Тип транзакции
    transaction_type = Column(
        String(50), nullable=False
    )  # earned, redeemed, expired, bonus
    points = Column(
        Integer, nullable=False
    )  # Положительное для начисления, отрицательное для списания

    # Связанные объекты
    appointment_id = Column(Integer)  # ForeignKey("appointments.id") - убираем пока
    visit_id = Column(Integer)  # ForeignKey("visits.id") - убираем пока
    invoice_id = Column(Integer)  # ForeignKey("invoices.id") - убираем пока

    # Детали
    description = Column(Text)
    amount_related = Column(Float)  # Сумма, связанная с транзакцией

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    patient_loyalty = relationship(
        "PatientLoyalty", back_populates="point_transactions"
    )
    # appointment = relationship("Appointment")  # убираем пока
    # visit = relationship("Visit")  # убираем пока
    creator = relationship("User", foreign_keys=[created_by])
