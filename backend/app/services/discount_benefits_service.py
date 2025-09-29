"""
Сервис для управления скидками и льготами
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models.discount_benefits import (
    Discount, Benefit, DiscountService, PatientBenefit, 
    DiscountApplication, BenefitApplication, LoyaltyProgram,
    PatientLoyalty, LoyaltyPointTransaction, DiscountType, BenefitType
)
from app.models.patient import Patient
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.visit import Visit
import json
import logging

logger = logging.getLogger(__name__)


class DiscountBenefitsService:
    """Сервис для управления скидками и льготами"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # === СКИДКИ ===
    
    def create_discount(self, discount_data: Dict[str, Any], created_by: int) -> Discount:
        """Создать скидку"""
        discount = Discount(
            **discount_data,
            created_by=created_by
        )
        self.db.add(discount)
        self.db.commit()
        self.db.refresh(discount)
        return discount
    
    def get_active_discounts(self, service_ids: Optional[List[int]] = None) -> List[Discount]:
        """Получить активные скидки"""
        query = self.db.query(Discount).filter(
            Discount.is_active == True,
            or_(
                Discount.end_date.is_(None),
                Discount.end_date >= datetime.now()
            )
        )
        
        if service_ids:
            query = query.join(DiscountService).filter(
                DiscountService.service_id.in_(service_ids)
            )
        
        return query.order_by(Discount.priority.desc()).all()
    
    def calculate_discount(self, discount: Discount, amount: float, quantity: int = 1) -> float:
        """Рассчитать размер скидки"""
        if not discount.is_active or amount < discount.min_amount:
            return 0
        
        # Проверка лимита использований
        if discount.usage_limit and discount.usage_count >= discount.usage_limit:
            return 0
        
        # Проверка даты окончания
        if discount.end_date and discount.end_date < datetime.now():
            return 0
        
        discount_amount = 0
        
        if discount.discount_type == DiscountType.PERCENTAGE:
            discount_amount = amount * (discount.value / 100)
        elif discount.discount_type == DiscountType.FIXED_AMOUNT:
            discount_amount = discount.value
        elif discount.discount_type == DiscountType.BUY_X_GET_Y:
            # Логика "купи X получи Y"
            if quantity >= discount.value:
                free_items = quantity // int(discount.value)
                discount_amount = (amount / quantity) * free_items
        
        # Применить максимальную скидку
        if discount.max_discount and discount_amount > discount.max_discount:
            discount_amount = discount.max_discount
        
        return min(discount_amount, amount)
    
    def apply_discount(self, discount_id: int, amount: float, 
                      appointment_id: Optional[int] = None,
                      visit_id: Optional[int] = None,
                      invoice_id: Optional[int] = None,
                      applied_by: int = None) -> DiscountApplication:
        """Применить скидку"""
        discount = self.db.query(Discount).filter(Discount.id == discount_id).first()
        if not discount:
            raise ValueError("Скидка не найдена")
        
        discount_amount = self.calculate_discount(discount, amount)
        final_amount = amount - discount_amount
        
        application = DiscountApplication(
            discount_id=discount_id,
            appointment_id=appointment_id,
            visit_id=visit_id,
            invoice_id=invoice_id,
            original_amount=amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            applied_by=applied_by
        )
        
        # Увеличить счетчик использований
        discount.usage_count += 1
        
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        
        return application
    
    # === ЛЬГОТЫ ===
    
    def create_benefit(self, benefit_data: Dict[str, Any], created_by: int) -> Benefit:
        """Создать льготу"""
        benefit = Benefit(
            **benefit_data,
            created_by=created_by
        )
        self.db.add(benefit)
        self.db.commit()
        self.db.refresh(benefit)
        return benefit
    
    def assign_benefit_to_patient(self, patient_id: int, benefit_id: int, 
                                 document_data: Dict[str, Any],
                                 created_by: int) -> PatientBenefit:
        """Назначить льготу пациенту"""
        patient_benefit = PatientBenefit(
            patient_id=patient_id,
            benefit_id=benefit_id,
            document_number=document_data.get('document_number'),
            document_issued_date=document_data.get('document_issued_date'),
            document_expiry_date=document_data.get('document_expiry_date'),
            created_by=created_by
        )
        
        self.db.add(patient_benefit)
        self.db.commit()
        self.db.refresh(patient_benefit)
        
        return patient_benefit
    
    def verify_patient_benefit(self, patient_benefit_id: int, verified_by: int, 
                              notes: Optional[str] = None) -> PatientBenefit:
        """Верифицировать льготу пациента"""
        patient_benefit = self.db.query(PatientBenefit).filter(
            PatientBenefit.id == patient_benefit_id
        ).first()
        
        if not patient_benefit:
            raise ValueError("Льгота пациента не найдена")
        
        patient_benefit.verified = True
        patient_benefit.verification_date = datetime.now()
        patient_benefit.verification_notes = notes
        patient_benefit.verified_by = verified_by
        
        self.db.commit()
        self.db.refresh(patient_benefit)
        
        return patient_benefit
    
    def get_patient_benefits(self, patient_id: int, active_only: bool = True) -> List[PatientBenefit]:
        """Получить льготы пациента"""
        query = self.db.query(PatientBenefit).filter(
            PatientBenefit.patient_id == patient_id
        )
        
        if active_only:
            query = query.filter(
                PatientBenefit.is_active == True,
                PatientBenefit.verified == True,
                or_(
                    PatientBenefit.document_expiry_date.is_(None),
                    PatientBenefit.document_expiry_date >= datetime.now()
                )
            )
        
        return query.all()
    
    def calculate_benefit_discount(self, patient_benefit: PatientBenefit, amount: float) -> float:
        """Рассчитать размер льготной скидки"""
        if not patient_benefit.is_active or not patient_benefit.verified:
            return 0
        
        # Проверка срока действия документа
        if (patient_benefit.document_expiry_date and 
            patient_benefit.document_expiry_date < datetime.now()):
            return 0
        
        benefit = patient_benefit.benefit
        if not benefit.is_active:
            return 0
        
        # Рассчитать скидку
        discount_amount = amount * (benefit.discount_percentage / 100)
        
        # Применить максимальную скидку
        if benefit.max_discount_amount and discount_amount > benefit.max_discount_amount:
            discount_amount = benefit.max_discount_amount
        
        # Проверить месячный лимит
        if benefit.monthly_limit:
            current_month_usage = self.get_monthly_benefit_usage(patient_benefit.id)
            if current_month_usage + discount_amount > benefit.monthly_limit:
                discount_amount = max(0, benefit.monthly_limit - current_month_usage)
        
        # Проверить годовой лимит
        if benefit.yearly_limit:
            current_year_usage = self.get_yearly_benefit_usage(patient_benefit.id)
            if current_year_usage + discount_amount > benefit.yearly_limit:
                discount_amount = max(0, benefit.yearly_limit - current_year_usage)
        
        return min(discount_amount, amount)
    
    def apply_benefit(self, patient_benefit_id: int, amount: float,
                     appointment_id: Optional[int] = None,
                     visit_id: Optional[int] = None,
                     invoice_id: Optional[int] = None,
                     applied_by: int = None) -> BenefitApplication:
        """Применить льготу"""
        patient_benefit = self.db.query(PatientBenefit).filter(
            PatientBenefit.id == patient_benefit_id
        ).first()
        
        if not patient_benefit:
            raise ValueError("Льгота пациента не найдена")
        
        benefit_amount = self.calculate_benefit_discount(patient_benefit, amount)
        final_amount = amount - benefit_amount
        
        application = BenefitApplication(
            patient_benefit_id=patient_benefit_id,
            benefit_id=patient_benefit.benefit_id,
            appointment_id=appointment_id,
            visit_id=visit_id,
            invoice_id=invoice_id,
            original_amount=amount,
            benefit_amount=benefit_amount,
            final_amount=final_amount,
            applied_by=applied_by
        )
        
        # Обновить использование льготы
        patient_benefit.monthly_used_amount += benefit_amount
        patient_benefit.yearly_used_amount += benefit_amount
        patient_benefit.last_used_date = datetime.now()
        
        self.db.add(application)
        self.db.commit()
        self.db.refresh(application)
        
        return application
    
    def get_monthly_benefit_usage(self, patient_benefit_id: int) -> float:
        """Получить месячное использование льготы"""
        current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        result = self.db.query(func.sum(BenefitApplication.benefit_amount)).filter(
            BenefitApplication.patient_benefit_id == patient_benefit_id,
            BenefitApplication.applied_at >= current_month,
            BenefitApplication.applied_at < next_month
        ).scalar()
        
        return result or 0
    
    def get_yearly_benefit_usage(self, patient_benefit_id: int) -> float:
        """Получить годовое использование льготы"""
        current_year = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        next_year = current_year.replace(year=current_year.year + 1)
        
        result = self.db.query(func.sum(BenefitApplication.benefit_amount)).filter(
            BenefitApplication.patient_benefit_id == patient_benefit_id,
            BenefitApplication.applied_at >= current_year,
            BenefitApplication.applied_at < next_year
        ).scalar()
        
        return result or 0
    
    # === ПРОГРАММА ЛОЯЛЬНОСТИ ===
    
    def create_loyalty_program(self, program_data: Dict[str, Any], created_by: int) -> LoyaltyProgram:
        """Создать программу лояльности"""
        program = LoyaltyProgram(
            **program_data,
            created_by=created_by
        )
        self.db.add(program)
        self.db.commit()
        self.db.refresh(program)
        return program
    
    def enroll_patient_in_loyalty(self, patient_id: int, program_id: int) -> PatientLoyalty:
        """Записать пациента в программу лояльности"""
        # Проверить, не записан ли уже
        existing = self.db.query(PatientLoyalty).filter(
            PatientLoyalty.patient_id == patient_id,
            PatientLoyalty.program_id == program_id
        ).first()
        
        if existing:
            return existing
        
        patient_loyalty = PatientLoyalty(
            patient_id=patient_id,
            program_id=program_id
        )
        
        self.db.add(patient_loyalty)
        self.db.commit()
        self.db.refresh(patient_loyalty)
        
        return patient_loyalty
    
    def earn_loyalty_points(self, patient_id: int, program_id: int, amount: float,
                           appointment_id: Optional[int] = None,
                           visit_id: Optional[int] = None,
                           invoice_id: Optional[int] = None,
                           created_by: Optional[int] = None) -> int:
        """Начислить баллы лояльности"""
        program = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.id == program_id,
            LoyaltyProgram.is_active == True
        ).first()
        
        if not program or amount < program.min_purchase_for_points:
            return 0
        
        # Получить или создать запись лояльности пациента
        patient_loyalty = self.db.query(PatientLoyalty).filter(
            PatientLoyalty.patient_id == patient_id,
            PatientLoyalty.program_id == program_id
        ).first()
        
        if not patient_loyalty:
            patient_loyalty = self.enroll_patient_in_loyalty(patient_id, program_id)
        
        # Рассчитать баллы
        points = int(amount * program.points_per_ruble)
        
        if points > 0:
            # Создать транзакцию
            transaction = LoyaltyPointTransaction(
                patient_loyalty_id=patient_loyalty.id,
                transaction_type="earned",
                points=points,
                appointment_id=appointment_id,
                visit_id=visit_id,
                invoice_id=invoice_id,
                description=f"Начислено за покупку на сумму {amount} руб.",
                amount_related=amount,
                created_by=created_by
            )
            
            # Обновить баланс
            patient_loyalty.total_points_earned += points
            patient_loyalty.current_balance += points
            patient_loyalty.total_purchases += 1
            patient_loyalty.total_amount_spent += amount
            patient_loyalty.last_activity_date = datetime.now()
            
            self.db.add(transaction)
            self.db.commit()
        
        return points
    
    def redeem_loyalty_points(self, patient_id: int, program_id: int, points: int,
                             appointment_id: Optional[int] = None,
                             visit_id: Optional[int] = None,
                             invoice_id: Optional[int] = None,
                             created_by: Optional[int] = None) -> float:
        """Списать баллы лояльности"""
        program = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.id == program_id,
            LoyaltyProgram.is_active == True
        ).first()
        
        if not program:
            raise ValueError("Программа лояльности не найдена или неактивна")
        
        patient_loyalty = self.db.query(PatientLoyalty).filter(
            PatientLoyalty.patient_id == patient_id,
            PatientLoyalty.program_id == program_id,
            PatientLoyalty.is_active == True
        ).first()
        
        if not patient_loyalty:
            raise ValueError("Пациент не участвует в программе лояльности")
        
        if points < program.min_points_to_redeem:
            raise ValueError(f"Минимум для списания: {program.min_points_to_redeem} баллов")
        
        if points > patient_loyalty.current_balance:
            raise ValueError("Недостаточно баллов")
        
        # Рассчитать сумму скидки
        discount_amount = points * program.ruble_per_point
        
        # Создать транзакцию
        transaction = LoyaltyPointTransaction(
            patient_loyalty_id=patient_loyalty.id,
            transaction_type="redeemed",
            points=-points,
            appointment_id=appointment_id,
            visit_id=visit_id,
            invoice_id=invoice_id,
            description=f"Списано {points} баллов на сумму {discount_amount} руб.",
            amount_related=discount_amount,
            created_by=created_by
        )
        
        # Обновить баланс
        patient_loyalty.total_points_redeemed += points
        patient_loyalty.current_balance -= points
        patient_loyalty.last_activity_date = datetime.now()
        
        self.db.add(transaction)
        self.db.commit()
        
        return discount_amount
    
    def get_patient_loyalty_balance(self, patient_id: int, program_id: int) -> int:
        """Получить баланс баллов пациента"""
        patient_loyalty = self.db.query(PatientLoyalty).filter(
            PatientLoyalty.patient_id == patient_id,
            PatientLoyalty.program_id == program_id,
            PatientLoyalty.is_active == True
        ).first()
        
        return patient_loyalty.current_balance if patient_loyalty else 0
    
    # === КОМПЛЕКСНОЕ ПРИМЕНЕНИЕ ===
    
    def calculate_total_discount(self, patient_id: int, service_ids: List[int], 
                               amount: float) -> Dict[str, Any]:
        """Рассчитать общую скидку для пациента"""
        result = {
            'original_amount': amount,
            'discounts': [],
            'benefits': [],
            'loyalty_points_available': 0,
            'total_discount': 0,
            'final_amount': amount
        }
        
        # Получить активные скидки для услуг
        discounts = self.get_active_discounts(service_ids)
        
        # Получить льготы пациента
        patient_benefits = self.get_patient_benefits(patient_id)
        
        # Получить баллы лояльности
        active_programs = self.db.query(LoyaltyProgram).filter(
            LoyaltyProgram.is_active == True
        ).all()
        
        total_discount = 0
        current_amount = amount
        
        # Применить скидки (по приоритету)
        for discount in discounts:
            if not discount.can_combine_with_others and total_discount > 0:
                continue
            
            discount_amount = self.calculate_discount(discount, current_amount)
            if discount_amount > 0:
                result['discounts'].append({
                    'id': discount.id,
                    'name': discount.name,
                    'type': discount.discount_type,
                    'amount': discount_amount
                })
                total_discount += discount_amount
                current_amount -= discount_amount
        
        # Применить льготы
        for patient_benefit in patient_benefits:
            benefit_amount = self.calculate_benefit_discount(patient_benefit, current_amount)
            if benefit_amount > 0:
                result['benefits'].append({
                    'id': patient_benefit.id,
                    'name': patient_benefit.benefit.name,
                    'type': patient_benefit.benefit.benefit_type,
                    'amount': benefit_amount
                })
                total_discount += benefit_amount
                current_amount -= benefit_amount
        
        # Рассчитать доступные баллы лояльности
        for program in active_programs:
            balance = self.get_patient_loyalty_balance(patient_id, program.id)
            max_points_for_purchase = min(
                balance,
                program.max_points_per_purchase or balance,
                int(current_amount / program.ruble_per_point)
            )
            
            if max_points_for_purchase >= program.min_points_to_redeem:
                result['loyalty_points_available'] += max_points_for_purchase
        
        result['total_discount'] = total_discount
        result['final_amount'] = current_amount
        
        return result
    
    # === АНАЛИТИКА ===
    
    def get_discount_analytics(self, start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Получить аналитику по скидкам"""
        query = self.db.query(DiscountApplication)
        
        if start_date:
            query = query.filter(DiscountApplication.applied_at >= start_date)
        if end_date:
            query = query.filter(DiscountApplication.applied_at <= end_date)
        
        applications = query.all()
        
        total_applications = len(applications)
        total_original_amount = sum(app.original_amount for app in applications)
        total_discount_amount = sum(app.discount_amount for app in applications)
        
        # Группировка по типам скидок
        discount_types = {}
        for app in applications:
            discount_type = app.discount.discount_type
            if discount_type not in discount_types:
                discount_types[discount_type] = {
                    'count': 0,
                    'total_discount': 0,
                    'total_original': 0
                }
            
            discount_types[discount_type]['count'] += 1
            discount_types[discount_type]['total_discount'] += app.discount_amount
            discount_types[discount_type]['total_original'] += app.original_amount
        
        return {
            'total_applications': total_applications,
            'total_original_amount': total_original_amount,
            'total_discount_amount': total_discount_amount,
            'average_discount_percentage': (total_discount_amount / total_original_amount * 100) if total_original_amount > 0 else 0,
            'discount_types': discount_types
        }
    
    def get_benefit_analytics(self, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Получить аналитику по льготам"""
        query = self.db.query(BenefitApplication)
        
        if start_date:
            query = query.filter(BenefitApplication.applied_at >= start_date)
        if end_date:
            query = query.filter(BenefitApplication.applied_at <= end_date)
        
        applications = query.all()
        
        total_applications = len(applications)
        total_original_amount = sum(app.original_amount for app in applications)
        total_benefit_amount = sum(app.benefit_amount for app in applications)
        
        # Группировка по типам льгот
        benefit_types = {}
        for app in applications:
            benefit_type = app.benefit.benefit_type
            if benefit_type not in benefit_types:
                benefit_types[benefit_type] = {
                    'count': 0,
                    'total_benefit': 0,
                    'total_original': 0
                }
            
            benefit_types[benefit_type]['count'] += 1
            benefit_types[benefit_type]['total_benefit'] += app.benefit_amount
            benefit_types[benefit_type]['total_original'] += app.original_amount
        
        return {
            'total_applications': total_applications,
            'total_original_amount': total_original_amount,
            'total_benefit_amount': total_benefit_amount,
            'average_benefit_percentage': (total_benefit_amount / total_original_amount * 100) if total_original_amount > 0 else 0,
            'benefit_types': benefit_types
        }
    
    def get_loyalty_analytics(self, program_id: Optional[int] = None) -> Dict[str, Any]:
        """Получить аналитику по программе лояльности"""
        query = self.db.query(PatientLoyalty)
        
        if program_id:
            query = query.filter(PatientLoyalty.program_id == program_id)
        
        loyalty_records = query.all()
        
        total_patients = len(loyalty_records)
        total_points_earned = sum(record.total_points_earned for record in loyalty_records)
        total_points_redeemed = sum(record.total_points_redeemed for record in loyalty_records)
        total_amount_spent = sum(record.total_amount_spent for record in loyalty_records)
        
        active_patients = len([r for r in loyalty_records if r.is_active])
        
        return {
            'total_patients': total_patients,
            'active_patients': active_patients,
            'total_points_earned': total_points_earned,
            'total_points_redeemed': total_points_redeemed,
            'total_points_balance': total_points_earned - total_points_redeemed,
            'total_amount_spent': total_amount_spent,
            'average_points_per_patient': total_points_earned / total_patients if total_patients > 0 else 0,
            'redemption_rate': (total_points_redeemed / total_points_earned * 100) if total_points_earned > 0 else 0
        }

