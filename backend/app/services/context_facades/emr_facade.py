from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.domain.contracts.emr_contracts import (
    EmrContract,
    EmrContractFacade,
    VisitClinicalSnapshot,
)


logger = logging.getLogger(__name__)


class EmrServiceContractAdapter:
    """Adapter from legacy EMR services to EMR contract."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_visit_clinical_snapshot(
        self,
        visit_id: int,
        request_id: str | None = None,
    ) -> VisitClinicalSnapshot | None:
        _ = (visit_id, request_id)
        return None

    def append_clinical_note(
        self,
        visit_id: int,
        note_text: str,
        actor_user_id: int,
        request_id: str | None = None,
    ) -> bool:
        _ = (visit_id, note_text, actor_user_id, request_id)
        return False

    def index_emr_phrases(
        self,
        emr_id: int,
        doctor_id: int,
        specialty: str | None = None,
        request_id: str | None = None,
    ) -> int:
        _ = request_id
        from app.services.emr_phrase_indexer import get_emr_phrase_indexer

        indexer = get_emr_phrase_indexer(self._db)
        return indexer.index_single_emr(
            emr_id=emr_id,
            doctor_id=doctor_id,
            specialty=specialty,
        )


class EmrContextFacade:
    """Public entry point for cross-context EMR operations."""

    def __init__(self, contract: EmrContract) -> None:
        self._contract = EmrContractFacade(contract)

    def get_visit_clinical_snapshot(
        self,
        visit_id: int,
        correlation_id: str | None = None,
    ) -> VisitClinicalSnapshot | None:
        logger.info(
            "emr_facade.get_visit_clinical_snapshot correlation_id=%s visit_id=%s",
            correlation_id or "-",
            visit_id,
        )
        try:
            return self._contract.get_visit_clinical_snapshot(
                visit_id=visit_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "emr_facade.get_visit_clinical_snapshot failed correlation_id=%s visit_id=%s",
                correlation_id or "-",
                visit_id,
            )
            raise

    def append_clinical_note(
        self,
        visit_id: int,
        note_text: str,
        actor_user_id: int,
        correlation_id: str | None = None,
    ) -> bool:
        logger.info(
            "emr_facade.append_clinical_note correlation_id=%s visit_id=%s actor_user_id=%s",
            correlation_id or "-",
            visit_id,
            actor_user_id,
        )
        try:
            return self._contract.append_clinical_note(
                visit_id=visit_id,
                note_text=note_text,
                actor_user_id=actor_user_id,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "emr_facade.append_clinical_note failed correlation_id=%s visit_id=%s actor_user_id=%s",
                correlation_id or "-",
                visit_id,
                actor_user_id,
            )
            raise

    def index_emr_phrases(
        self,
        emr_id: int,
        doctor_id: int,
        specialty: str | None = None,
        correlation_id: str | None = None,
    ) -> int:
        logger.info(
            "emr_facade.index_emr_phrases correlation_id=%s emr_id=%s doctor_id=%s specialty=%s",
            correlation_id or "-",
            emr_id,
            doctor_id,
            specialty or "-",
        )
        try:
            return self._contract.index_emr_phrases(
                emr_id=emr_id,
                doctor_id=doctor_id,
                specialty=specialty,
                request_id=correlation_id,
            )
        except Exception:
            logger.exception(
                "emr_facade.index_emr_phrases failed correlation_id=%s emr_id=%s doctor_id=%s",
                correlation_id or "-",
                emr_id,
                doctor_id,
            )
            raise
