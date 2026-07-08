"""
API endpoints для AI интеграции в панелях врачей
Основа: passport.md стр. 3325-3888, detail.md стр. 3889-4282

P0-5 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `request: dict[str, Any]` with no
validation, allowing prompt injection, mass-assignment, and schema drift.
Replaced with typed Pydantic request models from app.schemas.ai_gateway.
"""

import logging
from datetime import datetime, UTC
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services.ai_feature_gating import RequireAiFeature
from app.api.deps import get_db, require_roles
from app.crud import ai_config as crud_ai
from app.models.user import User
from app.schemas.ai_gateway import (
    AnalyzeComplaintsIntegrationRequest,
    AnalyzeDocumentIntegrationRequest,
    InterpretLabResultsIntegrationRequest,
    QuickDiagnosisHelpRequest,
    SuggestICD10IntegrationRequest,
    SymptomCheckerRequest,
)
from app.services.ai_service import get_ai_service

router = APIRouter(dependencies=[Depends(RequireAiFeature("ai_integration"))])  # P1-13: feature flag
logger = logging.getLogger(__name__)

AI_INTEGRATION_PUBLIC_ERROR = "Internal server error"


def _ai_integration_http_error(exc: Exception, operation: str) -> HTTPException:
    logger.warning(
        "AI integration endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=AI_INTEGRATION_PUBLIC_ERROR,
    )


# ===================== АНАЛИЗ ЖАЛОБ ПАЦИЕНТОВ =====================


