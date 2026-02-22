from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.domain.contracts.patient_contracts import (
    PatientContract,
    PatientContractFacade,
    PatientSummary,
)


logger = logging.getLogger(__name__)


class PatientServiceContractAdapter:
    """Adapter from legacy patient CRUD/service layer to patient contract."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_patient_summary(
        self,
        patient_id: int,
        request_id: str | None = None,
    ) -> PatientSummary | None:
        _ = request_id
        from app.crud import patient as crud_patient

        patient_obj = crud_patient.get(self._db, id=patient_id)
        if not patient_obj:
            return None

        return PatientSummary(
            patient_id=patient_obj.id,
            full_name=getattr(patient_obj, "full_name", ""),
            phone=getattr(patient_obj, "phone", None),
            birth_date=getattr(patient_obj, "birth_date", None),
            active=True,
        )

    def ensure_patient_edit_access(
        self,
        patient_id: int,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        _ = (patient_id, actor_user_id, request_id)
        return True


class PatientContextFacade:
    """Public entry point for cross-context patient operations."""

    def __init__(self, contract: PatientContract) -> None:
        self._contract = PatientContractFacade(contract)

    def lookup_patient_summary(
        self,
        patient_id: int,
        correlation_id: str | None = None,
    ) -> PatientSummary | None:
        logger.info(
            "patient_facade.lookup_patient_summary correlation_id=%s patient_id=%s",
            correlation_id or "-",
            patient_id,
        )
        try:
            return self._contract.get_patient_summary(
                patient_id=patient_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "patient_facade.lookup_patient_summary failed correlation_id=%s patient_id=%s",
                correlation_id or "-",
                patient_id,
            )
            raise

    def ensure_patient_edit_access(
        self,
        patient_id: int,
        actor_user_id: int,
        correlation_id: str | None = None,
    ) -> bool:
        logger.info(
            "patient_facade.ensure_patient_edit_access correlation_id=%s patient_id=%s actor_user_id=%s",
            correlation_id or "-",
            patient_id,
            actor_user_id,
        )
        try:
            return self._contract.ensure_patient_edit_access(
                patient_id=patient_id,
                actor_user_id=actor_user_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "patient_facade.ensure_patient_edit_access failed correlation_id=%s patient_id=%s actor_user_id=%s",
                correlation_id or "-",
                patient_id,
                actor_user_id,
            )
            raise
