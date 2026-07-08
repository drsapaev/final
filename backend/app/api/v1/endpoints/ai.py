"""
AI API endpoints
"""

import json
import logging
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query
from pydantic import BaseModel

from ....api.deps import get_current_user
from ....core.rbac import AIPermission, require_any_ai_permission
from ....models.user import User
from ....services.ai import AIProviderType, ai_manager
from ....services.mcp import get_mcp_manager
from ....services.ai_feature_gating import RequireAiFeature

logger = logging.getLogger(__name__)


class AIResultResponse(BaseModel):
    """Generic AI response model for OpenAPI documentation."""
    success: bool = True
    data: dict | None = None
    error: str | None = None
    provider: str | None = None

MAX_LEGACY_AI_UPLOAD_BYTES = 25 * 1024 * 1024
AI_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024

LEGACY_AI_ACCESS = require_any_ai_permission(
    AIPermission.ADMIN_AI,
    AIPermission.DIAGNOSE,
    AIPermission.ANALYZE_IMAGE,
    AIPermission.ANALYZE_DOCUMENT,
    AIPermission.SUGGEST_ICD10,
)

router = APIRouter(dependencies=[Depends(LEGACY_AI_ACCESS), Depends(RequireAiFeature("ai_legacy"))])  # P1-13


async def _read_ai_upload_bounded(upload: UploadFile) -> bytes:
    total_size = 0
    chunks: list[bytes] = []

    while True:
        chunk = await upload.read(AI_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_LEGACY_AI_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "File too large "
                    f"(maximum {MAX_LEGACY_AI_UPLOAD_BYTES // 1024 // 1024} MB)"
                ),
            )
        chunks.append(chunk)

    return b"".join(chunks)


def _raise_ai_internal_error(exc: Exception) -> NoReturn:
    if isinstance(exc, HTTPException):
        raise exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


class ComplaintAnalysisRequest(BaseModel):
    """Запрос на анализ жалоб"""

    complaint: str
    patient_age: int | None = None
    patient_gender: str | None = None
    provider: AIProviderType | None = None
    use_mcp: bool = True  # Использовать MCP по умолчанию


class ICD10SuggestRequest(BaseModel):
    """Запрос на подсказки МКБ-10"""

    symptoms: list[str]
    diagnosis: str | None = None
    provider: AIProviderType | None = None


class LabInterpretRequest(BaseModel):
    """Запрос на интерпретацию анализов"""

    results: list[dict[str, Any]]
    patient_age: int | None = None
    patient_gender: str | None = None
    provider: AIProviderType | None = None


class ECGInterpretRequest(BaseModel):
    """Запрос на интерпретацию ЭКГ"""

    parameters: dict[str, Any]
    auto_interpretation: str | None = None
    patient_age: int | None = None
    patient_gender: str | None = None
    provider: AIProviderType | None = None


@router.get("/providers", response_model=dict[str, Any])
async def get_available_providers(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Получить список доступных AI провайдеров"""
    return {
        "providers": ai_manager.get_available_providers(),
        "default": (
            ai_manager.default_provider.value if ai_manager.default_provider else None
        ),
    }


@router.post("/complaint-to-plan", response_model=dict[str, Any])
async def analyze_complaint(
    request: ComplaintAnalysisRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
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

        # Используем MCP если включено
        if request.use_mcp:
            try:
                mcp_manager = await get_mcp_manager()
                result = await mcp_manager.execute_request(
                    server="complaint",
                    method="tool/analyze_complaint",
                    params={
                        "complaint": request.complaint,
                        "patient_info": patient_info if patient_info else None,
                        "provider": (
                            request.provider.value if request.provider else None
                        ),
                        "urgency_assessment": True,
                    },
                )

                if result.get("status") == "success":
                    return result.get("data", {})
                elif result.get("fallback"):
                    # Fallback to direct AI manager
                    logger.warning("MCP failed, falling back to direct AI manager")
                else:
                    raise HTTPException(
                        status_code=500, detail=result.get("error", "MCP error")
                    )
            except Exception as mcp_error:
                logger.error(f"MCP error: {str(mcp_error)}")
                # Fallback to direct AI manager if MCP fails

        # Direct AI manager call (fallback or if MCP disabled)
        result = await ai_manager.analyze_complaint(
            complaint=request.complaint,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error analyzing complaint: {str(e)}")
        _raise_ai_internal_error(e)


@router.post("/icd-suggest", response_model=list[dict[str, str]])
async def suggest_icd10_codes(
    request: ICD10SuggestRequest, current_user: User = Depends(get_current_user)
) -> list[dict[str, str]]:
    """Получить подсказки кодов МКБ-10"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        result = await ai_manager.suggest_icd10(
            symptoms=request.symptoms,
            diagnosis=request.diagnosis,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error suggesting ICD-10: {str(e)}")
        _raise_ai_internal_error(e)


@router.post("/lab-interpret", response_model=dict[str, Any])
async def interpret_lab_results(
    request: LabInterpretRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
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
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error interpreting lab results: {str(e)}")
        _raise_ai_internal_error(e)


@router.post("/skin-analyze", response_model=dict[str, Any])
async def analyze_skin(
    image: UploadFile = File(...),
    metadata: str | None = Form(None),
    provider: AIProviderType | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Анализ состояния кожи по фото"""
    try:
        # Проверяем права доступа
        if current_user.role not in ["doctor", "admin"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        # Проверяем тип файла
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Файл должен быть изображением")

        # Читаем изображение
        image_data = await _read_ai_upload_bounded(image)

        # Парсим метаданные если есть
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except Exception:
                metadata_dict = {"description": metadata}

        result = await ai_manager.analyze_skin(
            image_data=image_data, metadata=metadata_dict, provider_type=provider
        )

        return result

    except Exception as e:
        logger.error(f"Error analyzing skin: {str(e)}")
        _raise_ai_internal_error(e)


@router.post("/ecg-interpret", response_model=dict[str, Any])
async def interpret_ecg(
    request: ECGInterpretRequest, current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
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
            "auto_interpretation": request.auto_interpretation,
        }

        result = await ai_manager.interpret_ecg(
            ecg_data=ecg_data,
            patient_info=patient_info if patient_info else None,
            provider_type=request.provider,
        )

        return result

    except Exception as e:
        logger.error(f"Error interpreting ECG: {str(e)}")
        _raise_ai_internal_error(e)


class DifferentialDiagnosisRequest(BaseModel):
    """Запрос на дифференциальную диагностику"""

    symptoms: list[str]
    patient_info: dict[str, Any] | None = None
    provider: AIProviderType | None = None


class SymptomAnalysisRequest(BaseModel):
    """Запрос на анализ симптомов"""

    symptoms: list[str]
    severity: list[int] | None = None
    provider: AIProviderType | None = None


class ClinicalDecisionRequest(BaseModel):
    """Запрос на поддержку клинических решений"""

    case_data: dict[str, Any]
    provider: AIProviderType | None = None

