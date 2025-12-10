"""
External Integration API Endpoints
Эндпоинты для работы с внешними системами (DMED, eGOV, Страхование)
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.external_integration_service import (
    get_integration_manager,
    IntegrationType,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ===================== СХЕМЫ =====================


class PatientVerifyRequest(BaseModel):
    pinfl: Optional[str] = None
    policy_number: Optional[str] = None


class InsuranceAuthRequest(BaseModel):
    policy_number: str
    service_code: str
    estimated_cost: float


class ClaimSubmitRequest(BaseModel):
    policy_number: str
    patient_id: int
    visit_id: int
    services: list
    total_amount: float
    diagnosis_code: Optional[str] = None


# ===================== ОБЩИЕ =====================


@router.get("/available", summary="Доступные интеграции")
async def get_available_integrations(
    user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Dict[str, Any]:
    """
    Получить список доступных внешних интеграций
    """
    manager = get_integration_manager()
    return {
        "available": manager.get_available_integrations(),
    }


@router.post("/verify-patient", summary="Верифицировать пациента")
async def verify_patient(
    data: PatientVerifyRequest,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> Dict[str, Any]:
    """
    Верификация пациента через все доступные источники
    """
    try:
        identifier = data.pinfl or data.policy_number
        if not identifier:
            raise HTTPException(status_code=400, detail="Укажите ПИНФЛ или номер полиса")
        
        manager = get_integration_manager()
        results = await manager.verify_patient_all(identifier)
        
        return {
            "identifier": identifier,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Patient verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== DMED =====================


@router.get("/dmed/patient/{pinfl}", summary="Получить данные пациента из DMED")
async def get_dmed_patient(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> Dict[str, Any]:
    """
    Получить данные пациента из DMED по ПИНФЛ
    """
    try:
        manager = get_integration_manager()
        dmed = manager.get_integration(IntegrationType.DMED)
        
        if not dmed:
            raise HTTPException(status_code=503, detail="DMED интеграция недоступна")
        
        result = await dmed.verify_patient(pinfl)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DMED patient error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dmed/history/{pinfl}", summary="История болезни из DMED")
async def get_dmed_history(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Dict[str, Any]:
    """
    Получить историю болезни пациента из DMED
    """
    try:
        manager = get_integration_manager()
        dmed = manager.get_integration(IntegrationType.DMED)
        
        if not dmed:
            raise HTTPException(status_code=503, detail="DMED интеграция недоступна")
        
        from app.services.external_integration_service import DMEDIntegration
        if isinstance(dmed, DMEDIntegration):
            result = await dmed.get_patient_history(pinfl)
            return result
        
        raise HTTPException(status_code=503, detail="DMED интеграция некорректна")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DMED history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== eGOV =====================


@router.get("/egov/citizen/{pinfl}", summary="Данные гражданина из eGOV")
async def get_egov_citizen(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> Dict[str, Any]:
    """
    Верификация гражданина через eGOV
    """
    try:
        manager = get_integration_manager()
        egov = manager.get_integration(IntegrationType.EGOV)
        
        if not egov:
            raise HTTPException(status_code=503, detail="eGOV интеграция недоступна")
        
        result = await egov.verify_patient(pinfl)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"eGOV citizen error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/egov/benefits/{pinfl}", summary="Льготы гражданина")
async def get_egov_benefits(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> Dict[str, Any]:
    """
    Проверить льготы гражданина через eGOV
    """
    try:
        manager = get_integration_manager()
        egov = manager.get_integration(IntegrationType.EGOV)
        
        if not egov:
            raise HTTPException(status_code=503, detail="eGOV интеграция недоступна")
        
        from app.services.external_integration_service import EGOVIntegration
        if isinstance(egov, EGOVIntegration):
            result = await egov.check_benefits(pinfl)
            return result
        
        raise HTTPException(status_code=503, detail="eGOV интеграция некорректна")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"eGOV benefits error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== СТРАХОВАНИЕ =====================


@router.get("/insurance/policy/{policy_number}", summary="Проверить полис")
async def check_insurance_policy(
    policy_number: str,
    user: User = Depends(deps.require_roles("Admin", "Registrar", "Cashier")),
) -> Dict[str, Any]:
    """
    Проверить статус страхового полиса
    """
    try:
        manager = get_integration_manager()
        insurance = manager.get_integration(IntegrationType.INSURANCE)
        
        if not insurance:
            raise HTTPException(status_code=503, detail="Страховая интеграция недоступна")
        
        result = await insurance.verify_patient(policy_number)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insurance policy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insurance/authorize", summary="Авторизация услуги")
async def authorize_insurance_service(
    data: InsuranceAuthRequest,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> Dict[str, Any]:
    """
    Авторизовать медицинскую услугу в страховой компании
    """
    try:
        manager = get_integration_manager()
        insurance = manager.get_integration(IntegrationType.INSURANCE)
        
        if not insurance:
            raise HTTPException(status_code=503, detail="Страховая интеграция недоступна")
        
        from app.services.external_integration_service import InsuranceIntegration
        if isinstance(insurance, InsuranceIntegration):
            result = await insurance.authorize_service(
                policy_number=data.policy_number,
                service_code=data.service_code,
                estimated_cost=data.estimated_cost,
            )
            return result
        
        raise HTTPException(status_code=503, detail="Страховая интеграция некорректна")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insurance authorization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insurance/claim", summary="Отправить страховой случай")
async def submit_insurance_claim(
    data: ClaimSubmitRequest,
    user: User = Depends(deps.require_roles("Admin", "Cashier")),
) -> Dict[str, Any]:
    """
    Отправить страховой случай (claim) в страховую компанию
    """
    try:
        manager = get_integration_manager()
        insurance = manager.get_integration(IntegrationType.INSURANCE)
        
        if not insurance:
            raise HTTPException(status_code=503, detail="Страховая интеграция недоступна")
        
        claim_data = {
            "policy_number": data.policy_number,
            "patient_id": data.patient_id,
            "visit_id": data.visit_id,
            "services": data.services,
            "total_amount": data.total_amount,
            "diagnosis_code": data.diagnosis_code,
        }
        
        result = await insurance.submit_visit(claim_data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insurance claim error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insurance/claim/{claim_id}", summary="Статус страхового случая")
async def get_insurance_claim_status(
    claim_id: str,
    user: User = Depends(deps.require_roles("Admin", "Cashier")),
) -> Dict[str, Any]:
    """
    Получить статус страхового случая
    """
    try:
        manager = get_integration_manager()
        insurance = manager.get_integration(IntegrationType.INSURANCE)
        
        if not insurance:
            raise HTTPException(status_code=503, detail="Страховая интеграция недоступна")
        
        from app.services.external_integration_service import InsuranceIntegration
        if isinstance(insurance, InsuranceIntegration):
            result = await insurance.get_claim_status(claim_id)
            return result
        
        raise HTTPException(status_code=503, detail="Страховая интеграция некорректна")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Insurance claim status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