@router.post("/analyze-complaints", response_model=dict[str, Any])
async def analyze_patient_complaints(
    request: AnalyzeComplaintsIntegrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """
    Анализ жалоб пациента с помощью AI
    Из passport.md стр. 3325: жалобы → план обследования
    """
    try:
        # Use `complaints` field; fall back to `complaint` if only that's provided
        complaints_text = request.complaints or request.complaint or ""

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_complaints(
                complaints_text=complaints_text,
                specialty=request.specialty,
                language=request.language,
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise _ai_integration_http_error(e, "analyze_patient_complaints") from e


# ===================== ПОДБОР КОДОВ МКБ-10 =====================


@router.post("/suggest-icd10", response_model=dict[str, Any])
async def suggest_icd10_codes(
    request: SuggestICD10IntegrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """
    Автоподбор кодов МКБ-10 по диагнозу
    Из passport.md стр. 3456: автоматический подбор МКБ-10
    """
    try:
        async with await get_ai_service(db) as ai_service:
            result = await ai_service.suggest_icd10(
                diagnosis=request.diagnosis,
                specialty=request.specialty,
                language=request.language,
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise _ai_integration_http_error(e, "suggest_icd10_codes") from e


# ===================== АНАЛИЗ ДОКУМЕНТОВ =====================


@router.post("/analyze-document", response_model=dict[str, Any])
async def analyze_medical_document(
    request: AnalyzeDocumentIntegrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """
    Анализ медицинских документов
    Из passport.md стр. 3678: анализ документов и извлечение данных
    """
    try:
        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_document(
                document_text=request.document_text,
                document_type=request.document_type,
                specialty=request.specialty,
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise _ai_integration_http_error(e, "analyze_medical_document") from e


# ===================== ИНТЕРПРЕТАЦИЯ ЛАБОРАТОРНЫХ АНАЛИЗОВ =====================


@router.post("/interpret-lab-results", response_model=dict[str, Any])
async def interpret_lab_results(
    request: InterpretLabResultsIntegrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """
    Интерпретация результатов лабораторных анализов
    Из passport.md стр. 3567: AI анализ лабораторных данных
    """
    try:
        # Формируем текст для анализа
        if isinstance(request.lab_results, list):
            results_text = "\\n".join(
                [
                    f"{(item.parameter or item.name or '')}: {item.value or ''} {item.unit or ''}"
                    for item in request.lab_results
                ]
            )
        else:
            results_text = str(request.lab_results)

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_document(
                document_text=results_text,
                document_type="lab_results",
                specialty=request.specialty,
            )

            # Дополняем контекстом пациента
            if isinstance(result, dict) and result.get("success"):
                result["patient_context"] = {
                    "age": request.patient_age,
                    "gender": request.patient_gender,
                    "specialty": request.specialty,
                }

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise _ai_integration_http_error(e, "interpret_lab_results") from e


# ===================== ПОМОЩЬ ПО СИМПТОМАМ =====================


@router.post("/symptom-checker", response_model=dict[str, Any])
async def check_symptoms(
    request: SymptomCheckerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Проверка симптомов и предварительные рекомендации
    Помощь для триажа в регистратуре
    """
    try:
        # Формируем текст симптомов
        symptoms_text = "\\n".join([f"• {symptom}" for symptom in request.symptoms])

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_complaints(
                complaints_text=f"Симптомы:\\n{symptoms_text}", specialty="general"
            )

            if isinstance(result, dict) and result.get("success"):
                # Добавляем рекомендации по триажу
                result["triage_recommendations"] = {
                    "urgency_level": "medium",  # low, medium, high, critical
                    "recommended_specialist": "therapist",
                    "additional_questions": [
                        "Как давно появились симптомы?",
                        "Есть ли хронические заболевания?",
                        "Принимаете ли лекарства?",
                    ],
                }

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise _ai_integration_http_error(e, "check_symptoms") from e


# ===================== СТАТИСТИКА AI =====================


@router.get("/usage-stats", response_model=dict[str, Any])
def get_ai_usage_stats(
    days_back: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Статистика использования AI
    """
    try:
        from datetime import date, timedelta

        start_date = date.today() - timedelta(days=days_back)

        # Получаем логи использования
        logs = crud_ai.get_usage_logs(db, start_date=start_date)

        # Группируем по провайдерам и типам задач
        stats = {
            "total_requests": len(logs),
            "by_provider": {},
            "by_task_type": {},
            "by_day": {},
            "total_tokens": {
                "input": sum(log.input_tokens or 0 for log in logs),
                "output": sum(log.output_tokens or 0 for log in logs),
            },
        }

        for log in logs:
            # По провайдерам
            provider_name = log.provider.name if log.provider else "unknown"
            stats["by_provider"][provider_name] = (
                stats["by_provider"].get(provider_name, 0) + 1
            )

            # По типам задач
            task_type = log.task_type
            stats["by_task_type"][task_type] = (
                stats["by_task_type"].get(task_type, 0) + 1
            )

            # По дням
            day = log.created_at.date().isoformat()
            stats["by_day"][day] = stats["by_day"].get(day, 0) + 1

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": date.today().isoformat(),
                "days": days_back,
            },
            "statistics": stats,
        }

    except Exception as e:
        raise _ai_integration_http_error(e, "get_ai_usage_stats") from e


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/diagnosis-help", response_model=dict[str, Any])
async def quick_diagnosis_help(
    request: QuickDiagnosisHelpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """
    Быстрая помощь с диагнозом
    """
    try:
        symptoms = request.symptoms
        current_diagnosis = request.current_diagnosis

        # Объединяем симптомы и предварительный диагноз
        combined_text = f"Симптомы: {symptoms}"
        if current_diagnosis:
            combined_text += f"\\nПредварительный диагноз: {current_diagnosis}"

        async with await get_ai_service(db) as ai_service:
            # Анализируем жалобы
            complaints_result = await ai_service.analyze_complaints(
                complaints_text=combined_text,
                specialty=(
                    current_user.role
                    if current_user.role in ["cardio", "derma", "dentist"]
                    else "general"
                ),
            )

            # Подбираем МКБ-10 если есть диагноз
            icd10_result = None
            if current_diagnosis:
                icd10_result = await ai_service.suggest_icd10(
                    diagnosis=current_diagnosis,
                    specialty=(
                        current_user.role
                        if current_user.role in ["cardio", "derma", "dentist"]
                        else "general"
                    ),
                )

            return {
                "complaints_analysis": complaints_result,
                "icd10_suggestions": icd10_result,
                "doctor": {
                    "name": current_user.full_name,
                    "specialty": current_user.role,
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }

    except Exception as e:
        raise _ai_integration_http_error(e, "quick_diagnosis_help") from e
