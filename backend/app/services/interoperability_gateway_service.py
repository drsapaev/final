from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from app.domain.contracts.interoperability_contracts import (
    IntegrationRegistryContract,
    IntegrationRegistryContractFacade,
)
from app.services.external_integration_service import (
    IntegrationType,
    get_integration_manager,
)

logger = logging.getLogger(__name__)


class IntegrationUnavailableError(RuntimeError):
    """Raised when the requested integration is not configured."""

    def __init__(self, integration_type: IntegrationType) -> None:
        self.integration_type = integration_type
        super().__init__(f"{integration_type.value} integration unavailable")


class IntegrationCapabilityError(RuntimeError):
    """Raised when integration does not expose the required capability."""

    def __init__(self, integration_type: IntegrationType, capability: str) -> None:
        self.integration_type = integration_type
        self.capability = capability
        super().__init__(
            f"{integration_type.value} integration does not support '{capability}'"
        )


class InteroperabilityGatewayService:
    """Stable service contract for external integration endpoints."""

    def __init__(
        self,
        manager_factory: Callable[[], IntegrationRegistryContract] | None = None,
    ) -> None:
        self._manager_factory = manager_factory or get_integration_manager

    def get_available_integrations(self, request_id: str | None = None) -> list[str]:
        logger.info(
            "interoperability_gateway.get_available_integrations request_id=%s",
            request_id or "-",
        )
        registry = self._get_registry(request_id)
        return registry.get_available_integrations(request_id=request_id)

    async def verify_patient_all(
        self,
        identifier: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.verify_patient_all request_id=%s identifier=%s",
            request_id or "-",
            identifier,
        )
        registry = self._get_registry(request_id)
        return await registry.verify_patient_all(identifier=identifier, request_id=request_id)

    async def verify_patient(
        self,
        integration_type: IntegrationType,
        identifier: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.verify_patient request_id=%s integration=%s identifier=%s",
            request_id or "-",
            integration_type.value,
            identifier,
        )
        return await self._invoke_capability(
            integration_type=integration_type,
            capability="verify_patient",
            request_id=request_id,
            identifier=identifier,
        )

    async def get_dmed_history(
        self,
        pinfl: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.get_dmed_history request_id=%s pinfl=%s",
            request_id or "-",
            pinfl,
        )
        return await self._invoke_capability(
            integration_type=IntegrationType.DMED,
            capability="get_patient_history",
            request_id=request_id,
            pinfl=pinfl,
        )

    async def get_egov_benefits(
        self,
        pinfl: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.get_egov_benefits request_id=%s pinfl=%s",
            request_id or "-",
            pinfl,
        )
        return await self._invoke_capability(
            integration_type=IntegrationType.EGOV,
            capability="check_benefits",
            request_id=request_id,
            pinfl=pinfl,
        )

    async def authorize_insurance_service(
        self,
        policy_number: str,
        service_code: str,
        estimated_cost: float,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.authorize_insurance_service request_id=%s policy_number=%s service_code=%s",
            request_id or "-",
            policy_number,
            service_code,
        )
        return await self._invoke_capability(
            integration_type=IntegrationType.INSURANCE,
            capability="authorize_service",
            request_id=request_id,
            policy_number=policy_number,
            service_code=service_code,
            estimated_cost=estimated_cost,
        )

    async def submit_insurance_claim(
        self,
        claim_data: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.submit_insurance_claim request_id=%s policy_number=%s visit_id=%s",
            request_id or "-",
            claim_data.get("policy_number"),
            claim_data.get("visit_id"),
        )
        return await self._invoke_capability(
            integration_type=IntegrationType.INSURANCE,
            capability="submit_claim",
            request_id=request_id,
            claim_data=claim_data,
        )

    async def get_insurance_claim_status(
        self,
        claim_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "interoperability_gateway.get_insurance_claim_status request_id=%s claim_id=%s",
            request_id or "-",
            claim_id,
        )
        return await self._invoke_capability(
            integration_type=IntegrationType.INSURANCE,
            capability="get_claim_status",
            request_id=request_id,
            claim_id=claim_id,
        )

    def _get_registry(
        self,
        request_id: str | None = None,
    ) -> IntegrationRegistryContractFacade:
        logger.debug(
            "interoperability_gateway._get_registry.entry request_id=%s",
            request_id or "-",
        )
        registry = self._manager_factory()
        facade = IntegrationRegistryContractFacade(registry)
        logger.debug(
            "interoperability_gateway._get_registry.exit request_id=%s registry_type=%s",
            request_id or "-",
            type(registry).__name__,
        )
        return facade

    async def _invoke_capability(
        self,
        integration_type: IntegrationType,
        capability: str,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        logger.debug(
            "interoperability_gateway._invoke_capability.entry request_id=%s integration=%s capability=%s kwargs=%s",
            request_id or "-",
            integration_type.value,
            capability,
            sorted(kwargs.keys()),
        )
        registry = self._get_registry(request_id)
        integration = registry.get_integration(
            integration_type=integration_type,
            request_id=request_id,
        )

        if integration is None:
            logger.error(
                "interoperability_gateway.integration_missing request_id=%s integration=%s",
                request_id or "-",
                integration_type.value,
            )
            raise IntegrationUnavailableError(integration_type)

        raw_method = getattr(integration, capability, None)
        if not callable(raw_method):
            logger.error(
                "interoperability_gateway.capability_missing request_id=%s integration=%s capability=%s",
                request_id or "-",
                integration_type.value,
                capability,
            )
            raise IntegrationCapabilityError(integration_type, capability)

        try:
            result = raw_method(**kwargs)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            logger.exception(
                "interoperability_gateway._invoke_capability.failed request_id=%s integration=%s capability=%s",
                request_id or "-",
                integration_type.value,
                capability,
            )
            raise

        if not isinstance(result, dict):
            logger.error(
                "interoperability_gateway.invalid_response request_id=%s integration=%s capability=%s response_type=%s",
                request_id or "-",
                integration_type.value,
                capability,
                type(result).__name__,
            )
            return {"success": False, "error": "Invalid integration response"}

        logger.debug(
            "interoperability_gateway._invoke_capability.exit request_id=%s integration=%s capability=%s keys=%s",
            request_id or "-",
            integration_type.value,
            capability,
            sorted(result.keys()),
        )
        return result


_gateway: InteroperabilityGatewayService | None = None


def get_interoperability_gateway_service() -> InteroperabilityGatewayService:
    global _gateway
    if _gateway is None:
        _gateway = InteroperabilityGatewayService()
    return _gateway
