"""
API endpoints для AI функций EMR
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services.emr_ai_service import EMRService, get_emr_ai_service

router = APIRouter()


@router.post("/suggestions/diagnosis")
async def get_diagnosis_suggestions(
    symptoms: List[str],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить предложения диагнозов на основе симптомов"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_diagnosis_suggestions(symptoms, specialty)

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "specialty": specialty,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения предложений диагнозов: {str(e)}"
        )


@router.post("/suggestions/treatment")
async def get_treatment_suggestions(
    diagnosis: str,
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить предложения лечения на основе диагноза"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_treatment_suggestions(diagnosis, specialty)

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "diagnosis": diagnosis,
            "specialty": specialty,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения предложений лечения: {str(e)}"
        )


@router.post("/suggestions/icd10")
async def get_icd10_suggestions(
    diagnosis_text: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить предложения кодов МКБ-10"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_icd10_suggestions(diagnosis_text)

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "diagnosis_text": diagnosis_text,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения кодов МКБ-10: {str(e)}"
        )


@router.post("/auto-fill")
async def auto_fill_emr_fields(
    template_structure: Dict[str, Any],
    patient_data: Dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Автозаполнение полей EMR на основе данных пациента"""
    try:
        ai_service = await get_emr_ai_service()
        filled_data = await ai_service.auto_fill_emr_fields(
            template_structure, patient_data, specialty
        )

        return {
            "filled_data": filled_data,
            "template_structure": template_structure,
            "specialty": specialty,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка автозаполнения EMR: {str(e)}"
        )


