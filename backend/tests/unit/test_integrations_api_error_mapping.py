from __future__ import annotations

import pytest

from app.services.integrations_api_service import _map_gateway_error
from app.services.interoperability_gateway_service import (
    IntegrationCapabilityError,
    IntegrationType,
    IntegrationUnavailableError,
)


@pytest.mark.parametrize(
    ("integration_type", "expected_detail"),
    [
        (IntegrationType.DMED, "DMED интеграция недоступна"),
        (IntegrationType.EGOV, "eGOV интеграция недоступна"),
        (IntegrationType.INSURANCE, "Страховая интеграция недоступна"),
    ],
)
def test_map_gateway_error_for_unavailable_integrations(
    integration_type: IntegrationType,
    expected_detail: str,
) -> None:
    error = IntegrationUnavailableError(integration_type)

    mapped = _map_gateway_error(error)

    assert mapped.status_code == 503
    assert mapped.detail == expected_detail


@pytest.mark.parametrize(
    ("integration_type", "capability", "expected_detail"),
    [
        (IntegrationType.DMED, "get_patient_history", "DMED интеграция некорректна"),
        (IntegrationType.EGOV, "check_benefits", "eGOV интеграция некорректна"),
        (
            IntegrationType.INSURANCE,
            "authorize_service",
            "Страховая интеграция некорректна",
        ),
    ],
)
def test_map_gateway_error_for_capability_mismatch(
    integration_type: IntegrationType,
    capability: str,
    expected_detail: str,
) -> None:
    error = IntegrationCapabilityError(integration_type, capability)

    mapped = _map_gateway_error(error)

    assert mapped.status_code == 503
    assert mapped.detail == expected_detail


def test_map_gateway_error_for_unknown_capability_uses_fallback_message() -> None:
    error = IntegrationCapabilityError(IntegrationType.DMED, "unknown_capability")

    mapped = _map_gateway_error(error)

    assert mapped.status_code == 503
    assert mapped.detail == "Интеграция dmed не поддерживает unknown_capability"


def test_map_gateway_error_for_generic_error_returns_500() -> None:
    mapped = _map_gateway_error(RuntimeError("boom"))

    assert mapped.status_code == 500
    assert mapped.detail == "boom"
