"""Service layer for cashier endpoints."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit
from app.repositories.cashier_api_repository import CashierApiRepository

logger = logging.getLogger(__name__)


class CashierApiService:
    """Business logic for cashier endpoint module."""

    def __init__(self, db: Session, repository: CashierApiRepository | None = None):
        self.repository = repository or CashierApiRepository(db)

    @staticmethod
    def _get_patient_name(patient: Optional[Patient], patient_id: int) -> str:
        if patient:
            if hasattr(patient, "short_name") and callable(patient.short_name):
                return patient.short_name()
            elif hasattr(patient, "fio") and patient.fio:
                return patient.fio
            else:
                parts = []
                if hasattr(patient, "last_name") and patient.last_name:
                    parts.append(patient.last_name)
                if hasattr(patient, "first_name") and patient.first_name:
                    parts.append(patient.first_name)
                if hasattr(patient, "middle_name") and patient.middle_name:
                    parts.append(patient.middle_name)
                if parts:
                    return " ".join(parts)
        return f"Пациент #{patient_id}"

    def get_pending_payments(self, *, date_from: Optional[date], date_to: Optional[date], search: Optional[str], page: int, size: int):
        db = self.repository.db
        """
        Получить список ожидающих оплаты записей/визитов.
        
        ВАЖНО: Группировка по пациенту!
        - Один пациент = одна строка (карточка) со ВСЕМИ его неоплаченными услугами
        - Полностью оплаченные пациенты НЕ показываются (они в истории платежей)
        - Если у пациента есть неоплаченные услуги - все объединяются в один блок
        """
        try:
            from collections import defaultdict
            import math
        
            # Базовый запрос - получаем все визиты (не отменённые и не оплаченные)
            # Исключаем визиты со статусами: canceled, paid, completed, done, closed
            excluded_statuses = ["canceled", "cancelled", "paid", "completed", "done", "closed"]
        
            # ✅ ОПТИМИЗАЦИЯ: Используем joinedload для eager loading services
            # Примечание: Visit.patient relationship не существует, поэтому используем batch loading
            query = db.query(Visit).options(
                joinedload(Visit.services)
            ).filter(
                ~Visit.status.in_(excluded_statuses),
                # Также исключаем визиты с discount_mode='paid' (SSOT признак оплаты)
                or_(
                    Visit.discount_mode.is_(None),
                    Visit.discount_mode != "paid"
                )
            )
        
            # Фильтр по датам
            if date_from:
                query = query.filter(Visit.created_at >= datetime.combine(date_from, datetime.min.time()))
            if date_to:
                query = query.filter(Visit.created_at <= datetime.combine(date_to, datetime.max.time()))
        
            # Поиск по пациенту (Join с Patient)
            if search:
                search_param = f"%{search}%"
                query = query.join(Patient, Visit.patient_id == Patient.id, isouter=True).filter(
                    or_(
                        Patient.last_name.ilike(search_param),
                        Patient.first_name.ilike(search_param),
                        Patient.middle_name.ilike(search_param),
                    )
                )
        
            # ✅ ОПТИМИЗАЦИЯ: Загружаем все визиты с eager loading для services
            all_visits = query.order_by(Visit.created_at.desc()).all()
        
            if not all_visits:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "size": size,
                    "pages": 0
                }
        
            # Batch Loading: Пациенты (Visit.patient relationship не существует)
            patient_ids = list(set([v.patient_id for v in all_visits if v.patient_id]))
            patients_map = {}
            if patient_ids:
                patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
                patients_map = {p.id: p for p in patients}
        
            # Batch Loading: Платежи для всех визитов (этот запрос всё ещё нужен)
            visit_ids = [v.id for v in all_visits]
            payments_map = defaultdict(list)  # visit_id -> list[Payment]
            if visit_ids:
                payments_batch = db.query(Payment).filter(
                    Payment.visit_id.in_(visit_ids),
                    Payment.status.in_(["paid", "completed"])
                ).all()
                for p in payments_batch:
                    payments_map[p.visit_id].append(p)
        
            # =====================================================
            # ГРУППИРОВКА ПО ПАЦИЕНТУ
            # =====================================================
            # Структура: patient_id -> {services: [], visits: [], total, paid, remaining, ...}
            patient_groups = defaultdict(lambda: {
                "patient_id": None,
                "patient": None,
                "patient_name": "",
                "patient_iin": None,
                "visit_ids": [],
                "services": [],
                "total_amount": Decimal("0"),
                "paid_amount": Decimal("0"),
                "remaining_amount": Decimal("0"),
                "created_at": None,  # Самая ранняя дата
                "department": None,
                "queue_number": None,
            })
        
            for visit in all_visits:
                if not visit.patient_id:
                    continue
        
                patient_id = visit.patient_id
                group = patient_groups[patient_id]
        
                # Устанавливаем данные пациента (один раз)
                if group["patient_id"] is None:
                    patient = patients_map.get(patient_id)
                    group["patient_id"] = patient_id
                    group["patient"] = patient
                    group["patient_name"] = self._get_patient_name(patient, patient_id)
                    group["patient_iin"] = getattr(patient, 'doc_number', None) if patient else None
        
                # Добавляем visit_id
                group["visit_ids"].append(visit.id)
        
                # Самая ранняя дата создания
                if group["created_at"] is None or (visit.created_at and visit.created_at < group["created_at"]):
                    group["created_at"] = visit.created_at
        
                # Департамент (берём первый непустой)
                if not group["department"] and hasattr(visit, 'department') and visit.department:
                    group["department"] = visit.department
        
                # Обработка услуг визита
                if hasattr(visit, 'services') and visit.services:
                    for vs in visit.services:
                        service_name = vs.name if hasattr(vs, 'name') and vs.name else "Услуга"
                        service_price = float(vs.price) if hasattr(vs, 'price') and vs.price else 0
                        service_qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
        
                        group["services"].append({
                            "id": vs.service_id if hasattr(vs, 'service_id') else vs.id,
                            "visit_id": visit.id,
                            "name": service_name,
                            "price": service_price,
                            "quantity": service_qty,
                        })
                        group["total_amount"] += Decimal(str(service_price)) * service_qty
        
                # Оплаченная сумма для этого визита
                visit_payments = payments_map.get(visit.id, [])
                for payment in visit_payments:
                    group["paid_amount"] += payment.amount
        
            # Считаем remaining и фильтруем оплаченных
            pending_groups = []
            for patient_id, group in patient_groups.items():
                group["remaining_amount"] = group["total_amount"] - group["paid_amount"]
        
                # =====================================================
                # ФИЛЬТРАЦИЯ: Исключаем полностью оплаченных
                # =====================================================
        
                # 1. Если нет услуг - пропускаем
                if not group["services"]:
                    continue
        
                # 2. Если total_amount = 0 (нет цены у услуг) - считаем бесплатным, пропускаем
                if group["total_amount"] <= 0:
                    continue
        
                # 3. Если remaining_amount <= 0 - полностью оплачено, пропускаем
                if group["remaining_amount"] <= 0:
                    continue
        
                # 4. Если paid >= total - полностью оплачено, пропускаем
                if group["paid_amount"] >= group["total_amount"]:
                    continue
        
                # Определяем статус для неоплаченных
                if group["paid_amount"] > 0:
                    group["status"] = "partial"  # Частично оплачено
                else:
                    group["status"] = "pending"  # Ожидает оплаты
        
                pending_groups.append(group)
        
            # Сортируем группы по дате создания (новые сверху)
            pending_groups.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
        
            # Подсчёт общего количества (до пагинации)
            total_count = len(pending_groups)
        
            # Пагинация
            offset = (page - 1) * size
            paginated_groups = pending_groups[offset:offset + size]
        
            # Формируем результат
            result = []
            for group in paginated_groups:
                result.append(dict(
                    id=group["visit_ids"][0] if group["visit_ids"] else 0,  # Первый visit_id для совместимости
                    patient_id=group["patient_id"],
                    patient_name=group["patient_name"],
                    patient_iin=group["patient_iin"],
                    visit_id=group["visit_ids"][0] if group["visit_ids"] else None,
                    visit_ids=group["visit_ids"],  # Все visit_id пациента
                    appointment_id=None,
                    services=group["services"],
                    total_amount=group["total_amount"],
                    paid_amount=group["paid_amount"],
                    remaining_amount=group["remaining_amount"],
                    status=group["status"],
                    created_at=group["created_at"],
                    queue_number=group["queue_number"],
                    department=group["department"],
                ))
        
            return {
                "items": result,
                "total": total_count,
                "page": page,
                "size": size,
                "pages": math.ceil(total_count / size) if size > 0 else 0
            }
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка получения ожидающих оплаты: {str(e)}"
            )
    def get_cashier_stats(self, *, date_from: Optional[date], date_to: Optional[date]):
        db = self.repository.db
        """
        Получить агрегированную статистику платежей за период.
        """
        try:
            query = db.query(Payment)
        
            if date_from:
                query = query.filter(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
            if date_to:
                query = query.filter(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))
        
            payments = query.all()
        
            total_amount = Decimal("0")
            cash_amount = Decimal("0")
            card_amount = Decimal("0")
            pending_amount = Decimal("0")
            paid_count = 0
            cancelled_count = 0
        
        
            for p in payments:
                if p.status in ["paid", "completed"]:
                    total_amount += p.amount
                    paid_count += 1
                    if hasattr(p, 'method') and p.method == "cash":
                        cash_amount += p.amount
                    elif hasattr(p, 'method') and p.method == "card":
                        card_amount += p.amount
                elif p.status in ["cancelled", "refunded"]:
                    cancelled_count += 1
        
        
            # Считаем pending из Visit
            pending_query = db.query(Visit).filter(Visit.status != "canceled")
            if date_from:
                pending_query = pending_query.filter(Visit.created_at >= datetime.combine(date_from, datetime.min.time()))
            if date_to:
                pending_query = pending_query.filter(Visit.created_at <= datetime.combine(date_to, datetime.max.time()))
        
            # Считаем только визиты без полной оплаты
            pending_count = 0
            visits = pending_query.all()
            visit_ids = [v.id for v in visits]
        
            if visit_ids:
                # Получаем суммы платежей для каждого визита
                from collections import defaultdict
                paid_by_visit = defaultdict(Decimal)
                existing = db.query(Payment).filter(
                    Payment.visit_id.in_(visit_ids),
                    Payment.status.in_(["paid", "completed"])
                ).all()
                for ep in existing:
                    paid_by_visit[ep.visit_id] += ep.amount
        
                for v in visits:
                    # Считаем стоимость визита
                    visit_total = Decimal("0")
                    if hasattr(v, 'services') and v.services:
                        for vs in v.services:
                            price = Decimal(str(vs.price)) if hasattr(vs, 'price') and vs.price else Decimal("0")
                            qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
                            visit_total += price * qty
        
                    if visit_total == Decimal("0") and hasattr(v, 'total_price') and v.total_price:
                        visit_total = Decimal(str(v.total_price))
        
                    paid_for_visit = paid_by_visit.get(v.id, Decimal("0"))
                    if paid_for_visit < visit_total:
                        pending_count += 1
                        pending_amount += (visit_total - paid_for_visit)
        
            return dict(
                total_amount=total_amount,
                cash_amount=cash_amount,
                card_amount=card_amount,
                pending_count=pending_count,
                pending_amount=pending_amount,
                paid_count=paid_count,
                cancelled_count=cancelled_count,
        
            )
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка получения статистики: {str(e)}"
            )
    def export_payments(self, *, date_from: Optional[date], date_to: Optional[date]):
        db = self.repository.db
        """
        Экспорт всех платежей за период в CSV.
        """
        from fastapi.responses import StreamingResponse
        import io
        import csv
        
        try:
            query = db.query(Payment)
        
            if date_from:
                query = query.filter(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
            if date_to:
                query = query.filter(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))
        
            query = query.order_by(Payment.created_at.desc()).limit(10000)
            payments = query.all()
        
            # Batch load visits and patients
            visit_ids = [p.visit_id for p in payments if p.visit_id]
            visits_map = {}
            patients_map = {}
        
            if visit_ids:
                visits = db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
                visits_map = {v.id: v for v in visits}
        
                patient_ids = [v.patient_id for v in visits if v.patient_id]
                if patient_ids:
                    patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
                    patients_map = {p.id: p for p in patients}
        
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')
        
            # Header
            writer.writerow(['Дата', 'Время', 'Пациент', 'Способ оплаты', 'Сумма', 'Статус', 'Примечание'])
        
            for p in payments:
                patient_name = "Неизвестно"
                if p.visit_id and p.visit_id in visits_map:
                    visit = visits_map[p.visit_id]
                    patient = patients_map.get(visit.patient_id)
                    patient_name = self._get_patient_name(patient, visit.patient_id)
        
                date_str = p.created_at.strftime('%d.%m.%Y') if p.created_at else ''
                time_str = p.created_at.strftime('%H:%M') if p.created_at else ''
                method_str = 'Наличные' if p.method == 'cash' else 'Карта' if p.method == 'card' else p.method
                status_str = 'Оплачено' if p.status in ['paid', 'completed'] else 'Отменён' if p.status == 'cancelled' else 'Ожидает'
        
                writer.writerow([
                    date_str,
                    time_str,
                    patient_name,
                    method_str,
                    str(p.amount),
                    status_str,
                    p.note or ''
                ])
        
            output.seek(0)
        
            # Return as streaming response with proper encoding for Cyrillic
            def generate():
                yield '\ufeff'  # BOM for Excel
                yield output.getvalue()
        
            filename = f"payments_{date_from or 'all'}_{date_to or 'all'}.csv"
        
            return StreamingResponse(
                generate(),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка экспорта: {str(e)}"
            )
    def get_payments(self, *, date_from: Optional[date], date_to: Optional[date], search: Optional[str], status_filter: Optional[str], method: Optional[str], page: int, size: int):
        db = self.repository.db
        """
        Получить историю платежей с пагинацией и поиском.
        """
        try:
            query = db.query(Payment)
        
            # Фильтр по статусу
            if status_filter:
                query = query.filter(Payment.status == status_filter)
        
            # Фильтр по методу оплаты
            if method:
                query = query.filter(Payment.method == method)
        
            # Join необходимы для поиска по имени пациента
            if search:
                # Payment -> Visit -> Patient
                query = query.join(Visit, Payment.visit_id == Visit.id)\
                             .join(Patient, Visit.patient_id == Patient.id)
        
                search_param = f"%{search}%"
                query = query.filter(
                    or_(
                        Patient.last_name.ilike(search_param),
                        Patient.first_name.ilike(search_param),
                        Patient.middle_name.ilike(search_param),
                    )
                )
        
            # Фильтр по датам
            if date_from:
                # При поиске может быть join, поэтому явно указываем Payment.created_at
                query = query.filter(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
            if date_to:
                query = query.filter(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))
        
            # Получаем общее количество ДО пагинации
            total_count = query.count()
        
            # Пагинация и Сортировка
            offset = (page - 1) * size
            query = query.order_by(Payment.created_at.desc()).offset(offset).limit(size)
        
            payments = query.all()
        
            # === Batch Loading Optimization ===
            visit_ids = [p.visit_id for p in payments if p.visit_id]
            visits_map = {}
            patients_map = {}
        
            if visit_ids:
                visits = db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
                visits_map = {v.id: v for v in visits}
        
                patient_ids = [v.patient_id for v in visits if v.patient_id]
                if patient_ids:
                    patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
                    patients_map = {p.id: p for p in patients}
        
            items = []
            for payment in payments:
                patient_id = 0
                patient_name = "Неизвестно"
        
                if payment.visit_id:
                    visit = visits_map.get(payment.visit_id)
                    if visit:
                        patient_id = visit.patient_id
                        patient = patients_map.get(visit.patient_id)
                        patient_name = self._get_patient_name(patient, visit.patient_id)
        
                items.append(dict(
                    id=payment.id,
                    patient_id=patient_id,
                    patient_name=patient_name,
                    visit_id=payment.visit_id,
                    amount=payment.amount,
                    method=payment.method if hasattr(payment, 'method') else 'cash',
                    status=payment.status,
                    created_at=payment.created_at,
                    paid_at=payment.paid_at if hasattr(payment, 'paid_at') else None,
                    note=payment.note if hasattr(payment, 'note') else None,
                    cashier_name=None,
                ))
        
            import math
            return dict(
                items=items,
                total=total_count,
                page=page,
                size=size,
                pages=math.ceil(total_count / size) if size > 0 else 0
            )
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка получения истории платежей: {str(e)}"
            )
    def create_payment(self, *, payment_data, current_user):
        db = self.repository.db
        """
        Создать новый платеж.
        """
        try:
            # Определяем patient_id
            patient_id = payment_data.patient_id
        
            if payment_data.visit_id:
                # ✅ FIX: Use lazy load to ensure consistency with get_pending_payments
                visit = db.query(Visit).filter(Visit.id == payment_data.visit_id).first()
                if not visit:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Визит не найден"
                    )
                patient_id = visit.patient_id
        
                # === ВАЛИДАЦИЯ ПЕРЕПЛАТЫ ===
                # 1. Считаем общую стоимость услуг
                total_cost = Decimal("0")
                if hasattr(visit, 'services') and visit.services:
                    for vs in visit.services:
                        price = Decimal(str(vs.price)) if hasattr(vs, 'price') and vs.price else Decimal("0")
                        qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
                        total_cost += price * qty
        
                # Fallback: если услуги не загружены, используем visit.total_price (если есть)
                if total_cost == Decimal("0"):
                    if hasattr(visit, 'total_price') and visit.total_price:
                        total_cost = Decimal(str(visit.total_price))
                    elif hasattr(visit, 'total_amount') and visit.total_amount:
                        total_cost = Decimal(str(visit.total_amount))
        
                # 2. Считаем уже оплаченное
                paid_amount = Decimal("0")
                existing_payments = db.query(Payment).filter(
                    Payment.visit_id == visit.id,
                    Payment.status.in_(["paid", "completed"])
                ).all()
                for p in existing_payments:
                    paid_amount += p.amount
        
                # 3. Проверяем остаток
                remaining_debt = total_cost - paid_amount
        
                # ⚠️ RELAXED VALIDATION: Разрешаем оплату даже если долг 0 (депозит/аванс)
                # или если total_cost посчитан неверно (0), но кассир хочет принять деньги.
                # if payment_data.amount > remaining_debt:
                #    raise HTTPException(...)
        
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Для создания платежа необходимо указать visit_id"
                )
        
            # Создаем платеж
            new_payment = Payment(
                visit_id=payment_data.visit_id,
                amount=payment_data.amount,
                method=payment_data.method,
                status="paid",
                note=payment_data.note,
                created_at=datetime.utcnow(),
                paid_at=datetime.utcnow(),
            )
        
            db.add(new_payment)
            db.commit()
            db.refresh(new_payment)
        
            # 🔔 WebSocket: Broadcast payment_created event
            try:
                from app.ws.cashier_ws import broadcast_cashier_update
                import asyncio
                asyncio.create_task(broadcast_cashier_update("payment_created", {
                    "payment_id": new_payment.id,
                    "visit_id": new_payment.visit_id,
                    "patient_id": patient_id,
                    "amount": float(new_payment.amount),
                    "method": new_payment.method,
                    "status": new_payment.status
                }))
            except Exception as ws_error:
                logger.warning(f"WebSocket broadcast failed: {ws_error}")
        
            return dict(
                id=new_payment.id,
                visit_id=new_payment.visit_id,
                patient_id=patient_id,
                amount=new_payment.amount,
                method=new_payment.method,
                status=new_payment.status,
                created_at=new_payment.created_at,
                paid_at=new_payment.paid_at,
                note=new_payment.note,
            )
        
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка создания платежа: {str(e)}"
            )
    def get_payment_by_id(self, *, payment_id: int):
        db = self.repository.db
        """
        Получить платеж по ID.
        """
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Платеж не найден"
            )
        
        # Определяем patient_id через visit
        patient_id = None
        if payment.visit_id:
            visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
            if visit:
                patient_id = visit.patient_id
        
        return dict(
            id=payment.id,
            visit_id=payment.visit_id,
            patient_id=patient_id,
            amount=payment.amount,
            method=payment.method if hasattr(payment, 'method') else 'cash',
            status=payment.status,
            created_at=payment.created_at,
            paid_at=payment.paid_at if hasattr(payment, 'paid_at') else None,
            note=payment.note if hasattr(payment, 'note') else None,
        )
    def cancel_payment(self, *, payment_id: int, cancel_data):
        db = self.repository.db
        """
        Отменить платеж.
        """
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Платеж не найден"
            )
        
        if payment.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Платеж уже отменен"
            )
        
        try:
            # Отменяем платеж
            payment.status = "cancelled"
            if hasattr(payment, 'note') and cancel_data.reason:
                payment.note = f"Отменён: {cancel_data.reason}"
        
            # Возвращаем статус визита в 'pending', чтобы он появился в списке
            if payment.visit_id:
                visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
                if visit and visit.status == 'paid':
                     visit.status = 'pending'
                     visit.discount_mode = 'none'
                     db.add(visit)
        
            db.commit()
        
            return {
                "success": True,
                "message": "Платеж успешно отменен",
                "payment_id": payment_id
            }
        
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка отмены платежа: {str(e)}"
            )
    def mark_visit_as_paid(self, *, visit_id: int):
        db = self.repository.db
        """
        Отметить визит как оплаченный.
        Создаёт платёж на полную сумму услуг визита.
        """
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        try:
            # Вычисляем общую сумму услуг
            total_amount = Decimal("0")
            if hasattr(visit, 'services') and visit.services:
                for vs in visit.services:
                    price = Decimal(str(vs.price)) if hasattr(vs, 'price') and vs.price else Decimal("0")
                    qty = vs.qty if hasattr(vs, 'qty') and vs.qty else 1
                    total_amount += price * qty
        
            # Создаём платёж на полную сумму
            if total_amount > 0:
                new_payment = Payment(
                    visit_id=visit_id,
                    amount=total_amount,
                    method="cash",
                    status="paid",
                    note="Помечен как оплаченный",
                    created_at=datetime.utcnow(),
                    paid_at=datetime.utcnow(),
                )
                db.add(new_payment)
        
            # Обновляем статус визита и discount_mode (SSOT)
            visit.status = "paid"  # Используем "paid" вместо "closed" для правильной фильтрации
            visit.discount_mode = "paid"  # SSOT признак оплаты
        
            db.commit()
        
            return {
                "success": True,
                "message": "Визит отмечен как оплаченный",
                "visit_id": visit_id,
                "amount": float(total_amount)
            }
        
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка обновления статуса визита: {str(e)}"
            )
    def confirm_payment(self, *, payment_id: int):
        db = self.repository.db
        """
        Вручную подтвердить платеж.
        """
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
             raise HTTPException(status_code=404, detail="Платеж не найден")
        
        if payment.status == 'paid':
             return {"success": True, "message": "Платеж уже оплачен"}
        
        if payment.status == 'cancelled':
             raise HTTPException(status_code=400, detail="Нельзя подтвердить отмененный платеж")
        
        # Обновляем статус платежа
        payment.status = 'paid'
        if not payment.provider_transaction_id:
            from datetime import datetime
            payment.provider_transaction_id = f"MANUAL-{payment_id}-{int(datetime.utcnow().timestamp())}"
        
        # Обновляем статус визита
        if payment.visit_id:
             visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
             if visit:
                 visit.status = 'paid'
                 visit.discount_mode = 'paid'
                 db.add(visit)
        
        db.commit()
        return {"success": True, "status": "paid"}
    def refund_payment(self, *, payment_id: int, refund_data, current_user):
        db = self.repository.db
        """
        Частичный или полный возврат средств по платежу.
        """
        try:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()
        
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Платеж не найден"
                )
        
            if payment.status not in ["paid", "completed"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Невозможно выполнить возврат для платежа со статусом '{payment.status}'"
                )
        
            # Проверяем, что сумма возврата не превышает доступную
            already_refunded = payment.refunded_amount or Decimal("0")
            available_for_refund = payment.amount - already_refunded
        
            if refund_data.amount > available_for_refund:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Сумма возврата ({refund_data.amount}) превышает доступную ({available_for_refund})"
                )
        
            # Обновляем платеж
            new_refunded_amount = already_refunded + refund_data.amount
            payment.refunded_amount = new_refunded_amount
            payment.refund_reason = refund_data.reason
            payment.refunded_at = datetime.utcnow()
            payment.refunded_by = current_user.id if hasattr(current_user, 'id') else None
        
            # Если возвращена вся сумма — статус "refunded"
            if new_refunded_amount >= payment.amount:
                payment.status = "refunded"
        
                # Возвращаем статус визита в 'pending' при полном возврате
                if payment.visit_id:
                    visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
                    if visit and visit.status == 'paid':
                         visit.status = 'pending'
                         visit.discount_mode = 'none'
                         db.add(visit)
            else:
                # Частичный возврат — оставляем "paid" но с пометкой
                pass
        
            db.commit()
            db.refresh(payment)
        
            return dict(
                id=payment.id,
                original_amount=payment.amount,
                refunded_amount=new_refunded_amount,
                remaining_amount=payment.amount - new_refunded_amount,
                reason=refund_data.reason,
                refunded_at=payment.refunded_at,
                status=payment.status
            )
        
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка возврата средств: {str(e)}"
            )
    def get_payment_receipt(self, *, payment_id: int):
        db = self.repository.db
        from fastapi.responses import StreamingResponse
        import io

        try:
            payment = db.query(Payment).filter(Payment.id == payment_id).first()

            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Платеж не найден",
                )

            visit = (
                db.query(Visit).filter(Visit.id == payment.visit_id).first()
                if payment.visit_id
                else None
            )
            patient = None
            patient_name = "Неизвестно"

            if visit:
                patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                if patient:
                    patient_name = self._get_patient_name(patient, patient.id)

            receipt_content = f"""
