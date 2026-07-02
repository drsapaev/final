"""
AI Gateway Endpoints - Унифицированный API для всех AI операций.

Все AI запросы должны проходить через эти endpoints.
Обеспечивает:
- Единый контракт ответов (AIResponse)
- RBAC через permissions
- Rate limiting
- Аудит
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.rbac import (
    AIPermission,
    require_ai_permission,
    require_any_ai_permission,
)
from app.models.user import User
from app.services.ai import (
    AIResponse,
    AITaskType,
    get_ai_gateway,
)

router = APIRouter()


# =============================================================================
# DIAGNOSTIC ENDPOINTS (Requires DIAGNOSE permission)
# =============================================================================

@router.post("/analyze-complaints", response_model=AIResponse)
async def analyze_complaints(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.DIAGNOSE)),
    db: Session = Depends(get_db)
):
    """
    Анализ жалоб пациента → план обследования.
    
    Requires: DIAGNOSE permission (Doctor, Cardiologist, Dermatologist, Dentist)
    
    Request body:
    {
        "complaint": "Головная боль, тошнота, температура 38.5",
        "patient_age": 35,
        "patient_gender": "male",
        "specialty": "general"  // optional
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.COMPLAINT_ANALYSIS,
        payload=request,
        user_id=current_user.id,
        specialty=request.get("specialty")
    )
    
    return response


@router.post("/suggest-icd10", response_model=AIResponse)
async def suggest_icd10(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.SUGGEST_ICD10)),
    db: Session = Depends(get_db)
):
    """
    Подбор кодов МКБ-10 по симптомам/диагнозу.
    
    Requires: SUGGEST_ICD10 permission
    
    Request body:
    {
        "symptoms": ["головная боль", "повышенное давление"],
        "diagnosis": "Артериальная гипертензия"  // optional
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.ICD10_SUGGESTION,
        payload=request,
        user_id=current_user.id
    )
    
    return response


@router.post("/differential-diagnosis", response_model=AIResponse)
async def differential_diagnosis(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.DIAGNOSE)),
    db: Session = Depends(get_db)
):
    """
    Дифференциальная диагностика.
    
    Requires: DIAGNOSE permission
    
    Request body:
    {
        "symptoms": ["боль в груди", "одышка", "потливость"],
        "patient_age": 55,
        "patient_gender": "male"
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.DIFFERENTIAL_DIAGNOSIS,
        payload=request,
        user_id=current_user.id
    )
    
    return response


# =============================================================================
# LAB INTERPRETATION (Requires ANALYZE_LAB permission)
# =============================================================================

@router.post("/interpret-lab", response_model=AIResponse)
async def interpret_lab_results(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.ANALYZE_LAB)),
    db: Session = Depends(get_db)
):
    """
    Интерпретация лабораторных результатов.
    
    Requires: ANALYZE_LAB permission (Doctor, Lab)
    
    Request body:
    {
        "results": [
            {"name": "Гемоглобин", "value": 120, "unit": "г/л", "reference": "130-160"},
            {"name": "Лейкоциты", "value": 12.5, "unit": "×10⁹/л", "reference": "4-9"}
        ],
        "patient_age": 45,
        "patient_gender": "female"
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.LAB_INTERPRETATION,
        payload=request,
        user_id=current_user.id
    )
    
    return response


# =============================================================================
# IMAGE ANALYSIS (Requires ANALYZE_IMAGE permission)
# =============================================================================

@router.post("/analyze-skin", response_model=AIResponse)
async def analyze_skin(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.ANALYZE_IMAGE)),
    db: Session = Depends(get_db)
):
    """
    Анализ кожного образования.
    
    Requires: ANALYZE_IMAGE permission (Doctor, Dermatologist)
    
    Request body:
    {
        "image_data": "<base64 encoded image>",
        "metadata": {
            "location": "спина",
            "duration": "3 месяца",
            "changes": "увеличивается"
        }
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.SKIN_ANALYSIS,
        payload=request,
        user_id=current_user.id,
        specialty="dermatology"
    )
    
    return response


