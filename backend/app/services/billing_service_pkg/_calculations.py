"""Calculations mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase

class CalculationsMixin(BillingServiceMixinBase):
    """Calculations methods for BillingService."""

    def calculate_total(
        self,
        visit_id: int | None = None,
        services: list[dict[str, Any]] | None = None,
        discount_mode: str = "none",
    ) -> dict[str, Any]:
        """
        Расчёт общей суммы визита с учётом скидок (SSOT).

        Может работать с уже созданным визитом (visit_id) или с услугами до создания визита (services).

        Args:
            visit_id: ID визита (если визит уже создан)
            services: Список услуг в формате [{"service_id": int, "quantity": int, "custom_price": Optional[float]}] (если визит ещё не создан)
            discount_mode: Режим скидки (none|repeat|benefit|all_free)

        Returns:
            Dict с ключами: subtotal, discount, total, currency

        Raises:
            ValueError: Если визит не найден или не указаны ни visit_id, ни services
        """
        from decimal import Decimal

        subtotal = Decimal('0')
        original_total = Decimal('0')

        if visit_id:
            # Работаем с уже созданным визитом
            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                raise ValueError(f"Визит {visit_id} не найден")

            # Получаем услуги визита
            visit_services = (
                self.db.query(VisitService)
                .filter(VisitService.visit_id == visit_id)
                .all()
            )

            for visit_service in visit_services:
                # Базовая цена услуги
                base_price = visit_service.price or Decimal('0')
                item_total = base_price * Decimal(visit_service.qty or 1)
                original_total += item_total

                # Применяем скидки
                if (
                    discount_mode == "repeat"
                    and visit_service.code
                    and "consultation" in visit_service.code.lower()
                ):
                    # Повторная консультация бесплатна
                    item_total = Decimal('0')
                elif (
                    discount_mode == "benefit"
                    and visit_service.code
                    and "consultation" in visit_service.code.lower()
                ):
                    # Льготная консультация бесплатна
                    item_total = Decimal('0')
                elif discount_mode == "all_free":
                    # Всё бесплатно
                    item_total = Decimal('0')

                subtotal += item_total

        elif services:
            # Работаем с услугами до создания визита
            for service_item in services:
                service_id = service_item.get('service_id')
                quantity = service_item.get('quantity', 1)
                custom_price = service_item.get('custom_price')

                # Получаем услугу из БД
                service = (
                    self.db.query(Service).filter(Service.id == service_id).first()
                )
                if not service:
                    continue

                # Базовая цена (кастомная или из справочника)
                base_price = (
                    Decimal(str(custom_price))
                    if custom_price
                    else (service.price or Decimal('0'))
                )
                item_total = base_price * Decimal(quantity)
                original_total += item_total

                # Применяем скидки
                if discount_mode == "repeat" and service.is_consultation:
                    # Повторная консультация бесплатна
                    item_total = Decimal('0')
                elif discount_mode == "benefit" and service.is_consultation:
                    # Льготная консультация бесплатна
                    item_total = Decimal('0')
                elif discount_mode == "all_free":
                    # Всё бесплатно
                    item_total = Decimal('0')

                subtotal += item_total
        else:
            raise ValueError("Необходимо указать либо visit_id, либо services")

        # Расчёт скидки
        discount = original_total - subtotal

        total = subtotal
        currency = "UZS"  # По умолчанию

        return {
            "subtotal": float(subtotal),
            "discount": float(discount),
            "total": float(total),
            "currency": currency,
        }


    def get_discount_mode_for_visit(self, visit: Visit) -> str:
        """
        Получить registration discount_mode для визита (SSOT).

        Args:
            visit: Объект Visit

        Returns:
            discount_mode: none|repeat|benefit|all_free
        """
        return _normalize_registration_discount_mode(
            getattr(visit, 'discount_mode', None)
        )


    def update_visit_discount_mode(
        self,
        visit: Visit,
        force_update: bool = False,
    ) -> bool:
        """
        Нормализовать registration discount_mode визита (SSOT).

        Больше не использует и не сохраняет `paid` как discount_mode.

        Args:
            visit: Объект Visit для обновления
            force_update: Принудительно обновить даже если режим уже нормализован

        Returns:
            True если было выполнено обновление, False если нет
        """
        current_mode = getattr(visit, 'discount_mode', None)
        normalized_mode = _normalize_registration_discount_mode(current_mode)

        if force_update and normalized_mode != current_mode:
            visit.discount_mode = normalized_mode
            try:
                self.db.commit()
                self.db.refresh(visit)
                return True
            except Exception as e:
                self.db.rollback()
                raise ValueError(
                    f"Не удалось сохранить discount_mode для Visit {visit.id}: {e}"
                )

        return False


    def _get_applicable_billing_rules(
        self, trigger_event: str, entity
    ) -> list[BillingRule]:
        """Получить применимые правила биллинга"""
        rules = (
            self.db.query(BillingRule)
            .filter(
                BillingRule.is_active == True,
                BillingRule.trigger_event == trigger_event,
            )
            .all()
        )

        applicable_rules = []

        for rule in rules:
            if self._rule_matches_entity(rule, entity):
                applicable_rules.append(rule)

        return applicable_rules


    def _rule_matches_entity(self, rule: BillingRule, entity) -> bool:
        """Проверить, подходит ли правило для сущности"""
        # Здесь можно добавить более сложную логику проверки
        # На основе типов услуг, категорий пациентов, сумм и т.д.
        return True


    def _amount_to_words(self, amount: float) -> str:
        """Преобразовать сумму в слова"""
        # Упрощенная реализация
        return f"{int(amount)} сум"


