"""Dedicated PDF renderer for structured laboratory reports."""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime, UTC
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from jinja2 import Environment, FileSystemLoader

from app.services.pdf_service import REPORTLAB_AVAILABLE, _load_weasyprint_components

logger = logging.getLogger(__name__)




class LabReportPDFServiceMixinBase:
    """Type-hint anchor."""
    pass