@router.post("/analyze-ecg", response_model=AIResponse)
async def analyze_ecg(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.ANALYZE_IMAGE)),
    db: Session = Depends(get_db)
):
    """
    Интерпретация ЭКГ.
    
    Requires: ANALYZE_IMAGE permission
    
    Request body:
    {
        "ecg_data": {
            "heart_rate": 72,
            "rhythm": "синусовый",
            "intervals": {"PR": 0.16, "QRS": 0.08, "QT": 0.38}
        },
        "patient_age": 60,
        "patient_gender": "male"
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.ECG_INTERPRETATION,
        payload=request,
        user_id=current_user.id,
        specialty="cardiology"
    )
    
    return response


# =============================================================================
# TRIAGE (Requires SYMPTOM_CHECK permission)
# =============================================================================

@router.post("/symptom-check", response_model=AIResponse)
async def symptom_check(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.SYMPTOM_CHECK)),
    db: Session = Depends(get_db)
):
    """
    Проверка симптомов для триажа.
    
    Requires: SYMPTOM_CHECK permission (Registrar, Nurse)
    
    This is a LIMITED analysis for triage purposes only.
    Does NOT provide diagnosis or treatment.
    
    Request body:
    {
        "symptoms": ["боль в груди", "одышка"],
        "duration": "2 часа",
        "severity": "сильная"
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.SYMPTOM_CHECK,
        payload=request,
        user_id=current_user.id
    )
    
    # Add explicit disclaimer for triage
    response.warnings.append(
        "Это предварительная оценка для триажа. "
        "Не является диагнозом. Требуется осмотр врача."
    )
    
    return response


# =============================================================================
# DOCUMENT ANALYSIS (Requires ANALYZE_DOCUMENT permission)
# =============================================================================

@router.post("/analyze-document", response_model=AIResponse)
async def analyze_document(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.ANALYZE_DOCUMENT)),
    db: Session = Depends(get_db)
):
    """
    Анализ медицинского документа.
    
    Requires: ANALYZE_DOCUMENT permission (Doctor)
    
    Request body:
    {
        "document_text": "Заключение УЗИ органов брюшной полости...",
        "document_type": "ultrasound_report"
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.DOCUMENT_ANALYSIS,
        payload=request,
        user_id=current_user.id
    )
    
    return response


# =============================================================================
# DRUG INTERACTIONS (Requires DIAGNOSE permission)
# =============================================================================

@router.post("/drug-interaction", response_model=AIResponse)
async def check_drug_interaction(
    request: Dict[str, Any],
    current_user: User = Depends(require_ai_permission(AIPermission.DIAGNOSE)),
    db: Session = Depends(get_db)
):
    """
    Проверка лекарственных взаимодействий.
    
    Requires: DIAGNOSE permission
    
    Request body:
    {
        "medications": ["Аспирин", "Варфарин", "Омепразол"]
    }
    """
    gateway = get_ai_gateway()
    
    response = await gateway.execute(
        task_type=AITaskType.DRUG_INTERACTION,
        payload=request,
        user_id=current_user.id
    )
    
    return response


# =============================================================================
# HEALTH & ADMIN ENDPOINTS
# =============================================================================

@router.get("/health")
async def ai_health_check(
    current_user: User = Depends(require_any_ai_permission(
        AIPermission.ADMIN_AI, AIPermission.VIEW_STATS
    ))
):
    """
    Проверка здоровья AI подсистемы.
    
    Requires: ADMIN_AI or VIEW_STATS permission
    """
    gateway = get_ai_gateway()
    return await gateway.health_check()


@router.get("/rate-limit-status")
async def get_rate_limit_status(
    current_user: User = Depends(require_ai_permission(AIPermission.DIAGNOSE)),
    db: Session = Depends(get_db)
):
    """
    Статус rate limit для текущего пользователя.
    """
    from app.services.ai import get_rate_limiter
    
    limiter = get_rate_limiter()
    return limiter.get_user_usage(current_user.id)


@router.post("/admin/reset-circuit-breaker")
async def reset_circuit_breaker(
    provider: str = Query(..., description="Provider name (openai, gemini, deepseek)"),
    current_user: User = Depends(require_ai_permission(AIPermission.ADMIN_AI)),
    db: Session = Depends(get_db)
):
    """
    Сброс circuit breaker для провайдера.
    
    Requires: ADMIN_AI permission
    
    Use when provider is recovered after outage.
    """
    gateway = get_ai_gateway()
    gateway.reset_circuit_breaker(provider)
    
    return {
        "message": f"Circuit breaker reset for {provider}",
        "status": "success"
    }


@router.post("/admin/clear-cache")
async def clear_ai_cache(
    current_user: User = Depends(require_ai_permission(AIPermission.ADMIN_AI)),
    db: Session = Depends(get_db)
):
    """
    Очистка кэша AI ответов.
    
    Requires: ADMIN_AI permission
    """
    gateway = get_ai_gateway()
    gateway.clear_cache()
    
    return {
        "message": "AI cache cleared",
        "status": "success"
    }
