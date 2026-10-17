from __future__ import annotations

from types import SimpleNamespace

from app.api.v1.endpoints.qr_queue._specialists import get_available_specialists
from app.models.clinic import Doctor
from app.models.queue_profile import QueueProfile


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self._offset = 0
        self._limit = None

    def filter(self, *_conditions):
        return self

    def join(self, *_entities, **_kwargs):
        return self

    def options(self, *_options):
        return self

    def order_by(self, *_expressions):
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        end = None if self._limit is None else self._offset + self._limit
        return self.rows[self._offset : end]


class _Database:
    def __init__(self, doctors, profiles):
        self.queries = {Doctor: doctors, QueueProfile: profiles}

    def query(self, model):
        return _Query(self.queries[model])


def _doctor(doctor_id: int, name: str, specialty: str):
    return SimpleNamespace(
        id=doctor_id,
        specialty=specialty,
        cabinet=f"{doctor_id}",
        user=SimpleNamespace(full_name=name),
    )


def test_available_specialists_filters_before_pagination_and_reports_full_total(
    monkeypatch,
):
    from datetime import date

    from app.services import queue_profile_availability
    from app.services.queue_service import queue_service

    profiles = [
        QueueProfile(
            key="cardiology",
            title="Cardiology",
            title_ru="Cardiology",
            queue_tags=["cardiology"],
            is_active=True,
            show_on_qr_page=True,
        ),
        QueueProfile(
            key="closed-direction",
            title="Closed direction",
            title_ru="Closed direction",
            queue_tags=["closed-direction"],
            is_active=True,
            show_on_qr_page=True,
        ),
    ]
    availability = {
        profiles[0]: SimpleNamespace(
            state="available",
            is_available=True,
            parent_department_key=None,
        ),
        profiles[1]: SimpleNamespace(
            state="unavailable",
            is_available=False,
            parent_department_key=None,
        ),
    }
    monkeypatch.setattr(
        queue_profile_availability,
        "load_queue_profile_availability",
        lambda _db, rows: {profile: availability[profile] for profile in rows},
    )
    from app.crud import clinic as clinic_crud

    monkeypatch.setattr(clinic_crud, "clinic_today", lambda _db: date(2026, 1, 1))
    monkeypatch.setattr(
        queue_service,
        "_qr_profile_owner_scopes_for_catalog",
        lambda _db, rows, *, day: {},
    )

    def resolve_visible_profile(
        _db,
        doctor,
        *,
        profiles,
        availability_by_profile,
        day=None,
        owner_scope_by_profile=None,
    ):
        """Keep this pagination test independent of ORM owner-scope queries."""
        for profile in profiles:
            profile_availability = availability_by_profile.get(profile)
            if (
                doctor.specialty in (profile.queue_tags or [])
                and profile.is_active
                and profile.show_on_qr_page
                and profile_availability is not None
                and profile_availability.is_available
            ):
                return profile
        return None

    monkeypatch.setattr(
        queue_service,
        "_get_qr_visible_profile_for_doctor",
        resolve_visible_profile,
    )
    db = _Database(
        doctors=[
            _doctor(1, "Unmapped", "unmapped"),
            _doctor(2, "Unavailable", "closed-direction"),
            _doctor(3, "Alpha", "cardiology"),
            _doctor(4, "Bravo", "cardiology"),
            _doctor(5, "Charlie", "cardiology"),
        ],
        profiles=profiles,
    )

    response = get_available_specialists(db=db, limit=2, offset=1)

    assert response["total"] == 3
    assert [row["doctor_name"] for row in response["specialists"]] == [
        "Bravo",
        "Charlie",
    ]
