"""openai_provider_pkg — split from openai_provider.py (5450 LOC).

Re-exports OpenAIProvider for backward compatibility.
"""
from __future__ import annotations

from openai import AsyncOpenAI

from app.services.ai.openai_provider_pkg._analytics import AnalyticsMixin
from app.services.ai.openai_provider_pkg._base import (
    _PROVIDER_TIMEOUT,
        AIRequest,  # noqa: F401,
        AIResponse,  # noqa: F401,
    BaseAIProvider,
        OpenAIProviderMixinBase,  # noqa: F401,
        logger,  # noqa: F401,
)
from app.services.ai.openai_provider_pkg._clinical import ClinicalMixin
from app.services.ai.openai_provider_pkg._core import CoreMixin
from app.services.ai.openai_provider_pkg._documentation import DocumentationMixin
from app.services.ai.openai_provider_pkg._imaging import ImagingMixin
from app.services.ai.openai_provider_pkg._risk import RiskMixin
from app.services.ai.openai_provider_pkg._scheduling import SchedulingMixin
from app.services.ai.openai_provider_pkg._text import TextMixin
from app.services.ai.openai_provider_pkg._treatment import TreatmentMixin

__all__ = ["OpenAIProvider"]


class OpenAIProvider(
    CoreMixin,
    ClinicalMixin,
    ImagingMixin,
    TreatmentMixin,
    RiskMixin,
    TextMixin,
    SchedulingMixin,
    DocumentationMixin,
    AnalyticsMixin,
    BaseAIProvider,
):
    """Провайдер OpenAI (GPT-4, GPT-3.5).

    Composed of focused mixin modules under openai_provider_pkg/.
    """

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key, model)
        self.client = AsyncOpenAI(api_key=api_key, timeout=_PROVIDER_TIMEOUT)
