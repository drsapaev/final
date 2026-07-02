"""
Odontogram Model
Модель для хранения данных одонтограммы (стоматологической карты зубов)
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Odontogram(Base):
    """Модель одонтограммы пациента"""

    __tablename__ = "odontograms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Связь с пациентом и визитом
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Тип одонтограммы
    chart_type: Mapped[str] = mapped_column(String(20), default="adult")  # adult, child

    # Данные по каждому зубу (JSON объект с 32 зубами)
    # Формат: { "11": {...}, "12": {...}, ..., "48": {...} }
    teeth_data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Легенда статусов зубов:
    # healthy (▢) - здоровый
    # caries (🔴) - кариес
    # filling (🔵) - пломба
    # crown (🟢) - коронка
    # extraction (⬜) - удалён
    # implant (🟡) - имплант
    # root_canal - лечение канала
    # periodontal - пародонтит
    # bridge - мост
    # temporary - временная пломба

    # Заметки и комментарии
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # История изменений
    change_history: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)

    # Флаги
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)  # Первичный осмотр

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Odontogram(id={self.id}, patient_id={self.patient_id}, type={self.chart_type})>"

    def update_tooth(self, tooth_id: str, status: str, notes: str = None, surfaces: dict = None):
        """
        Обновляет статус зуба

        Args:
            tooth_id: Номер зуба (11-18, 21-28, 31-38, 41-48)
            status: Статус зуба
            notes: Заметки по зубу
            surfaces: Поверхности зуба (O, M, D, B, L - для детализации)
        """
        if not self.teeth_data:
            self.teeth_data = {}

        old_status = self.teeth_data.get(tooth_id, {}).get('status', 'healthy')

        self.teeth_data[tooth_id] = {
            'status': status,
            'notes': notes,
            'surfaces': surfaces or {},
            'updated_at': datetime.utcnow().isoformat(),
        }

        # Записываем в историю
        if not self.change_history:
            self.change_history = []

        self.change_history.append({
            'tooth_id': tooth_id,
            'old_status': old_status,
            'new_status': status,
            'timestamp': datetime.utcnow().isoformat(),
        })

        self.updated_at = datetime.utcnow()

    def get_tooth(self, tooth_id: str) -> dict:
        """Получает данные по зубу"""
        if not self.teeth_data:
            return {'status': 'healthy', 'notes': None, 'surfaces': {}}
        return self.teeth_data.get(tooth_id, {'status': 'healthy', 'notes': None, 'surfaces': {}})

    def get_summary(self) -> dict:
        """Получает сводку по одонтограмме"""
        if not self.teeth_data:
            return {
                'total_teeth': 32,
                'healthy': 32,
                'treated': 0,
                'missing': 0,
                'with_issues': 0,
            }

        summary = {
            'total_teeth': 32,
            'healthy': 0,
            'treated': 0,
            'missing': 0,
            'with_issues': 0,
        }

        for _tooth_id, data in self.teeth_data.items():
            status = data.get('status', 'healthy')
            if status == 'healthy':
                summary['healthy'] += 1
            elif status in ('filling', 'crown', 'implant', 'root_canal'):
                summary['treated'] += 1
            elif status == 'extraction':
                summary['missing'] += 1
            else:
                summary['with_issues'] += 1

        # Добавляем здоровые зубы которых нет в данных
        teeth_in_data = len(self.teeth_data)
        summary['healthy'] += 32 - teeth_in_data

        return summary


class ToothHistory(Base):
    """История изменений по отдельному зубу"""

    __tablename__ = "tooth_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    odontogram_id: Mapped[int] = mapped_column(
        ForeignKey("odontograms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tooth_id: Mapped[str] = mapped_column(String(4), nullable=False, index=True)  # 11-48

    # Изменение
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Детали
    treatment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Кто изменил
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    def __repr__(self):
        return f"<ToothHistory(id={self.id}, tooth={self.tooth_id}, {self.old_status}->{self.new_status})>"
