from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.emr import EMR, Prescription
from app.schemas.emr import EMRCreate, EMRUpdate, PrescriptionCreate, PrescriptionUpdate


class CRUDEMR(CRUDBase[EMR, EMRCreate, EMRUpdate]):
    """CRUD операции для EMR"""

    def get_by_appointment(self, db: Session, *, appointment_id: int) -> Optional[EMR]:
        """Получить EMR по ID записи"""
        return db.query(EMR).filter(EMR.appointment_id == appointment_id).first()

    def save_emr(self, db: Session, *, emr_id: int) -> Optional[EMR]:
        """Сохранить EMR (перевести из draft в saved)"""
        emr = db.query(EMR).filter(EMR.id == emr_id).first()
        if emr and emr.is_draft:
            emr.is_draft = False
            emr.saved_at = datetime.utcnow()
            emr.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(emr)
        return emr

    def get_drafts(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[EMR]:
        """Получить черновики EMR"""
        # Форматирование обновлено для CI/CD
        return db.query(EMR).filter(EMR.is_draft).offset(skip).limit(limit).all()


class CRUDPrescription(CRUDBase[Prescription, PrescriptionCreate, PrescriptionUpdate]):
    """CRUD операции для рецептов"""

    def get_by_appointment(
        self, db: Session, *, appointment_id: int
    ) -> Optional[Prescription]:
        """Получить рецепт по ID записи"""
        return (
            db.query(Prescription)
            .filter(Prescription.appointment_id == appointment_id)
            .first()
        )

    def get_by_emr(self, db: Session, *, emr_id: int) -> Optional[Prescription]:
        """Получить рецепт по ID EMR"""
        return db.query(Prescription).filter(Prescription.emr_id == emr_id).first()

    def save_prescription(
        self, db: Session, *, prescription_id: int
    ) -> Optional[Prescription]:
        """Сохранить рецепт (перевести из draft в saved)"""
        prescription = (
            db.query(Prescription).filter(Prescription.id == prescription_id).first()
        )
        if prescription and prescription.is_draft:
            prescription.is_draft = False
            prescription.saved_at = datetime.utcnow()
            prescription.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(prescription)
        return prescription

    def mark_printed(
        self, db: Session, *, prescription_id: int
    ) -> Optional[Prescription]:
        """Отметить рецепт как напечатанный"""
        prescription = (
            db.query(Prescription).filter(Prescription.id == prescription_id).first()
        )
        if prescription:
            prescription.printed_at = datetime.utcnow()
            prescription.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(prescription)
        return prescription

    def get_drafts(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[Prescription]:
        """Получить черновики рецептов"""
        return (
            db.query(Prescription)
            .filter(Prescription.is_draft)
            .offset(skip)
            .limit(limit)
            .all()
        )


# Экземпляры CRUD
emr = CRUDEMR(EMR)
prescription = CRUDPrescription(Prescription)
