"""
MCP (Model Context Protocol) API endpoints
"""

import base64
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ....api.deps import get_current_user
from ....models.user import User
from ....services.mcp import get_mcp_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# === MCP Management Endpoints ===


@router.get("/status")
async def get_mcp_status(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Получить статус MCP системы"""
    try:
        mcp_manager = await get_mcp_manager()
        return {
            "healthy": mcp_manager.is_healthy(),
            "metrics": mcp_manager.get_metrics(),
            "capabilities": await mcp_manager.get_capabilities(),
        }
    except Exception as e:
        logger.error(f"Error getting MCP status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def mcp_health_check(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Проверка здоровья MCP серверов"""
    try:
        mcp_manager = await get_mcp_manager()
        if mcp_manager.client:
            health = await mcp_manager.client.health_check()
            return health
        else:
            return {"overall": "unhealthy", "error": "MCP client not initialized"}
    except Exception as e:
        logger.error(f"Error checking MCP health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_mcp_metrics(
    server: Optional[str] = None, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Получить метрики MCP"""
    try:
        mcp_manager = await get_mcp_manager()
        if server:
            return mcp_manager.get_server_metrics(server)
        return mcp_manager.get_metrics()
    except Exception as e:
        logger.error(f"Error getting MCP metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-metrics")
async def reset_mcp_metrics(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Сбросить метрики MCP (только для админов)"""
    try:
        if current_user.role not in ["admin", "Admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        mcp_manager = await get_mcp_manager()
        await mcp_manager.reset_metrics()
        return {"status": "success", "message": "Metrics reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting MCP metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === Complaint Analysis via MCP ===


class MCPComplaintRequest(BaseModel):
    """Запрос на анализ жалоб через MCP"""

    complaint: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    urgency_assessment: bool = True
    provider: Optional[str] = None


@router.post("/complaint/analyze")
async def mcp_analyze_complaint(
    request: MCPComplaintRequest, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Анализ жалоб через MCP"""
    try:
        # Расширенный список разрешенных ролей
        allowed_roles = [
            "doctor",
            "Doctor",
            "admin",
            "Admin",
            "Registrar",
            "cardio",
            "cardiology",
            "Cardiologist",
            "Cardio",
            "derma",
            "Dermatologist",
            "dentist",
            "Dentist",
            "Lab",
            "Laboratory",
        ]
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Недостаточно прав. Роль: {current_user.role}, Требуется: {allowed_roles}",
            )

        mcp_manager = await get_mcp_manager()

        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender

        result = await mcp_manager.execute_request(
            server="complaint",
            method="tool/analyze_complaint",
            params={
                "complaint": request.complaint,
                "patient_info": patient_info if patient_info else None,
                "provider": request.provider,
                "urgency_assessment": request.urgency_assessment,
            },
        )

        return result

    except Exception as e:
        logger.error(f"Error in MCP complaint analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complaint/validate")
async def mcp_validate_complaint(
    complaint: str, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Валидация жалоб через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="complaint",
            method="tool/validate_complaint",
            params={"complaint": complaint},
        )

        return result

    except Exception as e:
        logger.error(f"Error in MCP complaint validation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/complaint/templates")
async def mcp_get_complaint_templates(
    specialty: Optional[str] = None, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Получить шаблоны жалоб через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="complaint",
            method="resource/complaint_templates",
            params={"specialty": specialty},
        )

        return result

    except Exception as e:
        logger.error(f"Error getting complaint templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === ICD-10 via MCP ===


class MCPICD10Request(BaseModel):
    """Запрос на работу с МКБ-10 через MCP"""

    symptoms: List[str]
    diagnosis: Optional[str] = None
    specialty: Optional[str] = None
    provider: Optional[str] = None
    max_suggestions: int = 5


@router.post("/icd10/suggest")
async def mcp_suggest_icd10(
    request: MCPICD10Request, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Подсказки МКБ-10 через MCP"""
    try:
        # Расширенный список разрешенных ролей
        allowed_roles = [
            "doctor",
            "Doctor",
            "admin",
            "Admin",
            "Registrar",
            "cardio",
            "cardiology",
            "Cardiologist",
            "Cardio",
            "derma",
            "Dermatologist",
            "dentist",
            "Dentist",
            "Lab",
            "Laboratory",
        ]
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Недостаточно прав. Роль: {current_user.role}, Требуется: {allowed_roles}",
            )

        # Проверка на пустой или слишком короткий запрос
        if not request.symptoms or len(request.symptoms) == 0:
            # Если нет симптомов и нет диагноза, возвращаем пустой результат
            if not request.diagnosis or len(request.diagnosis.strip()) < 2:
                return {
                    "suggestions": [],
                    "message": "Укажите симптомы или диагноз для подбора кодов МКБ-10",
                    "success": False,
                }

        # Фильтруем пустые симптомы
        symptoms = [s.strip() for s in request.symptoms if s and s.strip()]

        # Если после фильтрации симптомы пусты и диагноз короткий
        if len(symptoms) == 0 and (
            not request.diagnosis or len(request.diagnosis.strip()) < 2
        ):
            return {
                "suggestions": [],
                "message": "Укажите симптомы или диагноз для подбора кодов МКБ-10",
                "success": False,
            }

        # Проверяем, что есть хотя бы один значимый входной параметр
        diagnosis_text = (request.diagnosis or "").strip()
        if len(symptoms) == 0 and len(diagnosis_text) < 2:
            return {
                "suggestions": [],
                "message": "Недостаточно данных для подбора кодов МКБ-10",
                "success": False,
            }

        mcp_manager = await get_mcp_manager()

        try:
            result = await mcp_manager.execute_request(
                server="icd10",
                method="tool/suggest_icd10",
                params={
                    "symptoms": (
                        symptoms
                        if len(symptoms) > 0
                        else [diagnosis_text] if diagnosis_text else []
                    ),
                    "diagnosis": diagnosis_text if diagnosis_text else None,
                    "specialty": request.specialty,
                    "provider": request.provider,
                    "max_suggestions": request.max_suggestions,
                },
            )

            # Если результат пустой или содержит ошибку, возвращаем корректный ответ
            if not result or result.get("error"):
                return {
                    "suggestions": [],
                    "message": result.get(
                        "error", "Не удалось получить подсказки МКБ-10"
                    ),
                    "success": False,
                }

            return result

        except Exception as mcp_error:
            # Если ошибка при обращении к MCP, возвращаем корректный ответ вместо 500
            logger.warning(f"MCP ICD-10 service error: {str(mcp_error)}")
            return {
                "suggestions": [],
                "message": f"Сервис подбора МКБ-10 временно недоступен: {str(mcp_error)}",
                "success": False,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in MCP ICD-10 suggestions: {str(e)}")
        # Возвращаем корректный ответ вместо 500
        return {
            "suggestions": [],
            "message": f"Ошибка при подборе кодов МКБ-10: {str(e)}",
            "success": False,
        }


@router.post("/icd10/validate")
async def mcp_validate_icd10(
    code: str,
    symptoms: Optional[List[str]] = None,
    diagnosis: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Валидация кода МКБ-10 через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="icd10",
            method="tool/validate_icd10",
            params={"code": code, "symptoms": symptoms, "diagnosis": diagnosis},
        )

        return result

    except Exception as e:
        logger.error(f"Error in MCP ICD-10 validation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/icd10/search")
async def mcp_search_icd10(
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Поиск кодов МКБ-10 через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="icd10",
            method="tool/search_icd10",
            params={"query": query, "category": category, "limit": limit},
        )

        return result

    except Exception as e:
        logger.error(f"Error in MCP ICD-10 search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === Lab Analysis via MCP ===


class MCPLabRequest(BaseModel):
    """Запрос на анализ лабораторных данных через MCP"""

    results: List[Dict[str, Any]]
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    provider: Optional[str] = None
    include_recommendations: bool = True


@router.post("/lab/interpret")
async def mcp_interpret_lab_results(
    request: MCPLabRequest, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Интерпретация лабораторных результатов через MCP"""
    try:
        if current_user.role not in ["doctor", "lab", "admin", "Admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        mcp_manager = await get_mcp_manager()

        patient_info = {}
        if request.patient_age:
            patient_info["age"] = request.patient_age
        if request.patient_gender:
            patient_info["gender"] = request.patient_gender

        result = await mcp_manager.execute_request(
            server="lab",
            method="tool/interpret_lab_results",
            params={
                "results": request.results,
                "patient_info": patient_info if patient_info else None,
                "provider": request.provider,
                "include_recommendations": request.include_recommendations,
            },
        )

        return result

    except Exception as e:
        logger.error(f"Error in MCP lab interpretation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lab/check-critical")
async def mcp_check_critical_values(
    results: List[Dict[str, Any]], current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Проверка критических значений через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="lab",
            method="tool/check_critical_values",
            params={"results": results},
        )

        return result

    except Exception as e:
        logger.error(f"Error checking critical values: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lab/normal-ranges")
async def mcp_get_normal_ranges(
    test_name: Optional[str] = None,
    patient_gender: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Получить нормальные диапазоны через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="lab",
            method="resource/normal_ranges",
            params={"test_name": test_name, "patient_gender": patient_gender},
        )

        return result

    except Exception as e:
        logger.error(f"Error getting normal ranges: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === Medical Imaging via MCP ===


@router.post("/imaging/analyze")
async def mcp_analyze_image(
    image: UploadFile = File(...),
    image_type: str = Form(...),
    modality: Optional[str] = Form(None),
    clinical_context: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Анализ медицинского изображения через MCP"""
    try:
        if current_user.role not in ["doctor", "admin", "Admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        # Проверяем тип файла
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")

        # Читаем и кодируем изображение в base64
        image_data = await image.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="imaging",
            method="tool/analyze_medical_image",
            params={
                "image_data": image_base64,
                "image_type": image_type,
                "modality": modality,
                "clinical_context": clinical_context,
                "patient_info": None,
                "provider": provider,
            },
        )

        return result

    except Exception as e:
        logger.error(f"Error in MCP image analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/imaging/skin-lesion")
async def mcp_analyze_skin_lesion(
    image: UploadFile = File(...),
    lesion_info: Optional[str] = Form(None),
    patient_history: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Анализ кожных образований через MCP"""
    try:
        if current_user.role not in ["doctor", "admin", "Admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        # Читаем и кодируем изображение
        image_data = await image.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Парсим JSON данные
        lesion_dict = json.loads(lesion_info) if lesion_info else None
        history_dict = json.loads(patient_history) if patient_history else None

        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="imaging",
            method="tool/analyze_skin_lesion",
            params={
                "image_data": image_base64,
                "lesion_info": lesion_dict,
                "patient_history": history_dict,
                "provider": provider,
            },
        )

        return result

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Неверный формат JSON данных")
    except Exception as e:
        logger.error(f"Error in MCP skin lesion analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/imaging/types")
async def mcp_get_imaging_types(
    category: Optional[str] = None, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Получить типы медицинских изображений через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        result = await mcp_manager.execute_request(
            server="imaging",
            method="resource/imaging_types",
            params={"category": category},
        )

        return result

    except Exception as e:
        logger.error(f"Error getting imaging types: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === Batch Processing ===


class MCPBatchRequest(BaseModel):
    """Запрос на пакетную обработку через MCP"""

    requests: List[Dict[str, Any]]
    parallel: bool = True


@router.post("/batch")
async def mcp_batch_process(
    request: MCPBatchRequest, current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Пакетная обработка запросов через MCP"""
    try:
        if current_user.role not in ["doctor", "admin", "Admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        mcp_manager = await get_mcp_manager()

        results = await mcp_manager.batch_execute(
            requests=request.requests, parallel=request.parallel
        )

        return results

    except Exception as e:
        logger.error(f"Error in MCP batch processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === Server Capabilities ===


@router.get("/capabilities")
async def mcp_get_capabilities(
    server: Optional[str] = None, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Получить возможности MCP серверов"""
    try:
        mcp_manager = await get_mcp_manager()

        if mcp_manager.client:
            return await mcp_manager.client.get_server_capabilities(server)
        else:
            return {"status": "error", "error": "MCP client not initialized"}

    except Exception as e:
        logger.error(f"Error getting MCP capabilities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
