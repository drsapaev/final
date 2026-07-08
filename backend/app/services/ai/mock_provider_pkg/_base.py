"""Base infrastructure for mock_provider package.

Split from mock_provider.py (4669 LOC → modular).
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from ..base_provider import AIRequest, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)


class MockProviderMixinBase:
    """Type-hint anchor for MockProvider mixins."""

    if False:
        api_key: str
        model: str
