from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.clinic import Doctor
from app.models.finance import FinanceTransaction
from app.schemas.finance import FinanceTransactionCreate, FinanceTransactionUpdate


class CRUDFinanceTransaction(
    CRUDBase[FinanceTransaction, FinanceTransactionCreate, FinanceTransactionUpdate]
):
    def _query(self, db: Session):
        return (
            db.query(self.model)
            .options(
                joinedload(self.model.patient),
                joinedload(self.model.doctor).joinedload(Doctor.user),
            )
        )

    @staticmethod
    def _normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        for key in ("category", "description", "notes", "reference", "payment_method", "type", "status"):
            value = payload.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                payload[key] = stripped if stripped else None
        for key in ("notes", "reference"):
            if payload.get(key) == "":
                payload[key] = None
        return payload

    def get(self, db: Session, id: Any) -> FinanceTransaction | None:
        return self._query(db).filter(self.model.id == id).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        type: str | None = None,
        status: str | None = None,
        category: str | None = None,
        patient_id: int | None = None,
        doctor_id: int | None = None,
    ) -> list[FinanceTransaction]:
        query = self._query(db)

        if type:
            query = query.filter(self.model.type == type)
        if status:
            query = query.filter(self.model.status == status)
        if category:
            query = query.filter(self.model.category == category)
        if patient_id is not None:
            query = query.filter(self.model.patient_id == patient_id)
        if doctor_id is not None:
            query = query.filter(self.model.doctor_id == doctor_id)

        return (
            query.order_by(self.model.transaction_date.desc(), self.model.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(
        self, db: Session, *, obj_in: FinanceTransactionCreate
    ) -> FinanceTransaction:
        data = self._normalize_payload(obj_in.model_dump())
        db_obj = self.model(**data)  # type: ignore[arg-type]
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return self.get(db, db_obj.id) or db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: FinanceTransaction,
        obj_in: FinanceTransactionUpdate | dict[str, Any],
    ) -> FinanceTransaction:
        if hasattr(obj_in, "model_dump"):
            update_data = obj_in.model_dump(exclude_unset=True)  # type: ignore[call-arg]
        else:
            update_data = dict(obj_in)

        update_data = self._normalize_payload(update_data)

        required_fields = (
            "type",
            "category",
            "amount",
            "description",
            "payment_method",
            "status",
            "transaction_date",
        )
        for field in required_fields:
            if field in update_data and update_data[field] is None:
                raise ValueError(f"Поле '{field}' не может быть пустым")

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return self.get(db, db_obj.id) or db_obj


finance_transaction = CRUDFinanceTransaction(FinanceTransaction)
