"""
Сервис для генерации расширенных отчетов
"""

import csv  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
import os  # noqa: F401
from datetime import date, datetime, timedelta  # noqa: F401
from io import StringIO  # noqa: F401
from typing import Any  # noqa: F401

import pandas as pd  # noqa: F401
from jinja2 import Template  # noqa: F401
from sqlalchemy import func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.models.appointment import Appointment  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: F401
from app.models.patient import Patient  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.visit import Visit, VisitService  # noqa: F401

logger = logging.getLogger(__name__)



class ReportingServiceMixinBase:
    """Type-hint anchor."""










































































































































