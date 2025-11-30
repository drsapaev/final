"""
Сервис для динамического ценообразования и пакетных услуг
"""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.dynamic_pricing import (
    DiscountType,
    DynamicPrice,
    PackagePurchase,
    PackageService,
    PriceHistory,
    PricingRule,
    PricingRuleService,
    PricingRuleType,
    ServicePackage,
)
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit


class DynamicPricingService:
    """Сервис для управления динамическим ценообразованием"""

    def __init__(self, db: Session):
        self.db = db

    # === Правила ценообразования ===

    def create_pricing_rule(
        self,
        name: str,
        rule_type: PricingRuleType,
        discount_type: DiscountType,
        discount_value: float,
        description: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        start_time: str = None,
        end_time: str = None,
        days_of_week: str = None,
        min_quantity: int = 1,
        max_quantity: int = None,
        min_amount: float = None,
        priority: int = 0,
        max_uses: int = None,
        created_by: int = None,
    ) -> PricingRule:
        """Создать правило ценообразования"""
        rule = PricingRule(
            name=name,
            description=description,
            rule_type=rule_type,
            discount_type=discount_type,
            discount_value=discount_value,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            days_of_week=days_of_week,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            min_amount=min_amount,
            priority=priority,
            max_uses=max_uses,
            created_by=created_by,
        )

        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def get_active_pricing_rules(
        self, service_ids: List[int] = None, rule_type: PricingRuleType = None
    ) -> List[PricingRule]:
        """Получить активные правила ценообразования"""
        query = self.db.query(PricingRule).filter(PricingRule.is_active == True)

        # Фильтр по времени
        now = datetime.now()
        query = query.filter(
            or_(PricingRule.start_date.is_(None), PricingRule.start_date <= now),
            or_(PricingRule.end_date.is_(None), PricingRule.end_date >= now),
        )

        # Фильтр по типу правила
        if rule_type:
            query = query.filter(PricingRule.rule_type == rule_type)

        # Фильтр по услугам
        if service_ids:
            query = query.join(PricingRuleService).filter(
                PricingRuleService.service_id.in_(service_ids)
            )

        return query.order_by(PricingRule.priority.desc()).all()

    def apply_pricing_rules(
        self,
        services: List[Dict[str, Any]],
        patient_id: int = None,
        appointment_time: datetime = None,
    ) -> Dict[str, Any]:
        """Применить правила ценообразования к списку услуг"""
        if not appointment_time:
            appointment_time = datetime.now()

        service_ids = [s.get('service_id') or s.get('id') for s in services]
        rules = self.get_active_pricing_rules(service_ids)

        # Исходная стоимость
        original_total = sum(s.get('price', 0) * s.get('quantity', 1) for s in services)

        # Применяем правила по приоритету
        applied_discounts = []
        current_total = original_total

        for rule in rules:
            if self._can_apply_rule(rule, services, appointment_time, patient_id):
                discount = self._calculate_rule_discount(rule, services, current_total)
                if discount > 0:
                    applied_discounts.append(
                        {
                            'rule_id': rule.id,
                            'rule_name': rule.name,
                            'discount_amount': discount,
                            'discount_type': rule.discount_type.value,
                        }
                    )
                    current_total -= discount

                    # Увеличиваем счетчик использований
                    rule.current_uses = (rule.current_uses or 0) + 1
                    self.db.commit()

        return {
            'original_total': original_total,
            'discounted_total': current_total,
            'total_savings': original_total - current_total,
            'applied_discounts': applied_discounts,
            'services_with_prices': self._update_service_prices(
                services, applied_discounts
            ),
        }

    def _can_apply_rule(
        self,
        rule: PricingRule,
        services: List[Dict[str, Any]],
        appointment_time: datetime,
        patient_id: int = None,
    ) -> bool:
        """Проверить, можно ли применить правило"""

        # Проверка лимита использований
        if rule.max_uses and rule.current_uses >= rule.max_uses:
            return False

        # Проверка времени дня
        if rule.start_time and rule.end_time:
            current_time = appointment_time.strftime('%H:%M:%S')
            if not (rule.start_time <= current_time <= rule.end_time):
                return False

        # Проверка дня недели
        if rule.days_of_week:
            weekday = str(appointment_time.weekday() + 1)  # 1-7 (пн-вс)
            if weekday not in rule.days_of_week.split(','):
                return False

        # Проверка количества услуг
        total_quantity = sum(s.get('quantity', 1) for s in services)
        if total_quantity < rule.min_quantity:
            return False
        if rule.max_quantity and total_quantity > rule.max_quantity:
            return False

        # Проверка минимальной суммы
        if rule.min_amount:
            total_amount = sum(
                s.get('price', 0) * s.get('quantity', 1) for s in services
            )
            if total_amount < rule.min_amount:
                return False

        return True

    def _calculate_rule_discount(
        self, rule: PricingRule, services: List[Dict[str, Any]], current_total: float
    ) -> float:
        """Рассчитать размер скидки по правилу"""

        if rule.discount_type == DiscountType.PERCENTAGE:
            return current_total * (rule.discount_value / 100)

        elif rule.discount_type == DiscountType.FIXED_AMOUNT:
            return min(rule.discount_value, current_total)

        elif rule.discount_type == DiscountType.BUY_X_GET_Y:
            # Логика "купи X получи Y бесплатно"
            total_quantity = sum(s.get('quantity', 1) for s in services)
            free_items = total_quantity // (rule.min_quantity + 1)
            if free_items > 0:
                # Находим самую дешевую услугу для бесплатной выдачи
                min_price = min(s.get('price', 0) for s in services)
                return min_price * free_items

        elif rule.discount_type == DiscountType.TIERED:
            # Ступенчатая скидка (чем больше, тем больше скидка)
            total_quantity = sum(s.get('quantity', 1) for s in services)
            if total_quantity >= 5:
                return current_total * 0.20  # 20% за 5+ услуг
            elif total_quantity >= 3:
                return current_total * 0.15  # 15% за 3-4 услуги
            elif total_quantity >= 2:
                return current_total * 0.10  # 10% за 2 услуги

        return 0

    def _update_service_prices(
        self, services: List[Dict[str, Any]], applied_discounts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Обновить цены услуг с учетом скидок"""
        # Пропорционально распределяем скидку по всем услугам
        total_discount = sum(d['discount_amount'] for d in applied_discounts)
        original_total = sum(s.get('price', 0) * s.get('quantity', 1) for s in services)

        updated_services = []
        for service in services:
            service_total = service.get('price', 0) * service.get('quantity', 1)
            if original_total > 0:
                service_discount = total_discount * (service_total / original_total)
                discounted_price = service.get('price', 0) - (
                    service_discount / service.get('quantity', 1)
                )
            else:
                discounted_price = service.get('price', 0)

            updated_service = service.copy()
            updated_service['discounted_price'] = max(0, discounted_price)
            updated_service['discount_amount'] = (
                service.get('price', 0) - discounted_price
            )
            updated_services.append(updated_service)

        return updated_services

    # === Пакеты услуг ===

    def create_service_package(
        self,
        name: str,
        description: str,
        service_ids: List[int],
        package_price: float,
        valid_from: datetime = None,
        valid_to: datetime = None,
        max_purchases: int = None,
        per_patient_limit: int = None,
        created_by: int = None,
    ) -> ServicePackage:
        """Создать пакет услуг"""

        # Рассчитываем исходную стоимость
        services = self.db.query(Service).filter(Service.id.in_(service_ids)).all()
        original_price = sum(s.price for s in services)
        savings_amount = original_price - package_price
        savings_percentage = (
            (savings_amount / original_price * 100) if original_price > 0 else 0
        )

        package = ServicePackage(
            name=name,
            description=description,
            package_price=package_price,
            original_price=original_price,
            savings_amount=savings_amount,
            savings_percentage=savings_percentage,
            valid_from=valid_from,
            valid_to=valid_to,
            max_purchases=max_purchases,
            per_patient_limit=per_patient_limit,
            created_by=created_by,
        )

        self.db.add(package)
        self.db.flush()

        # Добавляем услуги в пакет
        for service_id in service_ids:
            package_service = PackageService(
                package_id=package.id, service_id=service_id
            )
            self.db.add(package_service)

        self.db.commit()
        self.db.refresh(package)
        return package

    def get_available_packages(
        self, patient_id: int = None, service_ids: List[int] = None
    ) -> List[ServicePackage]:
        """Получить доступные пакеты услуг"""
        query = self.db.query(ServicePackage).filter(ServicePackage.is_active == True)

        # Фильтр по времени действия
        now = datetime.now()
        query = query.filter(
            or_(ServicePackage.valid_from.is_(None), ServicePackage.valid_from <= now),
            or_(ServicePackage.valid_to.is_(None), ServicePackage.valid_to >= now),
        )

        # Фильтр по лимиту покупок
        query = query.filter(
            or_(
                ServicePackage.max_purchases.is_(None),
                ServicePackage.current_purchases < ServicePackage.max_purchases,
            )
        )

        packages = query.all()

        # Фильтр по лимиту на пациента
        if patient_id:
            filtered_packages = []
            for package in packages:
                if package.per_patient_limit:
                    patient_purchases = (
                        self.db.query(PackagePurchase)
                        .filter(
                            PackagePurchase.package_id == package.id,
                            PackagePurchase.patient_id == patient_id,
                        )
                        .count()
                    )
                    if patient_purchases >= package.per_patient_limit:
                        continue
                filtered_packages.append(package)
            packages = filtered_packages

        return packages

    def purchase_package(
        self,
        package_id: int,
        patient_id: int,
        visit_id: int = None,
        appointment_id: int = None,
    ) -> PackagePurchase:
        """Купить пакет услуг"""
        package = (
            self.db.query(ServicePackage)
            .filter(ServicePackage.id == package_id)
            .first()
        )

        if not package:
            raise ValueError("Пакет не найден")

        if not package.is_active:
            raise ValueError("Пакет неактивен")

        # Проверяем лимиты
        if package.max_purchases and package.current_purchases >= package.max_purchases:
            raise ValueError("Превышен лимит покупок пакета")

        if package.per_patient_limit:
            patient_purchases = (
                self.db.query(PackagePurchase)
                .filter(
                    PackagePurchase.package_id == package_id,
                    PackagePurchase.patient_id == patient_id,
                )
                .count()
            )
            if patient_purchases >= package.per_patient_limit:
                raise ValueError("Превышен лимит покупок для пациента")

        # Создаем покупку
        purchase = PackagePurchase(
            package_id=package_id,
            patient_id=patient_id,
            visit_id=visit_id,
            appointment_id=appointment_id,
            purchase_price=package.package_price,
            original_price=package.original_price,
            savings_amount=package.savings_amount,
            expires_at=package.valid_to,
        )

        self.db.add(purchase)

        # Увеличиваем счетчик покупок
        package.current_purchases = (package.current_purchases or 0) + 1

        self.db.commit()
        self.db.refresh(purchase)
        return purchase

    # === Динамические цены ===

    def update_dynamic_prices(self) -> Dict[str, Any]:
        """Обновить динамические цены на основе спроса и загруженности"""
        updated_count = 0

        # Получаем все услуги с динамическими ценами
        dynamic_prices = self.db.query(DynamicPrice).all()

        for dp in dynamic_prices:
            # Рассчитываем факторы влияния
            demand_factor = self._calculate_demand_factor(dp.service_id)
            time_factor = self._calculate_time_factor()
            capacity_factor = self._calculate_capacity_factor(dp.service_id)
            seasonal_factor = self._calculate_seasonal_factor()

            # Рассчитываем новую цену
            new_price = (
                dp.base_price
                * demand_factor
                * time_factor
                * capacity_factor
                * seasonal_factor
            )
            new_price = max(dp.min_price, min(dp.max_price, new_price))

            # Обновляем если цена изменилась значительно (>5%)
            if abs(new_price - dp.current_price) / dp.current_price > 0.05:
                # Сохраняем историю
                self._save_price_history(
                    dp.service_id,
                    dp.current_price,
                    new_price,
                    "dynamic",
                    "automatic",
                    "Dynamic pricing algorithm",
                )

                dp.current_price = new_price
                dp.demand_factor = demand_factor
                dp.time_factor = time_factor
                dp.capacity_factor = capacity_factor
                dp.seasonal_factor = seasonal_factor
                dp.price_changes_count += 1
                dp.last_price_change = datetime.now()

                updated_count += 1

        self.db.commit()

        return {
            'updated_count': updated_count,
            'total_services': len(dynamic_prices),
            'timestamp': datetime.now(),
        }

    def _calculate_demand_factor(self, service_id: int) -> float:
        """Рассчитать коэффициент спроса"""
        # Анализируем записи за последние 30 дней
        thirty_days_ago = datetime.now() - timedelta(days=30)

        # Количество записей на эту услугу
        recent_bookings = (
            self.db.query(func.count(Visit.id))
            .join(Visit.visit_services)
            .filter(
                Visit.visit_services.any(service_id=service_id),
                Visit.created_at >= thirty_days_ago,
            )
            .scalar()
            or 0
        )

        # Нормализуем (1.0 = средний спрос, >1.0 = высокий спрос)
        avg_bookings = 10  # Базовое среднее количество
        return min(2.0, max(0.5, recent_bookings / avg_bookings))

    def _calculate_time_factor(self) -> float:
        """Рассчитать временной коэффициент"""
        now = datetime.now()
        hour = now.hour

        # Пиковые часы (9-12, 14-17) - повышенная цена
        if (9 <= hour <= 12) or (14 <= hour <= 17):
            return 1.2
        # Вечерние часы (18-20) - немного повышенная
        elif 18 <= hour <= 20:
            return 1.1
        # Остальное время - базовая или сниженная цена
        else:
            return 0.9

    def _calculate_capacity_factor(self, service_id: int) -> float:
        """Рассчитать коэффициент загруженности"""
        # Анализируем загруженность на ближайшие дни
        today = datetime.now().date()
        next_week = today + timedelta(days=7)

        # Количество свободных слотов
        # Это упрощенная логика, в реальности нужно анализировать расписание врачей
        total_slots = 50  # Общее количество слотов на неделю
        booked_slots = (
            self.db.query(func.count(Visit.id))
            .filter(Visit.visit_date >= today, Visit.visit_date <= next_week)
            .scalar()
            or 0
        )

        utilization = booked_slots / total_slots if total_slots > 0 else 0

        # Чем выше загруженность, тем выше цена
        if utilization > 0.8:
            return 1.3  # Очень высокая загруженность
        elif utilization > 0.6:
            return 1.1  # Высокая загруженность
        elif utilization < 0.3:
            return 0.8  # Низкая загруженность
        else:
            return 1.0  # Нормальная загруженность

    def _calculate_seasonal_factor(self) -> float:
        """Рассчитать сезонный коэффициент"""
        month = datetime.now().month

        # Зимние месяцы - повышенный спрос на медуслуги
        if month in [12, 1, 2]:
            return 1.1
        # Летние месяцы - сниженный спрос
        elif month in [6, 7, 8]:
            return 0.9
        else:
            return 1.0

    def _save_price_history(
        self,
        service_id: int,
        old_price: float,
        new_price: float,
        price_type: str,
        change_type: str,
        reason: str,
        changed_by: int = None,
    ):
        """Сохранить историю изменения цены"""
        history = PriceHistory(
            service_id=service_id,
            old_price=old_price,
            new_price=new_price,
            price_type=price_type,
            change_type=change_type,
            change_reason=reason,
            changed_by=changed_by,
            effective_from=datetime.now(),
        )
        self.db.add(history)

    # === Аналитика ===

    def get_pricing_analytics(
        self, start_date: datetime = None, end_date: datetime = None
    ) -> Dict[str, Any]:
        """Получить аналитику по ценообразованию"""
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()

        # Статистика по правилам
        rules_stats = (
            self.db.query(
                PricingRule.name,
                PricingRule.current_uses,
                func.sum(PriceHistory.old_price - PriceHistory.new_price).label(
                    'total_savings'
                ),
            )
            .outerjoin(
                PriceHistory,
                and_(
                    PriceHistory.change_type == 'rule_based',
                    PriceHistory.changed_at >= start_date,
                    PriceHistory.changed_at <= end_date,
                ),
            )
            .filter(PricingRule.is_active == True)
            .group_by(PricingRule.id, PricingRule.name)
            .all()
        )

        # Статистика по пакетам
        packages_stats = (
            self.db.query(
                ServicePackage.name,
                func.count(PackagePurchase.id).label('purchases_count'),
                func.sum(PackagePurchase.savings_amount).label('total_savings'),
            )
            .outerjoin(
                PackagePurchase,
                and_(
                    PackagePurchase.purchased_at >= start_date,
                    PackagePurchase.purchased_at <= end_date,
                ),
            )
            .filter(ServicePackage.is_active == True)
            .group_by(ServicePackage.id, ServicePackage.name)
            .all()
        )

        # Общая статистика
        total_rule_savings = sum(r.total_savings or 0 for r in rules_stats)
        total_package_savings = sum(p.total_savings or 0 for p in packages_stats)

        return {
            'period': {'start_date': start_date, 'end_date': end_date},
            'rules_statistics': [
                {
                    'name': r.name,
                    'uses': r.current_uses or 0,
                    'total_savings': r.total_savings or 0,
                }
                for r in rules_stats
            ],
            'packages_statistics': [
                {
                    'name': p.name,
                    'purchases': p.purchases_count or 0,
                    'total_savings': p.total_savings or 0,
                }
                for p in packages_stats
            ],
            'summary': {
                'total_rule_savings': total_rule_savings,
                'total_package_savings': total_package_savings,
                'total_savings': total_rule_savings + total_package_savings,
                'active_rules_count': len(rules_stats),
                'active_packages_count': len(packages_stats),
            },
        }
