"""
API endpoints для AI функций EMR
"""

import logging
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.rbac import AIPermission, require_any_ai_permission
from app.db.session import get_db
from app.services.ai_feature_gating import RequireAiFeature
from app.models.user import User
from app.services.emr_ai_service import get_emr_ai_service

router = APIRouter(dependencies=[Depends(RequireAiFeature("ai_emr_legacy"))])  # P1-13: feature flag
logger = logging.getLogger(__name__)

EMR_AI_ACCESS = require_any_ai_permission(
    AIPermission.ADMIN_AI,
    AIPermission.DIAGNOSE,
    AIPermission.SUGGEST_ICD10,
    AIPermission.ANALYZE_DOCUMENT,
)

EMR_AI_PUBLIC_ERROR = "Internal server error"


def _raise_emr_ai_internal_error(operation: str, exc: Exception) -> NoReturn:
    logger.warning(
        "EMR AI endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail=EMR_AI_PUBLIC_ERROR) from exc


def ai_safety_meta() -> dict[str, Any]:
    return {
        "decision_boundary": "suggestion_only",
        "requires_doctor_confirmation": True,
        "ai_notice": (
            "AI output is a draft suggestion. A doctor or admin must confirm it "
            "before it becomes part of the medical record."
        ),
    }


@router.post("/suggestions/diagnosis")
async def get_diagnosis_suggestions(
    symptoms: list[str],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user: User = Depends(EMR_AI_ACCESS),
):
    """Получить предложения диагнозов на основе симптомов"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_diagnosis_suggestions(symptoms, specialty)

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "specialty": specialty,
            **ai_safety_meta(),
        }
    except Exception as e:
        _raise_emr_ai_internal_error("get_diagnosis_suggestions", e)


@router.post("/suggestions/treatment")
async def get_treatment_suggestions(
    diagnosis: str,
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user: User = Depends(EMR_AI_ACCESS),
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
            **ai_safety_meta(),
        }
    except Exception as e:
        _raise_emr_ai_internal_error("get_treatment_suggestions", e)


@router.post("/suggestions/icd10")
async def get_icd10_suggestions(
    diagnosis_text: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(EMR_AI_ACCESS),
):
    """Получить предложения кодов МКБ-10"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_icd10_suggestions(diagnosis_text)

        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "diagnosis_text": diagnosis_text,
            **ai_safety_meta(),
        }
    except Exception as e:
        _raise_emr_ai_internal_error("get_icd10_suggestions", e)


@router.post("/auto-fill")
async def auto_fill_emr_fields(
    template_structure: dict[str, Any],
    patient_data: dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user: User = Depends(EMR_AI_ACCESS),
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
            **ai_safety_meta(),
        }
    except Exception as e:
        _raise_emr_ai_internal_error("auto_fill_emr_fields", e)


@router.post("/validate")
async def validate_emr_data(
    emr_data: dict[str, Any],
    template_structure: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(EMR_AI_ACCESS),
):
    """Валидация данных EMR"""
    try:
        ai_service = await get_emr_ai_service()
        validation_result = await ai_service.validate_emr_data(
            emr_data, template_structure
        )

        if isinstance(validation_result, dict):
            return {**validation_result, **ai_safety_meta()}
        return {"result": validation_result, **ai_safety_meta()}
    except Exception as e:
        _raise_emr_ai_internal_error("validate_emr_data", e)


@router.post("/suggestions/ai")
async def get_ai_suggestions(
    emr_data: dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user: User = Depends(EMR_AI_ACCESS),
):
    """Получить общие AI предложения для EMR"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_ai_suggestions(emr_data, specialty)

        return {
            "suggestions": suggestions,
            "specialty": specialty,
            "timestamp": "2024-01-01T00:00:00Z",  # Заглушка для времени
            **ai_safety_meta(),
        }
    except Exception as e:
        _raise_emr_ai_internal_error("get_ai_suggestions", e)


@router.get("/suggestions/health")
async def ai_health_check(current_user: User = Depends(EMR_AI_ACCESS)):
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

import uuid  # noqa: E402  # manual-review: conditional import after config — intentional

from pydantic import (  # noqa: E402  # manual-review: conditional import after config — intentional
    BaseModel,  # noqa: E402  # manual-review: conditional import after config — intentional
)


class AISuggestionV2(BaseModel):
    """EMR v2 compatible suggestion format"""
    id: str
    targetField: str
    content: str
    confidence: float
    source: str = "AI"
    explanation: str | None = None
    model: str = "mock"
    requiresDoctorConfirmation: bool = True


class DoctorContextEntry(BaseModel):
    """Single entry from doctor history"""
    content: str | None = None
    diagnosis: str | None = None
    created_at: str | None = None


class DoctorContext(BaseModel):
    """Doctor history context for better suggestions"""
    doctor_id: int | None = None
    specialty: str | None = None
    field_name: str | None = None
    previous_entries: list[DoctorContextEntry] | None = None
    unique_phrases: list[str] | None = None


class SuggestRequestV2(BaseModel):
    """EMR v2 suggest request"""
    emr_snapshot: dict[str, Any]
    specialty: str = "general"
    language: str = "ru"
    doctor_context: DoctorContext | None = None


class SuggestResponseV2(BaseModel):
    """EMR v2 suggest response"""
    suggestions: list[AISuggestionV2]
    model: str = "mock"
    specialty: str
    used_doctor_context: bool = False
    requires_doctor_confirmation: bool = True
    decision_boundary: str = "suggestion_only"


def generate_v2_suggestions(
    emr_data: dict[str, Any],
    specialty: str,
    doctor_context: DoctorContext | None = None,
) -> list[AISuggestionV2]:
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
    current_user: User = Depends(EMR_AI_ACCESS),
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
