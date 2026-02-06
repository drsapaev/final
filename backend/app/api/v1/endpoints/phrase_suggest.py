"""
Phrase Suggest API - Endpoint для подсказок из истории врача

Принцип: поиск и ранжирование ранее введённых фраз,
НЕ генерация нового текста.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.services.doctor_phrase_service import DoctorPhraseService, get_doctor_phrase_service

router = APIRouter()


# ============================================
# SCHEMAS
# ============================================

class PhraseSuggestRequest(BaseModel):
    """Запрос на подсказку фраз"""
    field: str = Field(..., description="Поле EMR: complaints, diagnosis, etc.")
    currentText: str = Field("", description="Текущий текст в поле")
    cursorPosition: int = Field(0, ge=0, description="Позиция курсора")
    doctorId: int = Field(..., description="ID врача")
    specialty: Optional[str] = Field(None, description="Специальность врача")
    maxSuggestions: int = Field(5, ge=1, le=10, description="Максимум подсказок")


class PhraseSuggestion(BaseModel):
    """Одна подсказка"""
    text: str = Field(..., description="Текст продолжения (хвост)")
    source: str = Field("history", description="Источник: history")
    usageCount: int = Field(0, description="Частота использования")
    lastUsed: Optional[str] = Field(None, description="Дата последнего использования")


class PhraseSuggestResponse(BaseModel):
    """Ответ с подсказками"""
    suggestions: List[PhraseSuggestion]
    field: str
    doctorId: int


class IndexPhraseRequest(BaseModel):
    """Запрос на индексацию фраз из EMR"""
    doctorId: int
    specialty: Optional[str] = None
    emrData: Dict[str, Any]


class IndexPhraseResponse(BaseModel):
    """Ответ на индексацию"""
    success: bool
    indexedCount: int
    message: str


# ============================================
# ENDPOINTS
# ============================================

@router.post("/phrase-suggest", response_model=PhraseSuggestResponse)
async def suggest_phrases(
    request: PhraseSuggestRequest,
    db: Session = Depends(deps.get_db)
) -> PhraseSuggestResponse:
    """
    Получить подсказки фраз из истории врача.
    
    Это НЕ генерация текста, а поиск и ранжирование
    ранее введённых врачом фраз.
    
    Возвращает только "хвост" (continuation), не полный текст.
    """
    service = get_doctor_phrase_service(db)
    
    suggestions = service.suggest_phrases(
        doctor_id=request.doctorId,
        field=request.field,
        current_text=request.currentText,
        cursor_position=request.cursorPosition,
        specialty=request.specialty,
        max_suggestions=request.maxSuggestions
    )
    
    return PhraseSuggestResponse(
        suggestions=[
            PhraseSuggestion(
                text=s["text"],
                source=s["source"],
                usageCount=s["usageCount"],
                lastUsed=s["lastUsed"]
            )
            for s in suggestions
        ],
        field=request.field,
        doctorId=request.doctorId
    )


@router.post("/phrase-index", response_model=IndexPhraseResponse)
async def index_phrases(
    request: IndexPhraseRequest,
    db: Session = Depends(deps.get_db)
) -> IndexPhraseResponse:
    """
    Проиндексировать фразы из EMR записи.
    
    Вызывается после сохранения EMR для обновления
    истории фраз врача.
    """
    service = get_doctor_phrase_service(db)
    
    try:
        indexed_count = service.index_doctor_phrases(
            doctor_id=request.doctorId,
            emr_data=request.emrData,
            specialty=request.specialty
        )
        
        return IndexPhraseResponse(
            success=True,
            indexedCount=indexed_count,
            message=f"Indexed {indexed_count} phrases for doctor {request.doctorId}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index phrases: {str(e)}"
        )


@router.get("/phrase-stats/{doctor_id}")
async def get_phrase_stats(
    doctor_id: int,
    db: Session = Depends(deps.get_db)
) -> Dict[str, Any]:
    """
    Получить статистику фраз врача.
    """
    from app.models.doctor_phrase_history import DoctorPhraseHistory
    from sqlalchemy import func
    
    stats = db.query(
        DoctorPhraseHistory.field,
        func.count(DoctorPhraseHistory.id).label('count'),
        func.sum(DoctorPhraseHistory.usage_count).label('total_usage')
    ).filter(
        DoctorPhraseHistory.doctor_id == doctor_id
    ).group_by(
        DoctorPhraseHistory.field
    ).all()
    
    return {
        "doctorId": doctor_id,
        "phrasesByField": {
            stat.field: {
                "uniquePhrases": stat.count,
                "totalUsage": stat.total_usage or 0
            }
            for stat in stats
        }
    }


# ============================================
# READINESS CHECK (Automatic Activation)
# ============================================

class ReadinessResponse(BaseModel):
    """Результат проверки готовности"""
    ready: bool
    progress: Dict[str, Any]
    missing: List[str]
    message: str


@router.get("/readiness/{doctor_id}", response_model=ReadinessResponse)
async def check_readiness(
    doctor_id: int,
    db: Session = Depends(deps.get_db)
) -> ReadinessResponse:
    """
    Проверить готовность врача к автоподсказкам.
    
    Автоподсказки активируются АВТОМАТИЧЕСКИ только когда:
    - ≥10 завершённых EMR
    - ≥30 уникальных фраз
    - ≥5 повторяющихся фраз
    
    До этого — полностью отключены, без UI switch.
    """
    from app.services.doctor_autocomplete_readiness import get_doctor_readiness_service
    
    service = get_doctor_readiness_service(db)
    result = service.check_readiness(doctor_id)
    
    return ReadinessResponse(**result.to_dict())


# ============================================
# TELEMETRY (Track acceptance rate)
# ============================================

class TelemetryRequest(BaseModel):
    """Событие telemetry"""
    doctorId: int
    field: str
    event: str = Field(..., pattern="^(shown|accepted|dismissed)$")
    phraseId: Optional[int] = None
    timeMs: Optional[int] = None


class TelemetryResponse(BaseModel):
    """Ответ на telemetry"""
    success: bool
    message: str


@router.post("/telemetry", response_model=TelemetryResponse)
async def record_telemetry(
    request: TelemetryRequest,
    db: Session = Depends(deps.get_db)
) -> TelemetryResponse:
    """
    Записать событие показа/принятия подсказки.
    
    Используется для расчёта acceptance_rate.
    """
    from app.models.doctor_phrase_history import DoctorPhraseHistory
    
    try:
        if request.phraseId:
            phrase = db.query(DoctorPhraseHistory).filter(
                DoctorPhraseHistory.id == request.phraseId
            ).first()
            
            if phrase:
                if request.event == "shown":
                    phrase.suggestions_shown += 1
                elif request.event == "accepted":
                    phrase.suggestions_accepted += 1
                
                db.commit()
        
        return TelemetryResponse(
            success=True,
            message=f"Recorded {request.event} event"
        )
    except Exception as e:
        return TelemetryResponse(
            success=False,
            message=str(e)
        )


# ============================================
# TELEMETRY STATS (Dashboard)
# ============================================

class TelemetryStatsResponse(BaseModel):
    """Статистика telemetry врача"""
    doctorId: int
    totalShown: int
    totalAccepted: int
    acceptanceRate: float
    avgTimeToAcceptMs: Optional[int]
    topAcceptedPhrases: List[Dict[str, Any]]


@router.get("/telemetry-stats/{doctor_id}", response_model=TelemetryStatsResponse)
async def get_telemetry_stats(
    doctor_id: int,
    db: Session = Depends(deps.get_db)
) -> TelemetryStatsResponse:
    """
    Получить статистику telemetry врача.
    
    Показывает acceptance rate и топ принятых фраз.
    """
    from app.models.doctor_phrase_history import DoctorPhraseHistory
    from sqlalchemy import func
    
    # Агрегированная статистика
    stats = db.query(
        func.sum(DoctorPhraseHistory.suggestions_shown).label('total_shown'),
        func.sum(DoctorPhraseHistory.suggestions_accepted).label('total_accepted')
    ).filter(
        DoctorPhraseHistory.doctor_id == doctor_id
    ).first()
    
    total_shown = stats.total_shown or 0 if stats else 0
    total_accepted = stats.total_accepted or 0 if stats else 0
    acceptance_rate = (total_accepted / total_shown * 100) if total_shown > 0 else 0
    
    # Топ принятых фраз
    top_phrases = db.query(
        DoctorPhraseHistory.phrase,
        DoctorPhraseHistory.field,
        DoctorPhraseHistory.suggestions_accepted
    ).filter(
        DoctorPhraseHistory.doctor_id == doctor_id,
        DoctorPhraseHistory.suggestions_accepted > 0
    ).order_by(
        DoctorPhraseHistory.suggestions_accepted.desc()
    ).limit(10).all()
    
    return TelemetryStatsResponse(
        doctorId=doctor_id,
        totalShown=total_shown,
        totalAccepted=total_accepted,
        acceptanceRate=round(acceptance_rate, 1),
        avgTimeToAcceptMs=None,  # TODO: track separately
        topAcceptedPhrases=[
            {
                "phrase": p.phrase[:50] + "..." if len(p.phrase) > 50 else p.phrase,
                "field": p.field,
                "timesAccepted": p.suggestions_accepted
            }
            for p in top_phrases
        ]
    )


# ============================================
# PER-FIELD PREFERENCES (Hybrid Control)
# ============================================

class FieldPreference(BaseModel):
    """Preference для одного поля"""
    field: str
    paused: bool = False


class FieldPreferencesRequest(BaseModel):
    """Запрос на обновление preferences"""
    doctorId: int
    preferences: List[FieldPreference]


class FieldPreferencesResponse(BaseModel):
    """Ответ с preferences"""
    doctorId: int
    preferences: Dict[str, bool]  # field -> paused


@router.get("/preferences/{doctor_id}", response_model=FieldPreferencesResponse)
async def get_field_preferences(
    doctor_id: int,
    db: Session = Depends(deps.get_db)
) -> FieldPreferencesResponse:
    """
    Получить per-field preferences для врача.
    
    Доступно ТОЛЬКО после readiness=true.
    """
    # TODO: Store in UserPreferences table
    # For now, return default (all enabled)
    return FieldPreferencesResponse(
        doctorId=doctor_id,
        preferences={
            "complaints": False,
            "anamnesis_morbi": False,
            "examination": False,
            "diagnosis": False,
            "treatment": False,
            "recommendations": False
        }
    )


@router.post("/preferences", response_model=FieldPreferencesResponse)
async def update_field_preferences(
    request: FieldPreferencesRequest,
    db: Session = Depends(deps.get_db)
) -> FieldPreferencesResponse:
    """
    Обновить per-field preferences.
    
    Позволяет врачу приостановить подсказки для конкретных полей.
    Доступно ТОЛЬКО после readiness=true.
    """
    # TODO: Store in UserPreferences table
    # For now, just echo back
    return FieldPreferencesResponse(
        doctorId=request.doctorId,
        preferences={
            pref.field: pref.paused
            for pref in request.preferences
        }
    )


# ============================================
# BATCH INDEXING (Migration)
# ============================================

class BatchIndexRequest(BaseModel):
    """Запрос на batch-индексацию"""
    limit: Optional[int] = Field(None, description="Максимум врачей")
    offset: int = Field(0, ge=0, description="Смещение")


class BatchIndexResponse(BaseModel):
    """Результат batch-индексации"""
    success: bool
    totalDoctors: int
    totalEmrs: int
    totalPhrases: int
    doctorsNowReady: int
    durationMs: int
    errors: List[str]


@router.post("/batch-index", response_model=BatchIndexResponse)
async def batch_index_emrs(
    request: BatchIndexRequest,
    db: Session = Depends(deps.get_db)
) -> BatchIndexResponse:
    """
    Batch-индексация EMR всех врачей.
    
    ⚠️ ADMIN ONLY - используется для миграции.
    Может занять много времени при большом количестве данных.
    """
    from app.services.emr_phrase_indexer import get_emr_phrase_indexer
    
    indexer = get_emr_phrase_indexer(db)
    
    try:
        result = indexer.index_all_doctors(
            limit=request.limit,
            offset=request.offset
        )
        
        return BatchIndexResponse(
            success=True,
            totalDoctors=result.total_doctors,
            totalEmrs=result.total_emrs,
            totalPhrases=result.total_phrases,
            doctorsNowReady=result.doctors_now_ready,
            durationMs=result.duration_ms,
            errors=result.errors
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch indexing failed: {str(e)}"
        )


class DoctorIndexRequest(BaseModel):
    """Запрос на индексацию одного врача"""
    doctorId: int
    specialty: Optional[str] = None


class DoctorIndexResponse(BaseModel):
    """Результат индексации врача"""
    success: bool
    doctorId: int
    totalEmrs: int
    totalPhrases: int
    durationMs: int


@router.post("/index-doctor", response_model=DoctorIndexResponse)
async def index_doctor_emrs(
    request: DoctorIndexRequest,
    db: Session = Depends(deps.get_db)
) -> DoctorIndexResponse:
    """
    Проиндексировать все EMR одного врача.
    """
    from app.services.emr_phrase_indexer import get_emr_phrase_indexer
    
    indexer = get_emr_phrase_indexer(db)
    
    try:
        result = indexer.index_doctor_emrs(
            doctor_id=request.doctorId,
            specialty=request.specialty
        )
        
        return DoctorIndexResponse(
            success=True,
            doctorId=result.doctor_id,
            totalEmrs=result.total_emrs,
            totalPhrases=result.total_phrases,
            durationMs=result.duration_ms
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Doctor indexing failed: {str(e)}"
        )
