"""
EMRPhraseIndexer - Batch-индексатор для миграции существующих EMR

Извлекает фразы из существующих записей врачей
для наполнения DoctorPhraseHistory.

Это НЕ генерация - это извлечение и индексация
реальных фраз из истории врача.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.emr import EMR
from app.models.user import User
from app.services.doctor_phrase_service import DoctorPhraseService

logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    """Результат индексации"""
    doctor_id: int
    total_emrs: int
    total_phrases: int
    new_phrases: int
    updated_phrases: int
    duration_ms: int


@dataclass
class BatchResult:
    """Результат batch-индексации"""
    total_doctors: int
    total_emrs: int
    total_phrases: int
    doctors_now_ready: int
    duration_ms: int
    errors: List[str]


class EMRPhraseIndexer:
    """
    Batch-индексатор для миграции существующих EMR.
    
    Вызывается:
    1. Один раз при деплое для индексации всех EMR
    2. После каждого сохранения EMR для инкрементальной индексации
    """
    
    # Поля EMR для индексации (соответствуют модели EMR в emr.py)
    INDEXABLE_FIELDS = [
        'complaints',
        'anamnesis',
        'examination',
        'diagnosis',
        'recommendations'
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self.phrase_service = DoctorPhraseService(db)
    
    # ============================================
    # SINGLE DOCTOR INDEXING
    # ============================================
    
    def index_doctor_emrs(
        self, 
        doctor_id: int,
        specialty: Optional[str] = None
    ) -> IndexResult:
        """
        Проиндексировать все EMR одного врача.
        """
        from app.models.appointment import Appointment
        start_time = datetime.utcnow()
        
        # Получаем все EMR, привязанные к записям этого врача
        emrs = self.db.query(EMR).join(
            Appointment, EMR.appointment_id == Appointment.id
        ).filter(
            Appointment.doctor_id == doctor_id,
            EMR.is_draft == False  # Индексируем только завершённые
        ).all()
        
        total_phrases = 0
        new_phrases = 0
        updated_phrases = 0
        
        for emr in emrs:
            emr_data = self._extract_emr_fields(emr)
            
            if emr_data:
                indexed = self.phrase_service.index_doctor_phrases(
                    doctor_id=doctor_id,
                    emr_data=emr_data,
                    specialty=specialty or emr.specialty
                )
                total_phrases += indexed
        
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return IndexResult(
            doctor_id=doctor_id,
            total_emrs=len(emrs),
            total_phrases=total_phrases,
            new_phrases=0,
            updated_phrases=0,
            duration_ms=duration_ms
        )
    
    def _extract_emr_fields(self, emr: EMR) -> Dict[str, str]:
        """Извлечь индексируемые поля из EMR"""
        data = {}
        
        for field in self.INDEXABLE_FIELDS:
            value = getattr(emr, field, None)
            if value and isinstance(value, str) and len(value.strip()) >= 10:
                data[field] = value.strip()
        
        return data
    
    # ============================================
    # BATCH INDEXING (Migration)
    # ============================================
    
    def index_all_doctors(
        self, 
        limit: Optional[int] = None,
        offset: int = 0
    ) -> BatchResult:
        """
        Проиндексировать EMR всех врачей.
        """
        from app.models.appointment import Appointment
        start_time = datetime.utcnow()
        errors = []
        
        # Находим всех уникальных врачей, у которых есть сохранённые EMR
        doctors_query = self.db.query(
            Appointment.doctor_id,
            func.count(EMR.id).label('emr_count')
        ).join(
            EMR, EMR.appointment_id == Appointment.id
        ).filter(
            EMR.is_draft == False,
            Appointment.doctor_id != None
        ).group_by(Appointment.doctor_id)
        
        if limit:
            doctors_query = doctors_query.limit(limit).offset(offset)
        
        doctors = doctors_query.all()
        
        total_emrs = 0
        total_phrases = 0
        doctors_now_ready = 0
        
        for doctor_row in doctors:
            doctor_id = doctor_row[0]
            
            try:
                # Получаем специальность врача
                user = self.db.query(User).filter(User.id == doctor_id).first()
                specialty = getattr(user, 'specialty', None) if user else None
                
                # Индексируем
                result = self.index_doctor_emrs(doctor_id, specialty)
                
                total_emrs += result.total_emrs
                total_phrases += result.total_phrases
                
                # Проверяем readiness
                from app.services.doctor_autocomplete_readiness import DoctorAutocompleteReadiness
                readiness_service = DoctorAutocompleteReadiness(self.db)
                readiness = readiness_service.check_readiness(doctor_id)
                
                if readiness.ready:
                    doctors_now_ready += 1
                    logger.info(f"Doctor {doctor_id} is now ready for autocomplete")
                
            except Exception as e:
                error_msg = f"Error indexing doctor {doctor_id}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return BatchResult(
            total_doctors=len(doctors),
            total_emrs=total_emrs,
            total_phrases=total_phrases,
            doctors_now_ready=doctors_now_ready,
            duration_ms=duration_ms,
            errors=errors
        )
    
    # ============================================
    # INCREMENTAL INDEXING (on EMR save)
    # ============================================
    
    def index_single_emr(
        self, 
        emr_id: int,
        doctor_id: int,
        specialty: Optional[str] = None
    ) -> int:
        """
        Проиндексировать одну EMR запись.
        
        Вызывается после сохранения EMR.
        
        Args:
            emr_id: ID EMR записи
            doctor_id: ID врача
            specialty: Специальность
            
        Returns:
            Количество проиндексированных фраз
        """
        emr = self.db.query(EMR).filter(EMR.id == emr_id).first()
        
        if not emr:
            return 0
        
        emr_data = self._extract_emr_fields(emr)
        
        if not emr_data:
            return 0
        
        return self.phrase_service.index_doctor_phrases(
            doctor_id=doctor_id,
            emr_data=emr_data,
            specialty=specialty
        )
    
    # ============================================
    # CLEANUP (remove old/unused phrases)
    # ============================================
    
    def cleanup_old_phrases(
        self, 
        doctor_id: int,
        max_age_days: int = 365,
        min_usage: int = 1
    ) -> int:
        """
        Удалить старые неиспользуемые фразы.
        
        Args:
            doctor_id: ID врача
            max_age_days: Максимальный возраст в днях
            min_usage: Минимальное количество использований
            
        Returns:
            Количество удалённых фраз
        """
        from app.models.doctor_phrase_history import DoctorPhraseHistory
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        deleted = self.db.query(DoctorPhraseHistory).filter(
            DoctorPhraseHistory.doctor_id == doctor_id,
            DoctorPhraseHistory.last_used < cutoff_date,
            DoctorPhraseHistory.usage_count <= min_usage
        ).delete()
        
        self.db.commit()
        
        return deleted


def get_emr_phrase_indexer(db: Session) -> EMRPhraseIndexer:
    """Factory function for DI"""
    return EMRPhraseIndexer(db)
