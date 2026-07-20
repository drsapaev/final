"""Dedicated PDF renderer for structured laboratory reports."""

from __future__ import annotations

import base64  # noqa: F401
import io  # noqa: F401
import logging  # noqa: F401
from datetime import UTC, datetime  # noqa: F401
from html import escape  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any  # noqa: F401
from urllib.parse import unquote, urlparse  # noqa: F401

from jinja2 import Environment, FileSystemLoader  # noqa: F401

from app.services.pdf_service import (  # noqa: F401
    REPORTLAB_AVAILABLE,
    _load_weasyprint_components,
)

logger = logging.getLogger(__name__)




class LabReportPDFServiceMixinBase:
    """Type-hint anchor."""
    pass
