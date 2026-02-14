"""Repository helpers for phrase_suggest endpoints."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.doctor_phrase_history import DoctorPhraseHistory


class PhraseSuggestRepository:
    """Encapsulates DoctorPhraseHistory ORM operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_phrase_stats(self, *, doctor_id: int):
        return (
            self.db.query(
                DoctorPhraseHistory.field,
                func.count(DoctorPhraseHistory.id).label("count"),
                func.sum(DoctorPhraseHistory.usage_count).label("total_usage"),
            )
            .filter(DoctorPhraseHistory.doctor_id == doctor_id)
            .group_by(DoctorPhraseHistory.field)
            .all()
        )

    def get_by_id(self, phrase_id: int) -> DoctorPhraseHistory | None:
        return self.db.query(DoctorPhraseHistory).filter(DoctorPhraseHistory.id == phrase_id).first()

    def update_telemetry(self, *, phrase: DoctorPhraseHistory, event: str) -> None:
        if event == "shown":
            phrase.suggestions_shown += 1
        elif event == "accepted":
            phrase.suggestions_accepted += 1
        self.db.commit()

    def get_telemetry_totals(self, *, doctor_id: int):
        return (
            self.db.query(
                func.sum(DoctorPhraseHistory.suggestions_shown).label("total_shown"),
                func.sum(DoctorPhraseHistory.suggestions_accepted).label("total_accepted"),
            )
            .filter(DoctorPhraseHistory.doctor_id == doctor_id)
            .first()
        )

    def get_top_accepted_phrases(self, *, doctor_id: int, limit: int = 10):
        return (
            self.db.query(
                DoctorPhraseHistory.phrase,
                DoctorPhraseHistory.field,
                DoctorPhraseHistory.suggestions_accepted,
            )
            .filter(
                DoctorPhraseHistory.doctor_id == doctor_id,
                DoctorPhraseHistory.suggestions_accepted > 0,
            )
            .order_by(DoctorPhraseHistory.suggestions_accepted.desc())
            .limit(limit)
            .all()
        )

