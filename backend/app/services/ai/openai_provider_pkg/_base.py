"""Base infrastructure for openai_provider package.

Split from openai_provider.py (5450 LOC → modular).
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from ....core.config import settings
from ..base_provider import AIRequest, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

_PROVIDER_TIMEOUT = float(getattr(settings, "AI_PROVIDER_TIMEOUT", 180))


class OpenAIProviderMixinBase:
    """Type-hint anchor for OpenAIProvider mixins.

    All mixin classes inherit from this. The actual instance state
    (self.client, self.api_key, self.model) is set up by
    OpenAIProvider.__init__.
    """

    if False:  # TYPE_CHECKING equivalent
        client: AsyncOpenAI
        api_key: str
        model: str
