"""
AI API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from ....services.ai import ai_manager, AIProviderType
from ....api.deps import get_current_user
from ....models.user import User
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ComplaintAnalysisRequest(BaseModel):
    """Запрос на анализ жалоб"""
    complaint: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[AIProviderType] = None


class ICD10SuggestRequest(BaseModel):
    """Запрос на подсказки МКБ-10"""
    symptoms: List[str]
    diagnosis: Optional[str] = None
    provider: Optional[AIProviderType] = None


class LabInterpretRequest(BaseModel):
    """Запрос на интерпретацию анализов"""
    results: List[Dict[str, Any]]
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[AIProviderType] = None


class ECGInterpretRequest(BaseModel):
    """Запрос на интерпретацию ЭКГ"""
    parameters: Dict[str, Any]
    auto_interpretation: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[AIProviderType] = None


@router.get("/providers")
async def get_available_providers(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Получить список доступных AI провайдеров"""
    return {
        "providers": ai_manager.get_available_providers(),
        "default": ai_manager.default_provider.value if ai_manager.default_provider else None
    }


@router.post("/complaint-to-plan")
async def analyze_complaint(
    request: ComplaintAnalysisRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Анализ жалоб пациента и создание плана обследования"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender
        
        result = await ai_manager.analyze_complaint(
            complaint=request.complaint,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing complaint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/icd-suggest")
async def suggest_icd10_codes(
    request: ICD10SuggestRequest,
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Получить подсказки кодов МКБ-10"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        result = await ai_manager.suggest_icd10(
            symptoms=request.symptoms,
            diagnosis=request.diagnosis,
            provider_type=request.provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error suggesting ICD-10: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lab-interpret")
async def interpret_lab_results(
    request: LabInterpretRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Интерпретация результатов лабораторных анализов"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "lab", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender
        
        result = await ai_manager.interpret_lab_results(
            results=request.results,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error interpreting lab results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skin-analyze")
async def analyze_skin(
    image: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    provider: Optional[AIProviderType] = Form(None),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Анализ состояния кожи по фото"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        # Проверяем тип файла
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")
        
        # Читаем изображение
        image_data = await image.read()
        
        # Парсим метаданные если есть
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except:
                metadata_dict = {"description": metadata}
        
        result = await ai_manager.analyze_skin(
            image_data=image_data,
            metadata=metadata_dict,
            provider_type=provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing skin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ecg-interpret")
async def interpret_ecg(
    request: ECGInterpretRequest,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Интерпретация данных ЭКГ"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender
        
        ecg_data = {
            "parameters": request.parameters,
            "auto_interpretation": request.auto_interpretation
        }
        
        result = await ai_manager.interpret_ecg(
            ecg_data=ecg_data,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error interpreting ECG: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
