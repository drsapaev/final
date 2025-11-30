"""
Расширенные API endpoints для EMR с AI интеграцией
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import emr
from app.models.user import User
from app.schemas.emr import EMRCreate, EMRUpdate
from app.services.emr_ai_enhanced import emr_ai_enhanced

router = APIRouter()


@router.post("/generate-smart-template")
async def generate_smart_template(
    specialty: str = Query(..., description="Специализация врача"),
    patient_data: Dict[str, Any] = None,
    doctor_preferences: Optional[Dict[str, Any]] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Генерация умного шаблона EMR на основе данных пациента"""
    try:
        if patient_data is None:
            patient_data = {}

        template = await emr_ai_enhanced.generate_smart_template(
            specialty=specialty,
            patient_data=patient_data,
            doctor_preferences=doctor_preferences,
        )

        return {
            "template": template,
            "specialty": specialty,
            "generated_at": "2024-01-01T00:00:00Z",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка генерации шаблона: {str(e)}"
        )


@router.post("/smart-suggestions")
async def get_smart_suggestions(
    field_name: str = Query(..., description="Название поля"),
    current_data: Dict[str, Any] = None,
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить умные подсказки для поля EMR"""
    try:
        if current_data is None:
            current_data = {}

        suggestions = await emr_ai_enhanced.get_smart_suggestions(
            current_data=current_data, field_name=field_name, specialty=specialty
        )

        return {
            "field_name": field_name,
            "suggestions": suggestions,
            "count": len(suggestions),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения подсказок: {str(e)}"
        )


@router.post("/auto-fill")
async def auto_fill_emr_fields(
    template_structure: Dict[str, Any],
    patient_data: Dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Автоматическое заполнение полей EMR"""
    try:
        filled_data = await emr_ai_enhanced.auto_fill_emr_fields(
            template_structure=template_structure,
            patient_data=patient_data,
            specialty=specialty,
        )

        return {
            "filled_data": filled_data,
            "filled_fields": list(filled_data.keys()),
            "count": len(filled_data),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка автозаполнения: {str(e)}")


@router.post("/validate")
async def validate_emr_data(
    emr_data: Dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Валидация данных EMR с AI подсказками"""
    try:
        validation_result = await emr_ai_enhanced.validate_emr_data(
            emr_data=emr_data, specialty=specialty
        )

        return validation_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка валидации: {str(e)}")


@router.post("/icd10-suggestions")
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
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка генерации ICD-10 предложений: {str(e)}"
        )


@router.post("/analyze-patient")
async def analyze_patient_data(
    patient_data: Dict[str, Any],
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Анализ данных пациента для персонализации EMR"""
    try:
        analysis = await emr_ai_enhanced._analyze_patient_data(patient_data)

        return {
            "analysis": analysis,
            "risk_factors": analysis.get("risk_factors", []),
            "age_group": analysis.get("age_group", "unknown"),
            "recommendations": await emr_ai_enhanced._generate_improvement_suggestions(
                patient_data, "general"
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка анализа пациента: {str(e)}"
        )


@router.get("/templates/specialty/{specialty}")
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
            status_code=500, detail=f"Ошибка получения шаблонов: {str(e)}"
        )


@router.post("/emr/{emr_id}/ai-enhance")
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
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка улучшения EMR: {str(e)}")


@router.get("/analytics/quality")
async def get_emr_quality_analytics(
    specialty: Optional[str] = Query(None, description="Фильтр по специализации"),
    date_from: Optional[str] = Query(None, description="Дата начала"),
    date_to: Optional[str] = Query(None, description="Дата окончания"),
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
            status_code=500, detail=f"Ошибка получения аналитики: {str(e)}"
        )
