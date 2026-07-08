"""
Сервис для генерации расширенных отчетов
"""

import csv
import json
import logging
import os
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Any

import pandas as pd
from jinja2 import Template
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService

logger = logging.getLogger(__name__)



class ReportingServiceMixinBase:
    """Type-hint anchor."""










































































































































