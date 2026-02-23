from __future__ import annotations

from typing import Any

import pytest

from app.services.external_integration_service import IntegrationType
from app.services.interoperability_gateway_service import (
    IntegrationCapabilityError,
    IntegrationUnavailableError,
    InteroperabilityGatewayService,
)


class _FakeIntegration:
    async def verify_patient(self, identifier: str) -> dict[str, Any]:
        return {"verified": True, "identifier": identifier}

    async def get_patient_history(self, pinfl: str) -> dict[str, Any]:
        return {"success": True, "history_for": pinfl}

    async def check_benefits(self, pinfl: str) -> dict[str, Any]:
        return {"success": True, "benefits_for": pinfl}

    async def authorize_service(
        self,
        policy_number: str,
        service_code: str,
        estimated_cost: float,
    ) -> dict[str, Any]:
        return {
            "authorized": True,
            "policy_number": policy_number,
            "service_code": service_code,
            "estimated_cost": estimated_cost,
        }

    async def submit_claim(self, claim_data: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "claim_id": "claim-1", "payload": claim_data}

    async def get_claim_status(self, claim_id: str) -> dict[str, Any]:
        return {"success": True, "claim_id": claim_id, "status": "approved"}


class _VerifyOnlyIntegration:
    async def verify_patient(self, identifier: str) -> dict[str, Any]:
        return {"verified": True, "identifier": identifier}


class _FakeManager:
    def __init__(self, integrations: dict[IntegrationType, Any]) -> None:
        self._integrations = integrations

    def get_integration(self, integration_type: IntegrationType) -> Any | None:
        return self._integrations.get(integration_type)

    def get_available_integrations(self) -> list[str]:
        return [integration.value for integration in self._integrations]

    async def verify_patient_all(self, identifier: str) -> dict[str, Any]:
        return {
            integration_type.value: await integration.verify_patient(identifier)
            for integration_type, integration in self._integrations.items()
        }


def _gateway_with(integrations: dict[IntegrationType, Any]) -> InteroperabilityGatewayService:
    manager = _FakeManager(integrations=integrations)
    return InteroperabilityGatewayService(manager_factory=lambda: manager)


def test_get_available_integrations_returns_registry_values() -> None:
    gateway = _gateway_with(
        integrations={
            IntegrationType.DMED: _FakeIntegration(),
            IntegrationType.EGOV: _FakeIntegration(),
        }
    )

    available = gateway.get_available_integrations(request_id="req-1")

    assert available == ["dmed", "egov"]


@pytest.mark.asyncio
async def test_verify_patient_all_delegates_to_registry() -> None:
    gateway = _gateway_with(integrations={IntegrationType.DMED: _FakeIntegration()})

    result = await gateway.verify_patient_all(identifier="12345", request_id="req-2")

    assert result["dmed"]["verified"] is True
    assert result["dmed"]["identifier"] == "12345"


@pytest.mark.asyncio
async def test_verify_patient_raises_when_integration_missing() -> None:
    gateway = _gateway_with(integrations={})

    with pytest.raises(IntegrationUnavailableError) as exc_info:
        await gateway.verify_patient(
            integration_type=IntegrationType.DMED,
            identifier="12345",
            request_id="req-3",
        )

    assert exc_info.value.integration_type == IntegrationType.DMED


@pytest.mark.asyncio
async def test_get_dmed_history_raises_when_capability_missing() -> None:
    gateway = _gateway_with(
        integrations={IntegrationType.DMED: _VerifyOnlyIntegration()}
    )

    with pytest.raises(IntegrationCapabilityError) as exc_info:
        await gateway.get_dmed_history(pinfl="111111", request_id="req-4")

    assert exc_info.value.integration_type == IntegrationType.DMED
    assert exc_info.value.capability == "get_patient_history"


@pytest.mark.asyncio
async def test_submit_insurance_claim_uses_claim_capability() -> None:
    gateway = _gateway_with(
        integrations={IntegrationType.INSURANCE: _FakeIntegration()}
    )
    claim_data = {"policy_number": "P-1", "visit_id": 10}

    result = await gateway.submit_insurance_claim(
        claim_data=claim_data,
        request_id="req-5",
    )

    assert result["success"] is True
    assert result["payload"]["policy_number"] == "P-1"
