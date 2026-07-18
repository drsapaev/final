"""Base infrastructure for mock_provider package.

Split from mock_provider.py (4669 LOC → modular).
"""
from __future__ import annotations

import asyncio  # noqa: F401
import logging  # noqa: F401
import random  # noqa: F401
from typing import Any  # noqa: F401

from ..base_provider import AIRequest, AIResponse, BaseAIProvider  # noqa: F401

logger = logging.getLogger(__name__)


class MockProviderMixinBase:
    """Type-hint anchor for MockProvider mixins."""

    if False:
        api_key: str
        model: str
