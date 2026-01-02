"""
QueueProfile Model - Dynamic Queue Tabs Configuration

Enables admin-configurable queue tabs without code changes.

SSOT Rules:
- QueueProfile defines which queue_tags belong to which tab
- Service.queue_tag → QueueProfile.queue_tags[] determines routing
- Frontend renders tabs from API, NOT hardcoded
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueProfile(Base):
    """
    Dynamic queue profile/tab configuration.
    
    Each profile represents a tab in the Registrar Panel.
    Entries are filtered by matching entry's queue_tag to profile's queue_tags.
    """
    __tablename__ = "queue_profiles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Unique key for frontend reference (e.g., "cardiology", "ecg")
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    
    # Display title
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    title_ru: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Which queue_tags belong to this profile
    # e.g., ["cardio", "echokg"] for cardiology tab
    queue_tags: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    
    # Optional: Link to department_key for additional filtering
    department_key: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    
    # Tab order (lower = first) - named display_order to avoid SQL reserved word
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Is this profile active/visible?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # ⭐ NEW: Show this profile on QR join page for patient self-registration
    show_on_qr_page: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Optional UI configuration
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "Heart", "Activity"
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g., "#FF5733"
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, onupdate=datetime.utcnow, nullable=True
    )


# Initial profiles for seeding
INITIAL_QUEUE_PROFILES = [
    {
        "key": "cardiology",
        "title": "Cardiology",
        "title_ru": "Кардиология",
        "queue_tags": ["cardio", "cardiology", "cardiology_common"],
        "department_key": "cardiology",
        "order": 1,
        "icon": "Heart",
        "color": "#E53E3E",
    },
    {
        "key": "ecg",
        "title": "ECG",
        "title_ru": "ЭКГ",
        "queue_tags": ["ecg", "echokg"],
        "department_key": None,
        "order": 2,
        "icon": "Activity",
        "color": "#3182CE",
    },
    {
        "key": "dermatology",
        "title": "Dermatology",
        "title_ru": "Дерматология",
        "queue_tags": ["derma", "dermatology"],
        "department_key": "dermatology",
        "order": 3,
        "icon": "Sparkles",
        "color": "#9F7AEA",
    },
    {
        "key": "stomatology",
        "title": "Dental",
        "title_ru": "Стоматология",
        "queue_tags": ["dental", "stomatology", "dentist"],
        "department_key": "stomatology",
        "order": 4,
        "icon": "Smile",
        "color": "#38A169",
    },
    {
        "key": "lab",
        "title": "Laboratory",
        "title_ru": "Лаборатория",
        "queue_tags": ["lab", "laboratory"],
        "department_key": "laboratory",
        "order": 5,
        "icon": "TestTube",
        "color": "#DD6B20",
    },
    {
        "key": "procedures",
        "title": "Procedures",
        "title_ru": "Процедуры",
        "queue_tags": ["procedures", "physio", "therapy"],
        "department_key": None,
        "order": 6,
        "icon": "Stethoscope",
        "color": "#718096",
    },
    {
        "key": "cosmetology",
        "title": "Cosmetology",
        "title_ru": "Косметология",
        "queue_tags": ["cosmetology"],
        "department_key": "cosmetology",
        "order": 7,
        "icon": "Sparkle",
        "color": "#D53F8C",
    },
    {
        "key": "general",
        "title": "General",
        "title_ru": "Общая очередь",
        "queue_tags": ["general"],
        "department_key": None,
        "order": 99,
        "icon": "Users",
        "color": "#4A5568",
    },
]
