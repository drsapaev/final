"""Configuration-only registry for Registrar views, isolated from admission."""

from __future__ import annotations

import hashlib
import logging
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.crud import clinic as crud_clinic
from app.models.audit import AuditLog
from app.models.clinic import ClinicSettings, Doctor
from app.models.queue_profile import QueueProfile
from app.models.user import User
from app.schemas.registrar_tabs import (
    AdminRegistrarTabsOut,
    RegistrarProfileFilter,
    RegistrarTabInput,
    RegistrarTabsOut,
    RegistrarTabsUpdate,
    ResolvedRegistrarTab,
    StoredRegistrarTabs,
)
from app.services.registrar_doctor_eligibility import is_named_eligible_real_doctor

logger = logging.getLogger(__name__)
REGISTRAR_TABS_KEY = "registrar_tabs_v1"
REGISTRAR_TABS_CATEGORY = "registrar_tabs"
_LOCK_KEY = int.from_bytes(
    hashlib.sha256(REGISTRAR_TABS_KEY.encode()).digest()[:8], "big", signed=True
)
Target = tuple[Literal["profile", "doctor"], int]


class RegistrarTabsError(Exception):
    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


def is_registrar_tabs_setting_key(key: str) -> bool:
    # Whitespace/case aliases must not provide a bypass around the writer.
    return key.strip().lower() == REGISTRAR_TABS_KEY


def _target(tab: RegistrarTabInput | ResolvedRegistrarTab) -> Target:
    return tab.target_kind, tab.target_id


def _safe_audit_tabs(tabs: list[RegistrarTabInput]) -> list[dict[str, object]]:
    return [
        {
            "target_kind": tab.target_kind,
            "target_id": tab.target_id,
            "visible": tab.visible,
            "title_sha256": (
                hashlib.sha256(tab.title.encode()).hexdigest() if tab.title else None
            ),
        }
        for tab in tabs
    ]


class RegistrarTabsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _row(self, *, lock: bool = False) -> ClinicSettings | None:
        query = self.db.query(ClinicSettings).filter(
            ClinicSettings.key == REGISTRAR_TABS_KEY
        )
        if lock:
            query = query.with_for_update().populate_existing()
        return query.first()

    @staticmethod
    def _stored(row: ClinicSettings | None) -> StoredRegistrarTabs | None:
        if row is None:
            return None
        if row.category != REGISTRAR_TABS_CATEGORY:
            raise RegistrarTabsError(503, "registrar_tabs_invalid_configuration")
        try:
            return StoredRegistrarTabs.model_validate(row.value)
        except ValidationError as exc:
            raise RegistrarTabsError(
                503, "registrar_tabs_invalid_configuration"
            ) from exc

    def _catalog(self) -> dict[Target, ResolvedRegistrarTab]:
        """Use the same eligibility predicates as the canonical doctor roster."""
        catalog: dict[Target, ResolvedRegistrarTab] = {}
        profiles = (
            self.db.query(QueueProfile)
            .order_by(QueueProfile.display_order, QueueProfile.id)
            .all()
        )
        for profile in profiles:
            catalog[("profile", profile.id)] = ResolvedRegistrarTab(
                target_kind="profile",
                target_id=profile.id,
                custom_title=None,
                title=profile.title,
                title_ru=profile.title_ru,
                profile_key=profile.key,
                queue_tags=profile.queue_tags or [],
                icon=profile.icon,
                color=profile.color,
                visible=True,
                available=bool(profile.is_active),
                reason_code=None if profile.is_active else "inactive_target",
            )

        doctors: list[Doctor] = []
        while True:
            page = crud_clinic.get_doctors(
                self.db,
                skip=len(doctors),
                limit=100,
                active_only=True,
                eligible_only=True,
                exclude_internal_only=True,
            )
            doctors.extend(page)
            if len(page) < 100:
                break
        owner_ids = [doctor.user_id for doctor in doctors if doctor.user_id]
        owners = (
            {
                owner.id: owner
                for owner in self.db.query(User).filter(User.id.in_(owner_ids)).all()
            }
            if owner_ids
            else {}
        )
        eligible = [
            doctor
            for doctor in doctors
            if is_named_eligible_real_doctor(doctor, owners.get(doctor.user_id))
        ]
        name_counts: dict[str, int] = {}
        for doctor in eligible:
            name = owners[doctor.user_id].full_name.strip()
            normalized = name.casefold()
            name_counts[normalized] = name_counts.get(normalized, 0) + 1
        for doctor in eligible:
            name = owners[doctor.user_id].full_name.strip()
            if name_counts[name.casefold()] > 1:
                name = f"{name} · #{doctor.id}"
            catalog[("doctor", doctor.id)] = ResolvedRegistrarTab(
                target_kind="doctor",
                target_id=doctor.id,
                custom_title=None,
                title=name,
                title_ru=name,
                profile_key=None,
                queue_tags=[],
                icon="UserCheck",
                color=None,
                visible=True,
                available=True,
                reason_code=None,
            )
        return catalog

    @staticmethod
    def _legacy(catalog: dict[Target, ResolvedRegistrarTab]) -> list[RegistrarTabInput]:
        return [
            RegistrarTabInput(target_kind=tab.target_kind, target_id=tab.target_id)
            for tab in catalog.values()
            if tab.available
        ]

    def _resolve(
        self, tabs: list[RegistrarTabInput], catalog: dict[Target, ResolvedRegistrarTab]
    ) -> list[ResolvedRegistrarTab]:
        missing_doctor_ids = [
            tab.target_id
            for tab in tabs
            if tab.target_kind == "doctor" and _target(tab) not in catalog
        ]
        existing_doctors = (
            {
                value
                for (value,) in self.db.query(Doctor.id)
                .filter(Doctor.id.in_(missing_doctor_ids))
                .all()
            }
            if missing_doctor_ids
            else set()
        )
        resolved: list[ResolvedRegistrarTab] = []
        for tab in tabs:
            current = catalog.get(_target(tab))
            if current is None:
                reason = (
                    "inactive_target"
                    if tab.target_kind == "doctor" and tab.target_id in existing_doctors
                    else "missing_target"
                )
                # Never retain a deleted target's label/PII in settings. IDs
                # remain stable and cannot bind a newly created replacement.
                current = ResolvedRegistrarTab(
                    target_kind=tab.target_kind,
                    target_id=tab.target_id,
                    custom_title=None,
                    title=f"#{tab.target_id}",
                    title_ru=None,
                    profile_key=None,
                    queue_tags=[],
                    icon=None,
                    color=None,
                    visible=tab.visible,
                    available=False,
                    reason_code=reason,
                )
            resolved.append(
                current.model_copy(
                    update={
                        "custom_title": tab.title,
                        "title": tab.title or current.title,
                        "title_ru": tab.title or current.title_ru,
                        "visible": tab.visible,
                    }
                )
            )
        return resolved

    def _output(
        self,
        stored: StoredRegistrarTabs | None,
        catalog: dict[Target, ResolvedRegistrarTab],
        *,
        admin: bool,
    ) -> RegistrarTabsOut | AdminRegistrarTabsOut:
        tabs = stored.tabs if stored is not None else self._legacy(catalog)
        resolved = self._resolve(tabs, catalog)
        configured_profiles = {
            tab.target_id: tab for tab in resolved if tab.target_kind == "profile"
        }
        profile_filters = []
        for option in catalog.values():
            if option.target_kind != "profile" or option.profile_key is None:
                continue
            display = configured_profiles.get(option.target_id, option)
            profile_filters.append(
                RegistrarProfileFilter(
                    key=option.profile_key,
                    queue_tags=option.queue_tags,
                    title=display.title,
                    title_ru=display.title_ru,
                )
            )
        common = {
            "mode": "configured" if stored is not None else "legacy",
            "version": stored.version if stored is not None else 0,
            "profile_filters": profile_filters,
        }
        if admin:
            return AdminRegistrarTabsOut(
                **common, tabs=resolved, options=list(catalog.values())
            )
        return RegistrarTabsOut(
            **common, tabs=[tab for tab in resolved if tab.visible and tab.available]
        )

    def read(self, *, admin: bool = False) -> RegistrarTabsOut | AdminRegistrarTabsOut:
        # GET has no flush, commit, seeding, creation of queues, or token work.
        return self._output(self._stored(self._row()), self._catalog(), admin=admin)

    def update(
        self,
        update: RegistrarTabsUpdate,
        *,
        actor_user_id: int,
        request_id: str,
        actor_role: str | None = None,
    ) -> AdminRegistrarTabsOut:
        if self.db.get_bind().dialect.name != "postgresql":
            raise RegistrarTabsError(503, "registrar_tabs_postgresql_required")
        try:
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY}
            )
            row = self._row(lock=True)
            current = self._stored(row)
            version = current.version if current else 0
            if update.expected_version != version:
                raise RegistrarTabsError(409, "registrar_tabs_version_conflict")
            catalog = self._catalog()
            old_tabs = current.tabs if current is not None else self._legacy(catalog)
            retained = {_target(tab) for tab in old_tabs}
            for tab in update.tabs:
                option = catalog.get(_target(tab))
                if (option is None or not option.available) and _target(
                    tab
                ) not in retained:
                    raise RegistrarTabsError(422, "registrar_tabs_target_unavailable")
            stored = StoredRegistrarTabs(version=version + 1, tabs=update.tabs)
            if row is None:
                row = ClinicSettings(
                    key=REGISTRAR_TABS_KEY, category=REGISTRAR_TABS_CATEGORY
                )
                self.db.add(row)
            row.value = stored.model_dump(mode="json")
            row.updated_by = actor_user_id
            self.db.flush()
            self.db.add(
                AuditLog(
                    action="registrar_tabs_updated",
                    event_type="REGISTRAR_TABS_UPDATED",
                    entity_type="clinic_settings",
                    entity_id=row.id,
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                    actor_type="staff",
                    outcome="success",
                    reason_code={"code": update.reason},
                    payload={
                        "old_version": version,
                        "new_version": stored.version,
                        "old": _safe_audit_tabs(old_tabs),
                        "new": _safe_audit_tabs(update.tabs),
                        "request_id": request_id[:128],
                    },
                )
            )
            self.db.flush()
            output = self._output(stored, catalog, admin=True)
            self.db.commit()
            logger.info(
                "Registrar tab configuration updated actor_id=%s version=%s",
                actor_user_id,
                stored.version,
            )
            return AdminRegistrarTabsOut.model_validate(output)
        except RegistrarTabsError:
            self.db.rollback()
            raise
        except Exception:
            self.db.rollback()
            logger.error(
                "Registrar tab configuration update failed actor_id=%s", actor_user_id
            )
            raise
