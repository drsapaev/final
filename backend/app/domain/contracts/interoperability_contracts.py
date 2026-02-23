from __future__ import annotations

import logging
from typing import Any, Protocol

from app.domain.contracts.contract_logging import ContractMethodLogger

logger = logging.getLogger(__name__)


class ExternalIntegrationContract(Protocol):
    async def verify_patient(self, identifier: str) -> dict[str, Any]: ...

    async def submit_visit(self, visit_data: dict[str, Any]) -> dict[str, Any]: ...


class DmedCapabilityContract(Protocol):
    async def get_patient_history(self, pinfl: str) -> dict[str, Any]: ...


class EgovCapabilityContract(Protocol):
    async def check_benefits(self, pinfl: str) -> dict[str, Any]: ...


class InsuranceCapabilityContract(Protocol):
    async def authorize_service(
        self,
        policy_number: str,
        service_code: str,
        estimated_cost: float,
    ) -> dict[str, Any]: ...

    async def submit_claim(self, claim_data: dict[str, Any]) -> dict[str, Any]: ...

    async def get_claim_status(self, claim_id: str) -> dict[str, Any]: ...


class IntegrationRegistryContract(Protocol):
    def get_integration(self, integration_type: Any) -> ExternalIntegrationContract | None: ...

    def get_available_integrations(self) -> list[str]: ...

    async def verify_patient_all(self, identifier: str) -> dict[str, Any]: ...


class IntegrationRegistryContractFacade:
    """Contract wrapper with explicit debug logs for interoperability calls."""

    def __init__(self, contract: IntegrationRegistryContract) -> None:
        self._contract = contract
        self._contract_logger = ContractMethodLogger(logger, "interoperability")

    def get_available_integrations(self, request_id: str | None = None) -> list[str]:
        self._contract_logger.log_entry(
            "get_available_integrations",
            request_id,
        )
        integrations = self._contract.get_available_integrations()
        self._contract_logger.log_exit(
            "get_available_integrations",
            request_id,
            integrations=integrations,
        )
        return integrations

    async def verify_patient_all(
        self,
        identifier: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self._contract_logger.log_entry(
            "verify_patient_all",
            request_id,
            identifier=identifier,
        )
        results = await self._contract.verify_patient_all(identifier)
        self._contract_logger.log_exit(
            "verify_patient_all",
            request_id,
            providers=list(results.keys()),
        )
        return results

    def get_integration(
        self,
        integration_type: Any,
        request_id: str | None = None,
    ) -> ExternalIntegrationContract | None:
        self._contract_logger.log_entry(
            "get_integration",
            request_id,
            integration_type=str(integration_type),
        )
        integration = self._contract.get_integration(integration_type)
        self._contract_logger.log_exit(
            "get_integration",
            request_id,
            integration_found=integration is not None,
        )
        return integration
