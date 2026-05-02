from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.activation import activate_key
from app.core.security import get_password_hash
from app.models.clinic import Branch, BranchStatus, ClinicSettings
from app.models.user import User
from app.models.user_profile import (
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
    UserStatus,
)
from app.repositories.setup_repository import SetupRepository
from app.schemas.setup import SetupInitializeIn, SetupInitializeOut, SetupStatusOut

CLINIC_IDENTITY_KEY = "clinic_name"
SETUP_CLINIC_KEYS = {
    "clinic_name": lambda payload: payload.clinic.name,
    "clinic_address": lambda payload: payload.clinic.address,
    "clinic_phone": lambda payload: payload.clinic.phone,
    "clinic_email": lambda payload: str(payload.clinic.email) if payload.clinic.email else None,
    "clinic_timezone": lambda payload: payload.clinic.timezone,
    "clinic_logo_url": lambda payload: payload.clinic.logo_url,
}


class SetupService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SetupRepository(db)

    def get_status(self) -> SetupStatusOut:
        return SetupStatusOut(initialized=self.is_initialized())

    def is_initialized(self) -> bool:
        clinic_setting = self.repo.get_setting(CLINIC_IDENTITY_KEY)
        clinic_name = None
        if clinic_setting:
            clinic_name = str(clinic_setting.value).strip() if clinic_setting.value else ""
        return bool(
            clinic_name
            and self.repo.count_branches() > 0
            and self.repo.count_active_admins() > 0
        )

    def initialize(self, payload: SetupInitializeIn) -> SetupInitializeOut:
        if self.is_initialized():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Deployment is already initialized",
            )

        try:
            self._upsert_clinic_settings(payload)
            branch = self._create_branch(payload)
            admin = self._create_admin(payload)

            activation_applied = False
            if payload.activation_key:
                activation = activate_key(
                    self.db,
                    key=payload.activation_key,
                    commit=False,
                )
                if not activation.ok:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Activation failed: {activation.reason or 'UNKNOWN'}",
                    )
                activation_applied = True

            self.db.commit()
            self.db.refresh(branch)
            self.db.refresh(admin)

            return SetupInitializeOut(
                initialized=True,
                branch_id=branch.id,
                admin_user_id=admin.id,
                activation_applied=activation_applied,
            )
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize deployment: {exc}",
            ) from exc

    def _upsert_clinic_settings(self, payload: SetupInitializeIn) -> None:
        for key, value_factory in SETUP_CLINIC_KEYS.items():
            value = value_factory(payload)
            row = self.repo.get_setting(key)
            if row:
                row.value = value
                row.category = row.category or "clinic"
            else:
                self.db.add(
                    ClinicSettings(
                        key=key,
                        value=value,
                        category="clinic",
                    )
                )
        self.db.flush()

    def _create_branch(self, payload: SetupInitializeIn) -> Branch:
        branch_code = self._build_branch_code(payload.branch.code, payload.branch.name)
        branch = Branch(
            name=payload.branch.name,
            code=branch_code,
            address=payload.branch.address,
            phone=payload.branch.phone,
            email=str(payload.branch.email) if payload.branch.email else None,
            status=BranchStatus.ACTIVE,
            timezone=payload.branch.timezone or payload.clinic.timezone,
            capacity=payload.branch.capacity,
        )
        self.db.add(branch)
        self.db.flush()
        return branch

    def _create_admin(self, payload: SetupInitializeIn) -> User:
        existing_username = self.repo.find_user_by_username(payload.admin.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin username is already in use",
            )

        existing_email = self.repo.find_user_by_email(str(payload.admin.email))
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin email is already in use",
            )

        user = User(
            username=payload.admin.username,
            full_name=payload.admin.full_name,
            email=str(payload.admin.email),
            hashed_password=get_password_hash(payload.admin.password),
            role="Admin",
            is_active=True,
            is_superuser=True,
            must_change_password=False,
        )
        self.db.add(user)
        self.db.flush()

        profile = UserProfile(
            user_id=user.id,
            full_name=payload.admin.full_name,
            status=UserStatus.ACTIVE,
            phone=payload.branch.phone,
            timezone=payload.clinic.timezone,
        )
        self.db.add(profile)
        self.db.flush()

        self.db.add(
            UserPreferences(
                user_id=user.id,
                profile_id=profile.id,
                timezone=payload.clinic.timezone,
            )
        )
        self.db.add(
            UserNotificationSettings(
                user_id=user.id,
                profile_id=profile.id,
            )
        )
        self.db.flush()
        return user

    def _build_branch_code(self, requested_code: str | None, branch_name: str) -> str:
        existing_codes = self.repo.get_existing_branch_codes()
        base = self._normalize_branch_code(requested_code or branch_name)
        if not base:
            base = "main"

        candidate = base[:20]
        suffix = 2
        while candidate.lower() in existing_codes:
            suffix_text = str(suffix)
            candidate = f"{base[: max(1, 20 - len(suffix_text))]}{suffix_text}"
            suffix += 1
        return candidate

    @staticmethod
    def _normalize_branch_code(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
        normalized = normalized.strip("-")
        return normalized or ""
