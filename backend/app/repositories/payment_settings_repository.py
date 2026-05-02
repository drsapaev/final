"""Repository helpers for payment settings flows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings


class PaymentSettingsRepository:
    """Encapsulates ORM operations for payment settings."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> ClinicSettings | None:
        return self.db.query(ClinicSettings).filter(ClinicSettings.key == key).first()

    def save_by_key(self, *, key: str, value: str, description: str) -> None:
        settings_record = self.get_by_key(key)
        if settings_record:
            settings_record.value = value
            if description:
                settings_record.description = description
        else:
            settings_record = ClinicSettings(
                key=key,
                value=value,
                description=description,
            )
            self.db.add(settings_record)
        self.db.commit()
