"""Service layer for phrase_suggest endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.phrase_suggest_repository import PhraseSuggestRepository


class PhraseSuggestApiService:
    """Builds phrase stats and telemetry payloads for API endpoints."""

    def __init__(
        self,
        db: Session,
        repository: PhraseSuggestRepository | None = None,
    ):
        self.repository = repository or PhraseSuggestRepository(db)

    def get_phrase_stats(self, *, doctor_id: int) -> dict:
        stats = self.repository.get_phrase_stats(doctor_id=doctor_id)
        return {
            "doctorId": doctor_id,
            "phrasesByField": {
                stat.field: {
                    "uniquePhrases": stat.count,
                    "totalUsage": stat.total_usage or 0,
                }
                for stat in stats
            },
        }

    def record_telemetry(
        self,
        *,
        phrase_id: int | None,
        event: str,
    ) -> dict:
        if phrase_id:
            phrase = self.repository.get_by_id(phrase_id)
            if phrase:
                self.repository.update_telemetry(phrase=phrase, event=event)

        return {
            "success": True,
            "message": f"Recorded {event} event",
        }

    def get_telemetry_stats(self, *, doctor_id: int) -> dict:
        stats = self.repository.get_telemetry_totals(doctor_id=doctor_id)
        total_shown = stats.total_shown or 0 if stats else 0
        total_accepted = stats.total_accepted or 0 if stats else 0
        acceptance_rate = (total_accepted / total_shown * 100) if total_shown > 0 else 0

        top_phrases = self.repository.get_top_accepted_phrases(doctor_id=doctor_id)

        return {
            "doctorId": doctor_id,
            "totalShown": total_shown,
            "totalAccepted": total_accepted,
            "acceptanceRate": round(acceptance_rate, 1),
            "avgTimeToAcceptMs": None,
            "topAcceptedPhrases": [
                {
                    "phrase": phrase.phrase[:50] + "..." if len(phrase.phrase) > 50 else phrase.phrase,
                    "field": phrase.field,
                    "timesAccepted": phrase.suggestions_accepted,
                }
                for phrase in top_phrases
            ],
        }

