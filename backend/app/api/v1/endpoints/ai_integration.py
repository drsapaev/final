"""
API endpoints для AI интеграции в панелях врачей
Основа: passport.md стр. 3325-3888, detail.md стр. 3889-4282
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import ai_config as crud_ai
from app.models.user import User
from app.services.ai_service import AIService, get_ai_service

router = APIRouter()

# ===================== АНАЛИЗ ЖАЛОБ ПАЦИЕНТОВ =====================


@router.post("/analyze-complaints")
async def analyze_patient_complaints(
    request: Dict[str, Any],
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
        complaints_text = request.get("complaints")
        specialty = request.get("specialty", "general")
        language = request.get("language", "ru")

        if not complaints_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Текст жалоб не указан"
            )

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_complaints(
                complaints_text=complaints_text, specialty=specialty, language=language
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка анализа жалоб: {str(e)}",
        )


# ===================== ПОДБОР КОДОВ МКБ-10 =====================


@router.post("/suggest-icd10")
async def suggest_icd10_codes(
    request: Dict[str, Any],
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
        diagnosis = request.get("diagnosis")
        specialty = request.get("specialty", "general")
        language = request.get("language", "ru")

        if not diagnosis:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Диагноз не указан"
            )

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.suggest_icd10(
                diagnosis=diagnosis, specialty=specialty, language=language
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подбора МКБ-10: {str(e)}",
        )


# ===================== АНАЛИЗ ДОКУМЕНТОВ =====================


@router.post("/analyze-document")
async def analyze_medical_document(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """
    Анализ медицинских документов
    Из passport.md стр. 3678: анализ документов и извлечение данных
    """
    try:
        document_text = request.get("document_text")
        document_type = request.get("document_type", "medical_report")
        specialty = request.get("specialty", "general")

        if not document_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Текст документа не указан",
            )

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_document(
                document_text=document_text,
                document_type=document_type,
                specialty=specialty,
            )

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка анализа документа: {str(e)}",
        )


# ===================== ИНТЕРПРЕТАЦИЯ ЛАБОРАТОРНЫХ АНАЛИЗОВ =====================


@router.post("/interpret-lab-results")
async def interpret_lab_results(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """
    Интерпретация результатов лабораторных анализов
    Из passport.md стр. 3567: AI анализ лабораторных данных
    """
    try:
        lab_results = request.get("lab_results")
        patient_age = request.get("patient_age")
        patient_gender = request.get("patient_gender", "unknown")
        specialty = request.get("specialty", "general")

        if not lab_results:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Результаты анализов не указаны",
            )

        # Формируем текст для анализа
        if isinstance(lab_results, list):
            results_text = "\\n".join(
                [
                    f"{result.get('parameter', '')}: {result.get('value', '')} {result.get('unit', '')}"
                    for result in lab_results
                ]
            )
        else:
            results_text = str(lab_results)

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_document(
                document_text=results_text,
                document_type="lab_results",
                specialty=specialty,
            )

            # Дополняем контекстом пациента
            if result.get("success"):
                result["patient_context"] = {
                    "age": patient_age,
                    "gender": patient_gender,
                    "specialty": specialty,
                }

            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка интерпретации анализов: {str(e)}",
        )


# ===================== ПОМОЩЬ ПО СИМПТОМАМ =====================


@router.post("/symptom-checker")
async def check_symptoms(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Проверка симптомов и предварительные рекомендации
    Помощь для триажа в регистратуре
    """
    try:
        symptoms = request.get("symptoms", [])
        patient_age = request.get("patient_age")
        patient_gender = request.get("patient_gender", "unknown")

        if not symptoms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Симптомы не указаны"
            )

        # Формируем текст симптомов
        symptoms_text = "\\n".join([f"• {symptom}" for symptom in symptoms])

        async with await get_ai_service(db) as ai_service:
            result = await ai_service.analyze_complaints(
                complaints_text=f"Симптомы:\\n{symptoms_text}", specialty="general"
            )

            if result.get("success"):
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки симптомов: {str(e)}",
        )


# ===================== СТАТИСТИКА AI =====================


@router.get("/usage-stats")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики AI: {str(e)}",
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/diagnosis-help")
async def quick_diagnosis_help(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """
    Быстрая помощь с диагнозом
    """
    try:
        symptoms = request.get("symptoms", "")
        current_diagnosis = request.get("current_diagnosis", "")

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
                "timestamp": datetime.utcnow().isoformat(),
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка AI помощи: {str(e)}",
        )
