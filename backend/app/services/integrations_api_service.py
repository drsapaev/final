"""
External Integration API Endpoints
Эндпоинты для работы с внешними системами (DMED, eGOV, Страхование)
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.services.interoperability_gateway_service import (
    IntegrationCapabilityError,
    IntegrationType,
    IntegrationUnavailableError,
    get_interoperability_gateway_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ===================== СХЕМЫ =====================


class PatientVerifyRequest(BaseModel):
    pinfl: str | None = None
    policy_number: str | None = None


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
    diagnosis_code: str | None = None


def _build_request_id(user: User, operation: str) -> str:
    return f"integrations:{operation}:user-{getattr(user, 'id', 'unknown')}"


def _map_gateway_error(error: Exception) -> HTTPException:
    if isinstance(error, IntegrationUnavailableError):
        integration_code = error.integration_type.value
        unavailable_messages = {
            "dmed": "DMED интеграция недоступна",
            "egov": "eGOV интеграция недоступна",
            "insurance": "Страховая интеграция недоступна",
        }
        detail = unavailable_messages.get(
            integration_code,
            f"Интеграция {integration_code} недоступна",
        )
        return HTTPException(status_code=503, detail=detail)

    if isinstance(error, IntegrationCapabilityError):
        integration_code = error.integration_type.value
        invalid_messages = {
            ("dmed", "get_patient_history"): "DMED интеграция некорректна",
            ("egov", "check_benefits"): "eGOV интеграция некорректна",
            ("insurance", "authorize_service"): "Страховая интеграция некорректна",
            ("insurance", "submit_claim"): "Страховая интеграция некорректна",
            ("insurance", "get_claim_status"): "Страховая интеграция некорректна",
        }
        detail = invalid_messages.get(
            (integration_code, error.capability),
            f"Интеграция {integration_code} не поддерживает {error.capability}",
        )
        return HTTPException(status_code=503, detail=detail)

    return HTTPException(status_code=500, detail=str(error))


# ===================== ОБЩИЕ =====================


@router.get("/available", summary="Доступные интеграции")
async def get_available_integrations(
    user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> dict[str, Any]:
    """
    Получить список доступных внешних интеграций
    """
    gateway = get_interoperability_gateway_service()
    request_id = _build_request_id(user, "available")
    return {
        "available": gateway.get_available_integrations(request_id=request_id),
    }


@router.post("/verify-patient", summary="Верифицировать пациента")
async def verify_patient(
    data: PatientVerifyRequest,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> dict[str, Any]:
    """
    Верификация пациента через все доступные источники
    """
    try:
        identifier = data.pinfl or data.policy_number
        if not identifier:
            raise HTTPException(status_code=400, detail="Укажите ПИНФЛ или номер полиса")

        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "verify-patient")
        results = await gateway.verify_patient_all(
            identifier=identifier,
            request_id=request_id,
        )

        return {
            "identifier": identifier,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Patient verification error")
        raise _map_gateway_error(error) from error


# ===================== DMED =====================


@router.get("/dmed/patient/{pinfl}", summary="Получить данные пациента из DMED")
async def get_dmed_patient(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Doctor", "Registrar")),
) -> dict[str, Any]:
    """
    Получить данные пациента из DMED по ПИНФЛ
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "dmed-patient")
        result = await gateway.verify_patient(
            integration_type=IntegrationType.DMED,
            identifier=pinfl,
            request_id=request_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("DMED patient error")
        raise _map_gateway_error(error) from error


@router.get("/dmed/history/{pinfl}", summary="История болезни из DMED")
async def get_dmed_history(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> dict[str, Any]:
    """
    Получить историю болезни пациента из DMED
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "dmed-history")
        return await gateway.get_dmed_history(
            pinfl=pinfl,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("DMED history error")
        raise _map_gateway_error(error) from error


# ===================== eGOV =====================


@router.get("/egov/citizen/{pinfl}", summary="Данные гражданина из eGOV")
async def get_egov_citizen(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> dict[str, Any]:
    """
    Верификация гражданина через eGOV
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "egov-citizen")
        result = await gateway.verify_patient(
            integration_type=IntegrationType.EGOV,
            identifier=pinfl,
            request_id=request_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("eGOV citizen error")
        raise _map_gateway_error(error) from error


@router.get("/egov/benefits/{pinfl}", summary="Льготы гражданина")
async def get_egov_benefits(
    pinfl: str,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> dict[str, Any]:
    """
    Проверить льготы гражданина через eGOV
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "egov-benefits")
        return await gateway.get_egov_benefits(
            pinfl=pinfl,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("eGOV benefits error")
        raise _map_gateway_error(error) from error


# ===================== СТРАХОВАНИЕ =====================


@router.get("/insurance/policy/{policy_number}", summary="Проверить полис")
async def check_insurance_policy(
    policy_number: str,
    user: User = Depends(deps.require_roles("Admin", "Registrar", "Cashier")),
) -> dict[str, Any]:
    """
    Проверить статус страхового полиса
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "insurance-policy")
        result = await gateway.verify_patient(
            integration_type=IntegrationType.INSURANCE,
            identifier=policy_number,
            request_id=request_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Insurance policy error")
        raise _map_gateway_error(error) from error


@router.post("/insurance/authorize", summary="Авторизация услуги")
async def authorize_insurance_service(
    data: InsuranceAuthRequest,
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
) -> dict[str, Any]:
    """
    Авторизовать медицинскую услугу в страховой компании
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "insurance-authorize")
        return await gateway.authorize_insurance_service(
            policy_number=data.policy_number,
            service_code=data.service_code,
            estimated_cost=data.estimated_cost,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Insurance authorization error")
        raise _map_gateway_error(error) from error


@router.post("/insurance/claim", summary="Отправить страховой случай")
async def submit_insurance_claim(
    data: ClaimSubmitRequest,
    user: User = Depends(deps.require_roles("Admin", "Cashier")),
) -> dict[str, Any]:
    """
    Отправить страховой случай (claim) в страховую компанию
    """
    try:
        claim_data = {
            "policy_number": data.policy_number,
            "patient_id": data.patient_id,
            "visit_id": data.visit_id,
            "services": data.services,
            "total_amount": data.total_amount,
            "diagnosis_code": data.diagnosis_code,
        }

        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "insurance-claim-submit")
        return await gateway.submit_insurance_claim(
            claim_data=claim_data,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Insurance claim error")
        raise _map_gateway_error(error) from error


@router.get("/insurance/claim/{claim_id}", summary="Статус страхового случая")
async def get_insurance_claim_status(
    claim_id: str,
    user: User = Depends(deps.require_roles("Admin", "Cashier")),
) -> dict[str, Any]:
    """
    Получить статус страхового случая
    """
    try:
        gateway = get_interoperability_gateway_service()
        request_id = _build_request_id(user, "insurance-claim-status")
        return await gateway.get_insurance_claim_status(
            claim_id=claim_id,
            request_id=request_id,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Insurance claim status error")
        raise _map_gateway_error(error) from error