================================
        КВИТАНЦИЯ ОБ ОПЛАТЕ
================================

Номер чека: {payment.receipt_no or f"PAY-{payment.id:06d}"}
Дата: {payment.paid_at.strftime('%d.%m.%Y %H:%M') if payment.paid_at else payment.created_at.strftime('%d.%m.%Y %H:%M')}

--------------------------------
Пациент: {patient_name}
Визит ID: {payment.visit_id or 'N/A'}

--------------------------------
ПЛАТЕЖНАЯ ИНФОРМАЦИЯ:

Сумма: {payment.amount:,.0f} {payment.currency or 'UZS'}
Способ оплаты: {'Наличные' if payment.method == 'cash' else 'Карта' if payment.method == 'card' else payment.method}
Статус: {'Оплачено' if payment.status in ['paid', 'completed'] else 'Возвращено' if payment.status == 'refunded' else payment.status}

{f'Возврат: {payment.refunded_amount:,.0f} UZS' if payment.refunded_amount else ''}
{f'Причина возврата: {payment.refund_reason}' if payment.refund_reason else ''}

--------------------------------
{payment.note or ''}

================================
   Спасибо за визит!
================================
            """

            buffer = io.BytesIO(receipt_content.encode("utf-8"))
            return StreamingResponse(
                buffer,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": f"attachment; filename=receipt_{payment_id}.txt"
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка генерации чека: {str(e)}",
            )

    def get_hourly_stats(self, *, target_date: Optional[date]):
        db = self.repository.db
        try:
            if not target_date:
                target_date = date.today()

            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())

            payments = (
                db.query(Payment)
                .filter(
                    Payment.created_at >= start_of_day,
                    Payment.created_at <= end_of_day,
                    Payment.status.in_(["paid", "completed"]),
                )
                .all()
            )

            hourly_data = {}
            for h in range(24):
                hourly_data[h] = {"hour": h, "count": 0, "amount": Decimal("0")}

            for p in payments:
                hour = p.created_at.hour
                hourly_data[hour]["count"] += 1
                hourly_data[hour]["amount"] += p.amount

            return [data for data in hourly_data.values()]

        except Exception as e:
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка получения почасовой статистики: {str(e)}",
            )
