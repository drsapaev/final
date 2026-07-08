"""
Сервис для печати документов
Основа: detail.md стр. 3721-3888, passport.md стр. 1925-2063
"""

import asyncio
import json
import logging
import os
import platform
import re
import socket
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import serial
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from app.crud import print_config as crud_print
from app.models.print_config import PrinterConfig, PrintJob, PrintTemplate
from app.models.user import User

logger = logging.getLogger(__name__)
LEGACY_COMMENT_BLOCK_RE = re.compile(r"{% comment %}.*?{% endcomment %}", re.S)
THERMAL_PRINTER_KEYWORDS = (
    "thermal",
    "therm",
    "ticket",
    "receipt",
    "pos",
    "escpos",
    "receipt printer",
    "ticket printer",
    "xprinter",
    "epson",
    "star",
    "bixolon",
    "pos58",
    "80mm",
    "58mm",
)
LAB_PRINTER_KEYWORDS = (
    "laser",
    "laserjet",
    "office",
    "canon",
    "brother",
    "xerox",
    "hp",
    "mfp",
    "a4",
    "pdf",
)
PRESCRIPTION_PRINTER_KEYWORDS = (
    "prescription",
    "rx",
    "a5",
)




class PrintServiceMixinBase:
    """Type-hint anchor."""
    pass
