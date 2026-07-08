"""
MCP (Model Context Protocol) API endpoints
"""

import base64
import json
import logging
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ....api.deps import get_current_user, require_roles
from ....models.user import User
from ....services.mcp import get_mcp_manager

logger = logging.getLogger(__name__)

router = APIRouter()
# AI-REAUDIT-28 P1-13: удалены redundant inline role checks —
# require_roles dependency уже enforcing RBAC.

MAX_MCP_IMAGE_UPLOAD_BYTES = 25 * 1024 * 1024
MCP_IMAGE_READ_CHUNK_BYTES = 1024 * 1024


async def _read_mcp_image_bounded(image: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await image.read(MCP_IMAGE_READ_CHUNK_BYTES)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > MAX_MCP_IMAGE_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    "Image upload is too large "
                    f"(maximum {MAX_MCP_IMAGE_UPLOAD_BYTES // 1024 // 1024} MB)"
                ),
            )
        chunks.append(chunk)

    return b"".join(chunks)


def log_mcp_service_unavailable(action: str, exc: Exception) -> None:
    logger.warning(
        "MCP service unavailable action=%s error_type=%s",
        action,
        type(exc).__name__,
    )


def raise_mcp_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.error(
        "MCP endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail="Internal server error") from exc


# === MCP Management Endpoints ===


@router.get("/status", response_model=dict[str, Any])
async def get_mcp_status(
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Получить статус MCP системы"""
    try:
        mcp_manager = await get_mcp_manager()
        return {
            "healthy": mcp_manager.is_healthy(),
            "metrics": mcp_manager.get_metrics(),
            "capabilities": await mcp_manager.get_capabilities(),
        }
    except Exception as e:
        raise_mcp_internal_error("get_mcp_status", e)


@router.get("/health", response_model=dict[str, Any])
async def mcp_health_check(
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Проверка здоровья MCP серверов"""
    try:
        mcp_manager = await get_mcp_manager()
        if mcp_manager.client:
            health = await mcp_manager.client.health_check()
            return health
        else:
            return {"overall": "unhealthy", "error": "MCP client not initialized"}
    except Exception as e:
        raise_mcp_internal_error("mcp_health_check", e)


@router.get("/metrics", response_model=dict[str, Any])
async def get_mcp_metrics(
    server: str | None = None, current_user: User = Depends(require_roles("Admin"))
) -> dict[str, Any]:
    """Получить метрики MCP"""
    try:
        mcp_manager = await get_mcp_manager()
        if server:
            return mcp_manager.get_server_metrics(server)
        return mcp_manager.get_metrics()
    except Exception as e:
        raise_mcp_internal_error("get_mcp_metrics", e)


@router.get("/circuit-breaker", response_model=dict[str, Any])
async def get_circuit_breaker_status(
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Получить статус circuit breaker для всех серверов"""
    try:
        mcp_manager = await get_mcp_manager()
        return {
            "status": "ok",
            "servers": mcp_manager.get_circuit_breaker_status(),
            "config": {
                "threshold": mcp_manager.CIRCUIT_BREAKER_THRESHOLD,
                "cooldown_seconds": mcp_manager.CIRCUIT_BREAKER_COOLDOWN,
            },
        }
    except Exception as e:
        raise_mcp_internal_error("get_circuit_breaker_status", e)


@router.post("/reset-metrics", response_model=dict[str, Any])
async def reset_mcp_metrics(
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician")),
) -> dict[str, Any]:
    """Сбросить метрики MCP (только для админов)"""
    try:
        if current_user.role not in ["admin", "Admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        mcp_manager = await get_mcp_manager()
        await mcp_manager.reset_metrics()
        return {"status": "success", "message": "Metrics reset successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise_mcp_internal_error("reset_mcp_metrics", e)


# === Complaint Analysis via MCP ===


class MCPComplaintRequest(BaseModel):
    """Запрос на анализ жалоб через MCP"""

    complaint: str
    patient_age: int | None = None
    patient_gender: str | None = None
    urgency_assessment: bool = True
    provider: str | None = None


@router.post("/complaint/analyze", response_model=dict[str, Any])
async def mcp_analyze_complaint(
    request: MCPComplaintRequest, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
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

    except HTTPException:
        raise
    except Exception as e:
        raise_mcp_internal_error("mcp_analyze_complaint", e)


@router.post("/complaint/validate", response_model=dict[str, Any])
async def mcp_validate_complaint(
    complaint: str, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_validate_complaint", e)


@router.get("/complaint/templates", response_model=dict[str, Any])
async def mcp_get_complaint_templates(
    specialty: str | None = None, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_get_complaint_templates", e)


# === ICD-10 via MCP ===


class MCPICD10Request(BaseModel):
    """Запрос на работу с МКБ-10 через MCP"""

    symptoms: list[str]
    diagnosis: str | None = None
    specialty: str | None = None
    provider: str | None = None
    max_suggestions: int = 5


@router.post("/icd10/suggest", response_model=dict[str, Any])
async def mcp_suggest_icd10(
    request: MCPICD10Request, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
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
            log_mcp_service_unavailable("mcp_suggest_icd10_service", mcp_error)
            return {
                "suggestions": [],
                "message": "Сервис подбора МКБ-10 временно недоступен",
                "success": False,
            }

    except HTTPException:
        raise
    except Exception as e:
        log_mcp_service_unavailable("mcp_suggest_icd10", e)
        # Возвращаем корректный ответ вместо 500
        return {
            "suggestions": [],
            "message": "Сервис подбора МКБ-10 временно недоступен",
            "success": False,
        }


@router.post("/icd10/validate", response_model=dict[str, Any])
async def mcp_validate_icd10(
    code: str,
    symptoms: list[str] | None = None,
    diagnosis: str | None = None,
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician")),
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_validate_icd10", e)


@router.get("/icd10/search", response_model=dict[str, Any])
async def mcp_search_icd10(
    query: str,
    category: str | None = None,
    limit: int = 10,
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician")),
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_search_icd10", e)


# === Lab Analysis via MCP ===


class MCPLabRequest(BaseModel):
    """Запрос на анализ лабораторных данных через MCP"""

    results: list[dict[str, Any]]
    patient_age: int | None = None
    patient_gender: str | None = None
    provider: str | None = None
    include_recommendations: bool = True


@router.post("/lab/interpret", response_model=dict[str, Any])
async def mcp_interpret_lab_results(
    request: MCPLabRequest, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
    """Интерпретация лабораторных результатов через MCP"""
    try:
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

    except HTTPException:
        raise
    except Exception as e:
        raise_mcp_internal_error("mcp_interpret_lab_results", e)


@router.post("/lab/check-critical", response_model=dict[str, Any])
async def mcp_check_critical_values(
    results: list[dict[str, Any]], current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_check_critical_values", e)


@router.get("/lab/normal-ranges", response_model=dict[str, Any])
async def mcp_get_normal_ranges(
    test_name: str | None = None,
    patient_gender: str | None = None,
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician")),
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_get_normal_ranges", e)


# === Medical Imaging via MCP ===


@router.post("/imaging/analyze", response_model=dict[str, Any])
async def mcp_analyze_image(
    image: UploadFile = File(...),
    image_type: str = Form(...),
    modality: str | None = Form(None),
    clinical_context: str | None = Form(None),
    provider: str | None = Form(None),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician")),
) -> dict[str, Any]:
    """Анализ медицинского изображения через MCP"""
    try:
        # Проверяем тип файла
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")

        # Читаем и кодируем изображение в base64
        image_data = await _read_mcp_image_bounded(image)
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

    except HTTPException:
        raise
    except Exception as e:
        raise_mcp_internal_error("mcp_analyze_image", e)


@router.post("/imaging/skin-lesion", response_model=dict[str, Any])
async def mcp_analyze_skin_lesion(
    image: UploadFile = File(...),
    lesion_info: str | None = Form(None),
    patient_history: str | None = Form(None),
    provider: str | None = Form(None),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician")),
) -> dict[str, Any]:
    """Анализ кожных образований через MCP"""
    try:
        # Читаем и кодируем изображение
        image_data = await _read_mcp_image_bounded(image)
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

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Неверный формат JSON данных")
    except Exception as e:
        raise_mcp_internal_error("mcp_analyze_skin_lesion", e)


@router.get("/imaging/types", response_model=dict[str, Any])
async def mcp_get_imaging_types(
    category: str | None = None, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> dict[str, Any]:
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
        raise_mcp_internal_error("mcp_get_imaging_types", e)


# === Batch Processing ===


class MCPBatchRequest(BaseModel):
    """Запрос на пакетную обработку через MCP"""

    requests: list[dict[str, Any]]
    parallel: bool = True


@router.post("/batch", response_model=list[dict[str, Any]])
async def mcp_batch_process(
    request: MCPBatchRequest, current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dermatologist", "dentist", "Lab", "labtechnician"))
) -> list[dict[str, Any]]:
    """Пакетная обработка запросов через MCP"""
    try:
        mcp_manager = await get_mcp_manager()

        results = await mcp_manager.batch_execute(
            requests=request.requests, parallel=request.parallel
        )

        return results

    except HTTPException:
        raise
    except Exception as e:
        raise_mcp_internal_error("mcp_batch_process", e)


# === Server Capabilities ===


@router.get("/capabilities", response_model=dict[str, Any])
async def mcp_get_capabilities(
    server: str | None = None, current_user: User = Depends(require_roles("Admin"))
) -> dict[str, Any]:
    """Получить возможности MCP серверов"""
    try:
        mcp_manager = await get_mcp_manager()

        if mcp_manager.client:
            return await mcp_manager.client.get_server_capabilities(server)
        else:
            return {"status": "error", "error": "MCP client not initialized"}

    except Exception as e:
        raise_mcp_internal_error("mcp_get_capabilities", e)
