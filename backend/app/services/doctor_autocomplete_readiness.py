"""
DoctorAutocompleteReadiness - Проверка готовности врача к автоподсказкам

Принцип: Autocomplete активируется АВТОМАТИЧЕСКИ 
только когда врач накопил достаточно данных.

До этого - полностью отключен, без UI switch.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models.doctor_phrase_history import DoctorPhraseHistory


@dataclass
class ReadinessProgress:
    """Прогресс до активации"""
    current: int
    required: int
    
    @property
    def met(self) -> bool:
        return self.current >= self.required
    
    @property
    def percentage(self) -> int:
        if self.required == 0:
            return 100
        return min(100, int((self.current / self.required) * 100))


@dataclass
class ReadinessResult:
    """Результат проверки готовности"""
    ready: bool
    completed_emrs: ReadinessProgress
    stored_phrases: ReadinessProgress
    repeated_phrases: ReadinessProgress
    acceptance_rate: Optional[float]
    missing: List[str]
    
    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "progress": {
                "completed_emrs": self.completed_emrs.current,
                "completed_emrs_required": self.completed_emrs.required,
                "stored_phrases": self.stored_phrases.current,
                "stored_phrases_required": self.stored_phrases.required,
                "repeated_phrases": self.repeated_phrases.current,
                "repeated_phrases_required": self.repeated_phrases.required,
                "acceptance_rate": self.acceptance_rate
            },
            "missing": self.missing,
            "message": self.missing[0] if self.missing else "Готово к автоподсказкам"
        }


class DoctorAutocompleteReadiness:
    """
    Сервис проверки готовности врача к автоподсказкам.
    
    Автоподсказки активируются ТОЛЬКО когда:
    - ≥10 завершённых EMR
    - ≥30 уникальных фраз в базе
    - ≥5 повторяющихся фраз (usage_count > 1)
    """
    
    # Пороговые значения
    MIN_COMPLETED_EMRS = 10
    MIN_STORED_PHRASES = 30
    MIN_REPEATED_PHRASES = 5
    MIN_ACCEPTANCE_RATE = 0.20  # опционально
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_readiness(self, doctor_id: int) -> ReadinessResult:
        """
        Проверить готовность врача к автоподсказкам.
        
        Args:
            doctor_id: ID врача
            
        Returns:
            ReadinessResult с флагом ready и прогрессом
        """
        stats = self._get_doctor_stats(doctor_id)
        missing = []
        
        # Проверяем каждый критерий
        completed_emrs = ReadinessProgress(
            current=stats['completed_emrs'],
            required=self.MIN_COMPLETED_EMRS
        )
        if not completed_emrs.met:
            missing.append(f"Нужно ещё {self.MIN_COMPLETED_EMRS - stats['completed_emrs']} завершённых EMR")
        
        stored_phrases = ReadinessProgress(
            current=stats['unique_phrases'],
            required=self.MIN_STORED_PHRASES
        )
        if not stored_phrases.met:
            missing.append(f"Нужно ещё {self.MIN_STORED_PHRASES - stats['unique_phrases']} уникальных фраз")
        
        repeated_phrases = ReadinessProgress(
            current=stats['repeated_phrases'],
            required=self.MIN_REPEATED_PHRASES
        )
        if not repeated_phrases.met:
            missing.append(f"Нужно ещё {self.MIN_REPEATED_PHRASES - stats['repeated_phrases']} повторяющихся фраз")
        
        # Acceptance rate (опционально, не блокирует)
        acceptance_rate = None
        if stats['suggestions_shown'] > 0:
            acceptance_rate = stats['suggestions_accepted'] / stats['suggestions_shown']
        
        ready = len(missing) == 0
        
        return ReadinessResult(
            ready=ready,
            completed_emrs=completed_emrs,
            stored_phrases=stored_phrases,
            repeated_phrases=repeated_phrases,
            acceptance_rate=acceptance_rate,
            missing=missing
        )
    
    def _get_doctor_stats(self, doctor_id: int) -> dict:
        """Получить статистику врача"""
        
        # Уникальные фразы
        unique_phrases = self.db.query(
            func.count(distinct(DoctorPhraseHistory.id))
        ).filter(
            DoctorPhraseHistory.doctor_id == doctor_id
        ).scalar() or 0
        
        # Повторяющиеся фразы (usage_count > 1)
        repeated_phrases = self.db.query(
            func.count(DoctorPhraseHistory.id)
        ).filter(
            DoctorPhraseHistory.doctor_id == doctor_id,
            DoctorPhraseHistory.usage_count > 1
        ).scalar() or 0
        
        # Подсчёт EMR (по уникальным датам first_used)
        # Предполагаем что каждая EMR создаёт фразы в один день
        completed_emrs = self.db.query(
            func.count(distinct(func.date(DoctorPhraseHistory.first_used)))
        ).filter(
            DoctorPhraseHistory.doctor_id == doctor_id
        ).scalar() or 0
        
        # Telemetry (suggestions_shown / accepted)
        telemetry = self.db.query(
            func.sum(DoctorPhraseHistory.suggestions_shown).label('shown'),
            func.sum(DoctorPhraseHistory.suggestions_accepted).label('accepted')
        ).filter(
            DoctorPhraseHistory.doctor_id == doctor_id
        ).first()
        
        suggestions_shown = telemetry.shown or 0 if telemetry else 0
        suggestions_accepted = telemetry.accepted or 0 if telemetry else 0
        
        return {
            'completed_emrs': completed_emrs,
            'unique_phrases': unique_phrases,
            'repeated_phrases': repeated_phrases,
            'suggestions_shown': suggestions_shown,
            'suggestions_accepted': suggestions_accepted
        }
    
    def get_readiness_summary(self, doctor_id: int) -> str:
        """Получить текстовое описание прогресса"""
        result = self.check_readiness(doctor_id)
        
        if result.ready:
            return "✅ Автоподсказки активны"
        
        # Показываем прогресс
        parts = []
        if not result.completed_emrs.met:
            parts.append(f"EMR: {result.completed_emrs.current}/{result.completed_emrs.required}")
        if not result.stored_phrases.met:
            parts.append(f"Фразы: {result.stored_phrases.current}/{result.stored_phrases.required}")
        if not result.repeated_phrases.met:
            parts.append(f"Повторы: {result.repeated_phrases.current}/{result.repeated_phrases.required}")
        
        return f"⏳ Прогресс: {', '.join(parts)}"


def get_doctor_readiness_service(db: Session) -> DoctorAutocompleteReadiness:
    """Factory function for DI"""
    return DoctorAutocompleteReadiness(db)
