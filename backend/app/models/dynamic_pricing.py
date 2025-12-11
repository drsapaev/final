"""
Модели для динамического ценообразования и пакетных услуг
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.models.appointment import Appointment
    from app.models.service import Service


class PricingRuleType(str, enum.Enum):
    """Типы правил ценообразования"""

    TIME_BASED = "time_based"  # По времени (утро/день/вечер)
    VOLUME_BASED = "volume_based"  # По объему (количество услуг)
    SEASONAL = "seasonal"  # Сезонные
    LOYALTY = "loyalty"  # Программа лояльности
    PACKAGE = "package"  # Пакетные предложения
    DYNAMIC = "dynamic"  # Динамические (на основе загруженности)


class DiscountType(str, enum.Enum):
    """Типы скидок"""

    PERCENTAGE = "percentage"  # Процентная скидка
    FIXED_AMOUNT = "fixed_amount"  # Фиксированная сумма
    BUY_X_GET_Y = "buy_x_get_y"  # Купи X получи Y
    TIERED = "tiered"  # Ступенчатая скидка


class PricingRule(Base):
    """Правила ценообразования"""

    __tablename__ = "pricing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    rule_type: Mapped[PricingRuleType] = mapped_column(Enum(PricingRuleType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Условия применения
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    start_time: Mapped[Optional[str]] = mapped_column(String(8))  # HH:MM:SS
    end_time: Mapped[Optional[str]] = mapped_column(String(8))  # HH:MM:SS
    days_of_week: Mapped[Optional[str]] = mapped_column(String(20))  # 1,2,3,4,5,6,7 (пн-вс)

    # Параметры скидки
    discount_type: Mapped[DiscountType] = mapped_column(Enum(DiscountType), nullable=False)
    discount_value: Mapped[float] = mapped_column(Float, nullable=False)  # Процент или сумма
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    max_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    min_amount: Mapped[Optional[float]] = mapped_column(Float)  # Минимальная сумма заказа

    # Дополнительные параметры
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Приоритет применения
    max_uses: Mapped[Optional[int]] = mapped_column(Integer)  # Максимальное количество использований
    current_uses: Mapped[int] = mapped_column(Integer, default=0)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    rule_services: Mapped[List["PricingRuleService"]] = relationship(
        "PricingRuleService", back_populates="rule"
    )
    rule_packages: Mapped[List["ServicePackage"]] = relationship(
        "ServicePackage", back_populates="pricing_rule"
    )


class PricingRuleService(Base):
    """Связь правил ценообразования с услугами"""

    __tablename__ = "pricing_rule_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("pricing_rules.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)

    # Специфичные параметры для услуги
    custom_discount_value: Mapped[Optional[float]] = mapped_column(
        Float
    )  # Переопределение скидки для конкретной услуги
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)  # Исключить услугу из правила

    # Связи
    rule: Mapped["PricingRule"] = relationship("PricingRule", back_populates="rule_services")
    service: Mapped["Service"] = relationship("Service")


class ServicePackage(Base):
    """Пакеты услуг"""

    __tablename__ = "service_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Ценообразование
    package_price: Mapped[float] = mapped_column(Float, nullable=False)
    original_price: Mapped[Optional[float]] = mapped_column(Float)  # Сумма цен отдельных услуг
    savings_amount: Mapped[Optional[float]] = mapped_column(Float)  # Размер экономии
    savings_percentage: Mapped[Optional[float]] = mapped_column(Float)  # Процент экономии

    # Условия
    min_services: Mapped[int] = mapped_column(Integer, default=1)
    max_services: Mapped[Optional[int]] = mapped_column(Integer)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Ограничения
    max_purchases: Mapped[Optional[int]] = mapped_column(Integer)  # Максимальное количество покупок
    current_purchases: Mapped[int] = mapped_column(Integer, default=0)
    per_patient_limit: Mapped[Optional[int]] = mapped_column(Integer)  # Лимит на пациента

    # Связи с правилами ценообразования
    pricing_rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pricing_rules.id"))
    pricing_rule: Mapped[Optional["PricingRule"]] = relationship(
        "PricingRule", back_populates="rule_packages"
    )

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    package_services: Mapped[List["PackageService"]] = relationship(
        "PackageService", back_populates="package"
    )
    package_purchases: Mapped[List["PackagePurchase"]] = relationship(
        "PackagePurchase", back_populates="package"
    )


class PackageService(Base):
    """Услуги в пакете"""

    __tablename__ = "package_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("service_packages.id"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)

    # Параметры услуги в пакете
    quantity: Mapped[int] = mapped_column(Integer, default=1)  # Количество данной услуги в пакете
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)  # Обязательная услуга
    discount_percentage: Mapped[Optional[float]] = mapped_column(Float)  # Индивидуальная скидка на услугу

    # Связи
    package: Mapped["ServicePackage"] = relationship("ServicePackage", back_populates="package_services")
    service: Mapped["Service"] = relationship("Service")


class PackagePurchase(Base):
    """История покупок пакетов"""

    __tablename__ = "package_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("service_packages.id"), nullable=False
    )
    patient_id: Mapped[int] = mapped_column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("visits.id"))
    appointment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("appointments.id"))

    # Детали покупки
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    original_price: Mapped[float] = mapped_column(Float, nullable=False)
    savings_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Статус
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, used, expired, cancelled

    # Временные метки
    purchased_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Связи
    package: Mapped["ServicePackage"] = relationship("ServicePackage", back_populates="package_purchases")
    patient: Mapped["Patient"] = relationship("Patient")
    visit: Mapped[Optional["Visit"]] = relationship("Visit")
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment")


class DynamicPrice(Base):
    """Динамические цены на услуги"""

    __tablename__ = "dynamic_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)

    # Ценовые параметры
    base_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    min_price: Mapped[float] = mapped_column(Float, nullable=False)
    max_price: Mapped[float] = mapped_column(Float, nullable=False)

    # Факторы влияния на цену
    demand_factor: Mapped[float] = mapped_column(Float, default=1.0)  # Коэффициент спроса
    time_factor: Mapped[float] = mapped_column(Float, default=1.0)  # Временной коэффициент
    capacity_factor: Mapped[float] = mapped_column(Float, default=1.0)  # Коэффициент загруженности
    seasonal_factor: Mapped[float] = mapped_column(Float, default=1.0)  # Сезонный коэффициент

    # Статистика
    price_changes_count: Mapped[int] = mapped_column(Integer, default=0)
    last_price_change: Mapped[Optional[datetime]] = mapped_column(DateTime)
    avg_price_last_30d: Mapped[Optional[float]] = mapped_column(Float)

    # Временные метки
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Связи
    service: Mapped["Service"] = relationship("Service")


class PriceHistory(Base):
    """История изменений цен"""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)

    # Цены
    old_price: Mapped[float] = mapped_column(Float, nullable=False)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    price_type: Mapped[str] = mapped_column(String(50), default="base")  # base, dynamic, package

    # Причина изменения
    change_reason: Mapped[Optional[str]] = mapped_column(String(255))
    change_type: Mapped[Optional[str]] = mapped_column(String(50))  # manual, automatic, rule_based

    # Метаданные
    changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    changed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Связи
    service: Mapped["Service"] = relationship("Service")
    changed_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by])
