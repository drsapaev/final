"""
Модели для динамического ценообразования и пакетных услуг
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
import enum


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

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    rule_type = Column(Enum(PricingRuleType), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Условия применения
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    start_time = Column(String(8))  # HH:MM:SS
    end_time = Column(String(8))  # HH:MM:SS
    days_of_week = Column(String(20))  # 1,2,3,4,5,6,7 (пн-вс)
    
    # Параметры скидки
    discount_type = Column(Enum(DiscountType), nullable=False)
    discount_value = Column(Float, nullable=False)  # Процент или сумма
    min_quantity = Column(Integer, default=1)
    max_quantity = Column(Integer)
    min_amount = Column(Float)  # Минимальная сумма заказа
    
    # Дополнительные параметры
    priority = Column(Integer, default=0)  # Приоритет применения
    max_uses = Column(Integer)  # Максимальное количество использований
    current_uses = Column(Integer, default=0)
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    rule_services = relationship("PricingRuleService", back_populates="rule")
    rule_packages = relationship("ServicePackage", back_populates="pricing_rule")


class PricingRuleService(Base):
    """Связь правил ценообразования с услугами"""
    __tablename__ = "pricing_rule_services"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("pricing_rules.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Специфичные параметры для услуги
    custom_discount_value = Column(Float)  # Переопределение скидки для конкретной услуги
    is_excluded = Column(Boolean, default=False)  # Исключить услугу из правила
    
    # Связи
    rule = relationship("PricingRule", back_populates="rule_services")
    service = relationship("Service")


class ServicePackage(Base):
    """Пакеты услуг"""
    __tablename__ = "service_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Ценообразование
    package_price = Column(Float, nullable=False)
    original_price = Column(Float)  # Сумма цен отдельных услуг
    savings_amount = Column(Float)  # Размер экономии
    savings_percentage = Column(Float)  # Процент экономии
    
    # Условия
    min_services = Column(Integer, default=1)
    max_services = Column(Integer)
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)
    
    # Ограничения
    max_purchases = Column(Integer)  # Максимальное количество покупок
    current_purchases = Column(Integer, default=0)
    per_patient_limit = Column(Integer)  # Лимит на пациента
    
    # Связи с правилами ценообразования
    pricing_rule_id = Column(Integer, ForeignKey("pricing_rules.id"))
    pricing_rule = relationship("PricingRule", back_populates="rule_packages")
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    package_services = relationship("PackageService", back_populates="package")
    package_purchases = relationship("PackagePurchase", back_populates="package")


class PackageService(Base):
    """Услуги в пакете"""
    __tablename__ = "package_services"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("service_packages.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Параметры услуги в пакете
    quantity = Column(Integer, default=1)  # Количество данной услуги в пакете
    is_required = Column(Boolean, default=True)  # Обязательная услуга
    discount_percentage = Column(Float)  # Индивидуальная скидка на услугу
    
    # Связи
    package = relationship("ServicePackage", back_populates="package_services")
    service = relationship("Service")


class PackagePurchase(Base):
    """История покупок пакетов"""
    __tablename__ = "package_purchases"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("service_packages.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    appointment_id = Column(Integer, ForeignKey("appointments.id"))
    
    # Детали покупки
    purchase_price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=False)
    savings_amount = Column(Float, nullable=False)
    
    # Статус
    status = Column(String(50), default="active")  # active, used, expired, cancelled
    
    # Временные метки
    purchased_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)
    used_at = Column(DateTime)
    
    # Связи
    package = relationship("ServicePackage", back_populates="package_purchases")
    patient = relationship("Patient")
    visit = relationship("Visit")
    appointment = relationship("Appointment")


class DynamicPrice(Base):
    """Динамические цены на услуги"""
    __tablename__ = "dynamic_prices"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Ценовые параметры
    base_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    
    # Факторы влияния на цену
    demand_factor = Column(Float, default=1.0)  # Коэффициент спроса
    time_factor = Column(Float, default=1.0)  # Временной коэффициент
    capacity_factor = Column(Float, default=1.0)  # Коэффициент загруженности
    seasonal_factor = Column(Float, default=1.0)  # Сезонный коэффициент
    
    # Статистика
    price_changes_count = Column(Integer, default=0)
    last_price_change = Column(DateTime)
    avg_price_last_30d = Column(Float)
    
    # Временные метки
    effective_from = Column(DateTime, server_default=func.now())
    effective_to = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Связи
    service = relationship("Service")


class PriceHistory(Base):
    """История изменений цен"""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Цены
    old_price = Column(Float, nullable=False)
    new_price = Column(Float, nullable=False)
    price_type = Column(String(50), default="base")  # base, dynamic, package
    
    # Причина изменения
    change_reason = Column(String(255))
    change_type = Column(String(50))  # manual, automatic, rule_based
    
    # Метаданные
    changed_at = Column(DateTime, server_default=func.now())
    changed_by = Column(Integer, ForeignKey("users.id"))
    effective_from = Column(DateTime)
    effective_to = Column(DateTime)
    
    # Связи
    service = relationship("Service")
    changed_by_user = relationship("User", foreign_keys=[changed_by])