@router.post("/validate")
async def validate_emr_data(
    emr_data: Dict[str, Any],
    template_structure: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Валидация данных EMR"""
    try:
        ai_service = await get_emr_ai_service()
        validation_result = await ai_service.validate_emr_data(
            emr_data, template_structure
        )

        return validation_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка валидации EMR: {str(e)}")


@router.post("/suggestions/ai")
async def get_ai_suggestions(
    emr_data: Dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить общие AI предложения для EMR"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_ai_suggestions(emr_data, specialty)

        return {
            "suggestions": suggestions,
            "specialty": specialty,
            "timestamp": "2024-01-01T00:00:00Z",  # Заглушка для времени
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения AI предложений: {str(e)}"
        )


@router.get("/suggestions/health")
async def ai_health_check():
    """Проверка здоровья AI сервиса"""
    return {
        "status": "ok",
        "ai_service": "active",
        "features": [
            "diagnosis_suggestions",
            "treatment_suggestions",
            "icd10_suggestions",
            "auto_fill",
            "validation",
            "ai_suggestions",
        ],
        "providers": ["openai", "anthropic", "local"],
    }


# =============================================================================
# EMR v2 Compatible Endpoint
# =============================================================================

import uuid
from pydantic import BaseModel, Field


class AISuggestionV2(BaseModel):
    """EMR v2 compatible suggestion format"""
    id: str
    targetField: str
    content: str
    confidence: float
    source: str = "AI"
    explanation: Optional[str] = None
    model: str = "mock"


class DoctorContextEntry(BaseModel):
    """Single entry from doctor history"""
    content: Optional[str] = None
    diagnosis: Optional[str] = None
    created_at: Optional[str] = None


class DoctorContext(BaseModel):
    """Doctor history context for better suggestions"""
    doctor_id: Optional[int] = None
    specialty: Optional[str] = None
    field_name: Optional[str] = None
    previous_entries: Optional[List[DoctorContextEntry]] = None
    unique_phrases: Optional[List[str]] = None


class SuggestRequestV2(BaseModel):
    """EMR v2 suggest request"""
    emr_snapshot: Dict[str, Any]
    specialty: str = "general"
    language: str = "ru"
    doctor_context: Optional[DoctorContext] = None


class SuggestResponseV2(BaseModel):
    """EMR v2 suggest response"""
    suggestions: List[AISuggestionV2]
    model: str = "mock"
    specialty: str
    used_doctor_context: bool = False


def generate_v2_suggestions(
    emr_data: Dict[str, Any], 
    specialty: str,
    doctor_context: Optional[DoctorContext] = None,
) -> List[AISuggestionV2]:
    """Generate mock suggestions in EMR v2 format"""
    suggestions = []
    
    complaints = emr_data.get("complaints", "")
    diagnosis = emr_data.get("diagnosis", "")
    icd10 = emr_data.get("icd10_code", "")
    treatment = emr_data.get("treatment", "")
    recommendations = emr_data.get("recommendations", "")
    
    # Use doctor context for better suggestions
    context_phrases = []
    if doctor_context and doctor_context.unique_phrases:
        context_phrases = doctor_context.unique_phrases[:10]
    
    # Diagnosis suggestions (enhanced with doctor context)
    if complaints and not diagnosis:
        # Standard suggestions
        if any(w in complaints.lower() for w in ["головн", "боль", "голова"]):
            suggestions.append(AISuggestionV2(
                id=f"dx-{uuid.uuid4().hex[:8]}",
                targetField="diagnosis",
                content="Цефалгия напряжённого типа",
                confidence=0.65,
                explanation="На основе жалоб на головную боль",
            ))
        if any(w in complaints.lower() for w in ["давлен", "гипертон", "ад"]):
            suggestions.append(AISuggestionV2(
                id=f"dx-{uuid.uuid4().hex[:8]}",
                targetField="diagnosis",
                content="Артериальная гипертензия, II стадия, риск ССО 3",
                confidence=0.72,
                explanation="На основе жалоб на повышенное давление",
            ))
        
        # Add suggestions from doctor context
        for phrase in context_phrases:
            if "диагноз" in phrase.lower() or len(phrase) > 20:
                suggestions.append(AISuggestionV2(
                    id=f"ctx-{uuid.uuid4().hex[:8]}",
                    targetField="diagnosis",
                    content=phrase,
                    confidence=0.55,
                    explanation="На основе вашей истории",
                ))
                break  # Only one context-based suggestion
    
    # ICD-10 suggestions
    if diagnosis and not icd10:
        if "гипертензия" in diagnosis.lower() or "гипертоническая" in diagnosis.lower():
            suggestions.append(AISuggestionV2(
                id=f"icd-{uuid.uuid4().hex[:8]}",
                targetField="icd10_code",
                content="I10",
                confidence=0.85,
                explanation="Эссенциальная [первичная] гипертензия",
            ))
        elif "цефалгия" in diagnosis.lower():
            suggestions.append(AISuggestionV2(
                id=f"icd-{uuid.uuid4().hex[:8]}",
                targetField="icd10_code",
                content="G44.2",
                confidence=0.78,
                explanation="Головная боль напряжённого типа",
            ))
    
    # Recommendations suggestions
    if treatment and not recommendations:
        suggestions.append(AISuggestionV2(
            id=f"rec-{uuid.uuid4().hex[:8]}",
            targetField="recommendations",
            content="Контроль АД 2 раза в день. Ограничение соли. Повторный осмотр через 2 недели.",
            confidence=0.60,
            explanation="Стандартные рекомендации",
        ))
    
    return suggestions


@router.post("/suggest", response_model=SuggestResponseV2)
async def suggest_v2(
    request: SuggestRequestV2,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    EMR v2 compatible AI suggestions endpoint.
    
    Returns suggestions in format expected by useEMRAI hook.
    AI only suggests - doctor must explicitly apply.
    
    Optionally accepts doctor_context for personalized suggestions.
    """
    suggestions = generate_v2_suggestions(
        request.emr_snapshot, 
        request.specialty,
        request.doctor_context,
    )
    
    return SuggestResponseV2(
        suggestions=suggestions,
        model="mock",
        specialty=request.specialty,
        used_doctor_context=request.doctor_context is not None,
    )
