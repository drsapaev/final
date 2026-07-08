"""mock_provider_pkg — split from mock_provider.py (4669 LOC).

Re-exports MockProvider for backward compatibility.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._analytics import AnalyticsMixin
from app.services.ai.mock_provider_pkg._base import (
        AIRequest,  # noqa: F401,
        AIResponse,  # noqa: F401,
    BaseAIProvider,
        MockProviderMixinBase,  # noqa: F401,
        logger,  # noqa: F401,
)
from app.services.ai.mock_provider_pkg._clinical import ClinicalMixin
from app.services.ai.mock_provider_pkg._core import CoreMixin
from app.services.ai.mock_provider_pkg._documentation import DocumentationMixin
from app.services.ai.mock_provider_pkg._imaging import ImagingMixin
from app.services.ai.mock_provider_pkg._risk import RiskMixin
from app.services.ai.mock_provider_pkg._scheduling import SchedulingMixin
from app.services.ai.mock_provider_pkg._text import TextMixin
from app.services.ai.mock_provider_pkg._treatment import TreatmentMixin
from app.services.ai.mock_provider_pkg._triage import TriageMixin

__all__ = ["MockProvider"]


class MockProvider(
    CoreMixin,
    ClinicalMixin,
    ImagingMixin,
    TreatmentMixin,
    RiskMixin,
    TextMixin,
    SchedulingMixin,
    DocumentationMixin,
    AnalyticsMixin,
    TriageMixin,
    BaseAIProvider,
):
    """Mock провайдер для демонстрации функционала без реального API.

    Composed of focused mixin modules under mock_provider_pkg/.
    """

    def __init__(self, api_key: str = "mock", model: str | None = None):
        super().__init__(api_key, model)
