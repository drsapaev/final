"""
API endpoints для AI функций EMR
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.emr_ai_service import get_emr_ai_service, EMRService

router = APIRouter()


@router.post("/suggestions/diagnosis")
async def get_diagnosis_suggestions(
    symptoms: List[str],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить предложения диагнозов на основе симптомов"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_diagnosis_suggestions(symptoms, specialty)
        
        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "specialty": specialty
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения предложений диагнозов: {str(e)}"
        )


@router.post("/suggestions/treatment")
async def get_treatment_suggestions(
    diagnosis: str,
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить предложения лечения на основе диагноза"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_treatment_suggestions(diagnosis, specialty)
        
        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "diagnosis": diagnosis,
            "specialty": specialty
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения предложений лечения: {str(e)}"
        )


@router.post("/suggestions/icd10")
async def get_icd10_suggestions(
    diagnosis_text: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить предложения кодов МКБ-10"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_icd10_suggestions(diagnosis_text)
        
        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "diagnosis_text": diagnosis_text
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения кодов МКБ-10: {str(e)}"
        )


@router.post("/auto-fill")
async def auto_fill_emr_fields(
    template_structure: Dict[str, Any],
    patient_data: Dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
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
            "specialty": specialty
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка автозаполнения EMR: {str(e)}"
        )


@router.post("/validate")
async def validate_emr_data(
    emr_data: Dict[str, Any],
    template_structure: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Валидация данных EMR"""
    try:
        ai_service = await get_emr_ai_service()
        validation_result = await ai_service.validate_emr_data(emr_data, template_structure)
        
        return validation_result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка валидации EMR: {str(e)}"
        )


@router.post("/suggestions/ai")
async def get_ai_suggestions(
    emr_data: Dict[str, Any],
    specialty: str = Query("general", description="Специализация врача"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить общие AI предложения для EMR"""
    try:
        ai_service = await get_emr_ai_service()
        suggestions = await ai_service.get_ai_suggestions(emr_data, specialty)
        
        return {
            "suggestions": suggestions,
            "specialty": specialty,
            "timestamp": "2024-01-01T00:00:00Z"  # Заглушка для времени
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения AI предложений: {str(e)}"
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
            "ai_suggestions"
        ],
        "providers": ["openai", "anthropic", "local"]
    }
