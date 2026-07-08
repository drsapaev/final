"""
Расширенные API endpoints для EMR с AI интеграцией
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import emr
from app.models.user import User
from app.services.emr_ai_enhanced import emr_ai_enhanced
from app.schemas.misc_endpoints import (
    EmrAiCurrentDataRequest,
    EmrAiDoctorPreferencesRequest,
    EmrAiEmrDataRequest,
    EmrAiPatientDataRequest,
    EmrAiTemplateDataRequest,
)
from app.services.ai_feature_gating import RequireAiFeature

router = APIRouter()


def ai_safety_meta() -> dict[str, Any]:
    return {
        "decision_boundary": "suggestion_only",
        "requires_doctor_confirmation": True,
        "ai_notice": (
            "AI output is a draft suggestion. A doctor or admin must confirm it "
            "before it becomes part of the medical record."
        ),
    }


@router.post("/generate-smart-template", dependencies=[Depends(RequireAiFeature("ai_smart_template"))], response_model=Any)
async def generate_smart_template(
    specialty: str = Query(..., description="Специализация врача"),
    patient_data: EmrAiPatientDataRequest = EmrAiPatientDataRequest(),
    doctor_preferences: EmrAiDoctorPreferencesRequest | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Генерация умного шаблона EMR на основе данных пациента"""
    try:
        # patient_data is now a Pydantic model (defaults to empty dict)
        template = await emr_ai_enhanced.generate_smart_template(
            specialty=specialty,
            patient_data=patient_data.model_dump(exclude_none=True),
            doctor_preferences=doctor_preferences.model_dump(exclude_none=True) if doctor_preferences else None,
        )

        return {
            "template": template,
            "specialty": specialty,
            "generated_at": "2024-01-01T00:00:00Z",
            **ai_safety_meta(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/smart-suggestions", dependencies=[Depends(RequireAiFeature("ai_smart_suggestions"))], response_model=Any)
async def get_smart_suggestions(
    field_name: str = Query(..., description="Название поля"),
    current_data: EmrAiCurrentDataRequest = EmrAiCurrentDataRequest(),
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить умные подсказки для поля EMR"""
    try:
        # current_data is now a Pydantic model (defaults to empty dict)
        suggestions = await emr_ai_enhanced.get_smart_suggestions(
            current_data=current_data.model_dump(exclude_none=True), field_name=field_name, specialty=specialty
        )

        return {
            "field_name": field_name,
            "suggestions": suggestions,
            "count": len(suggestions),
            **ai_safety_meta(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/auto-fill", dependencies=[Depends(RequireAiFeature("ai_smart_template"))], response_model=Any)
async def auto_fill_emr_fields(
    template_structure: EmrAiTemplateDataRequest,
    patient_data: EmrAiPatientDataRequest,
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Автоматическое заполнение полей EMR"""
    try:
        filled_data = await emr_ai_enhanced.auto_fill_emr_fields(
            template_structure=template_structure.model_dump(exclude_none=True),
            patient_data=patient_data.model_dump(exclude_none=True),
            specialty=specialty,
        )

        return {
            "filled_data": filled_data,
            "filled_fields": list(filled_data.keys()),
            "count": len(filled_data),
            **ai_safety_meta(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/validate", dependencies=[Depends(RequireAiFeature("ai_smart_template"))], response_model=Any)
async def validate_emr_data(
    emr_data: EmrAiEmrDataRequest,
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Валидация данных EMR с AI подсказками"""
    try:
        validation_result = await emr_ai_enhanced.validate_emr_data(
            emr_data=emr_data.model_dump(exclude_none=True), specialty=specialty
        )

        if isinstance(validation_result, dict):
            return {**validation_result, **ai_safety_meta()}
        return {"result": validation_result, **ai_safety_meta()}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/icd10-suggestions", dependencies=[Depends(RequireAiFeature("ai_icd10_suggestion"))], response_model=Any)
async def get_icd10_suggestions(
    diagnosis_text: str = Query(..., description="Текст диагноза"),
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить предложения ICD-10 кодов"""
    try:
        suggestions = await emr_ai_enhanced.generate_icd10_suggestions(
            diagnosis_text=diagnosis_text, specialty=specialty
        )

        return {
            "diagnosis_text": diagnosis_text,
            "suggestions": suggestions,
            "count": len(suggestions),
            **ai_safety_meta(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/analyze-patient", dependencies=[Depends(RequireAiFeature("ai_smart_template"))], response_model=Any)
async def analyze_patient_data(
    patient_data: EmrAiPatientDataRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Анализ данных пациента для персонализации EMR"""
    try:
        analysis = await emr_ai_enhanced._analyze_patient_data(patient_data.model_dump(exclude_none=True))

        return {
            "analysis": analysis,
            "risk_factors": analysis.get("risk_factors", []),
            "age_group": analysis.get("age_group", "unknown"),
            "recommendations": await emr_ai_enhanced._generate_improvement_suggestions(
                patient_data, "general"
            ),
            **ai_safety_meta(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/templates/specialty/{specialty}", response_model=Any)
async def get_specialty_templates(
    specialty: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить шаблоны для конкретной специализации"""
    try:
        template = emr_ai_enhanced.specialty_templates.get(
            specialty, emr_ai_enhanced.specialty_templates["general"]
        )

        return {
            "specialty": specialty,
            "template": template,
            "fields": list(template.keys()),
            "field_count": len(template),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/emr/{emr_id}/ai-enhance", dependencies=[Depends(RequireAiFeature("ai_smart_template"))], response_model=Any)
async def enhance_emr_with_ai(
    emr_id: int,
    enhancement_type: str = Query(
        ..., description="Тип улучшения: suggestions, validation, auto_fill"
    ),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Улучшить EMR с помощью AI"""
    try:
        # Получаем EMR из базы данных
        emr_record = emr.get(db, id=emr_id)
        if not emr_record:
            raise HTTPException(status_code=404, detail="EMR не найден")

        emr_data = {
            "complaints": emr_record.complaints,
            "anamnesis": emr_record.anamnesis,
            "examination": emr_record.examination,
            "diagnosis": emr_record.diagnosis,
            "icd10": emr_record.icd10,
            "recommendations": emr_record.recommendations,
        }

        result = {}

        if enhancement_type == "suggestions":
            # Получаем подсказки для всех полей
            for field_name in ["complaints", "diagnosis", "treatment"]:
                suggestions = await emr_ai_enhanced.get_smart_suggestions(
                    current_data=emr_data,
                    field_name=field_name,
                    specialty=emr_record.specialty or "general",
                )
                result[field_name] = suggestions

        elif enhancement_type == "validation":
            # Валидируем данные
            result = await emr_ai_enhanced.validate_emr_data(
                emr_data=emr_data, specialty=emr_record.specialty or "general"
            )

        elif enhancement_type == "auto_fill":
            # Автозаполнение недостающих полей
            template = emr_ai_enhanced.specialty_templates.get(
                emr_record.specialty or "general",
                emr_ai_enhanced.specialty_templates["general"],
            )
            result = await emr_ai_enhanced.auto_fill_emr_fields(
                template_structure=template,
                patient_data=emr_data,
                specialty=emr_record.specialty or "general",
            )

        return {
            "emr_id": emr_id,
            "enhancement_type": enhancement_type,
            "result": result,
            "enhanced_at": "2024-01-01T00:00:00Z",
            **ai_safety_meta(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics/quality", response_model=Any)
async def get_emr_quality_analytics(
    specialty: str | None = Query(None, description="Фильтр по специализации"),
    date_from: str | None = Query(None, description="Дата начала"),
    date_to: str | None = Query(None, description="Дата окончания"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить аналитику качества EMR записей"""
    try:
        # Здесь будет реальная аналитика
        # Пока возвращаем заглушку
        analytics = {
            "total_emr": 150,
            "complete_emr": 120,
            "incomplete_emr": 30,
            "quality_score": 85.5,
            "common_issues": [
                "Отсутствует код МКБ-10",
                "Неполное описание симптомов",
                "Отсутствуют рекомендации",
            ],
            "improvement_suggestions": [
                "Использовать AI подсказки для заполнения полей",
                "Включить валидацию в реальном времени",
                "Добавить шаблоны для часто используемых диагнозов",
            ],
        }

        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )
