"""
ECG Data Model
Модель для хранения данных ЭКГ исследований
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Float,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base_class import Base


class ECGData(Base):
    """Модель данных ЭКГ исследования"""
    
    __tablename__ = "ecg_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связь с пациентом и визитом
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doctor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    
    # Информация о файле
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # dicom, pdf, image
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    
    # DICOM метаданные
    dicom_metadata: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    
    # Параметры ЭКГ
    heart_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # ЧСС
    pr_interval: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # мс
    qrs_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # мс
    qt_interval: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # мс
    qtc_interval: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # корригированный QT
    
    # Ось сердца
    axis_p: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    axis_qrs: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    axis_t: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Данные кривых (12 отведений)
    waveform_data: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    
    # AI интерпретация
    ai_interpretation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_findings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    
    # Заключение врача
    doctor_conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False)
    urgency_level: Mapped[str] = mapped_column(String(20), default="normal")  # normal, attention, urgent
    
    # Статус
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, analyzed, reviewed, archived
    
    # Временные метки
    recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    patient = relationship("Patient", back_populates="ecg_records", lazy="selectin")
    
    def __repr__(self):
        return f"<ECGData(id={self.id}, patient_id={self.patient_id}, recorded_at={self.recorded_at})>"
