"""Contract tests for the read-only Admin queue directions model."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.crud.queue_admin_directions_read_repository import (
    QueueAdminDirectionsSnapshot,
)
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.online_queue import (
    DailyQueue,
    QueueJoinSession,
    QueueResource,
    QueueToken,
)
from app.models.queue_direction_public_address import QueueDirectionPublicAddress
from app.models.queue_profile import QueueProfile
from app.models.service import Service
from app.models.user import User
from app.models.user_profile import UserProfile


def _admin_headers(admin_user: User) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def test_queue_admin_directions_requires_admin_role(
    client: TestClient, registrar_user: User
) -> None:
    from tests.conftest import mint_access_token

    response = client.get(
        "/api/v1/queue/admin/directions",
        headers={"Authorization": f"Bearer {mint_access_token(registrar_user)}"},
    )

    assert response.status_code == 403


def test_queue_admin_directions_returns_empty_snapshot_without_side_effects(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    monkeypatch,
) -> None:
    from app.services import queue_admin_directions_read_service

    empty_snapshot = QueueAdminDirectionsSnapshot(
        profiles=[],
        services=[],
        resources=[],
        doctors=[],
        daily_queues=[],
        profiles_with_permanent_address=set(),
    )
    monkeypatch.setattr(
        queue_admin_directions_read_service,
        "load_queue_admin_directions_snapshot",
        lambda _db, *, day: empty_snapshot,
    )
    tables = (
        QueueProfile,
        DailyQueue,
        QueueToken,
        QueueJoinSession,
        QueueDirectionPublicAddress,
    )
    before = tuple(db_session.query(model).count() for model in tables)

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    after = tuple(db_session.query(model).count() for model in tables)
    assert response.status_code == 200
    assert response.json() == {
        "as_of_day": "2026-10-17",
        "directions": [],
        "unattached": {"queue_tags": [], "services": [], "resources": []},
    }
    assert after == before


def test_queue_admin_directions_uses_typed_owners_and_separates_precreate(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    doctor_user = User(
        username="aqs_direction_doctor",
        email="aqs-direction-doctor@example.test",
        full_name="Synthetic Queue Doctor",
        hashed_password="not-used",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(doctor_user)
    db_session.flush()
    doctor = Doctor(
        id=1,
        user_id=doctor_user.id,
        specialty="cardiology",
        active=True,
    )
    resource = QueueResource(
        id=1,
        code="aqs-read-ecg",
        queue_tag="ecg",
        display_name="Synthetic ECG resource",
        active=True,
    )
    cardiology = QueueProfile(
        key="aqs-read-cardiology",
        title="Cardiology",
        title_ru="Кардиология",
        queue_tags=["cardiology"],
        is_active=True,
        show_on_qr_page=True,
        display_order=1,
    )
    ecg = QueueProfile(
        key="aqs-read-ecg",
        title="ECG",
        title_ru="ЭКГ",
        queue_tags=["ecg"],
        is_active=True,
        show_on_qr_page=True,
        display_order=2,
    )
    doctor_service = Service(
        name="Synthetic cardiology service",
        active=True,
        queue_tag="cardiology",
        doctor_id=None,
        requires_doctor=False,
    )
    resource_service = Service(
        name="Synthetic ECG service",
        active=True,
        queue_tag="ecg",
        doctor_id=None,
        requires_doctor=False,
    )
    db_session.add_all(
        [doctor, resource, cardiology, ecg, doctor_service, resource_service]
    )
    db_session.commit()
    side_effect_tables = (
        DailyQueue,
        QueueToken,
        QueueJoinSession,
        QueueDirectionPublicAddress,
    )
    before = tuple(db_session.query(model).count() for model in side_effect_tables)

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    assert (
        tuple(db_session.query(model).count() for model in side_effect_tables) == before
    )
    payload = response.json()
    by_key = {row["profile"]["key"]: row for row in payload["directions"]}
    doctor_row = by_key["aqs-read-cardiology"]
    resource_row = by_key["aqs-read-ecg"]
    assert doctor_row["resolved_mode"] == "booking"
    assert doctor_row["public_availability"] is True
    assert doctor_row["booking_targets"] == [
        {
            "owner_type": "doctor",
            "owner_id": 1,
            "queue_tag": "cardiology",
            "label": "Synthetic Queue Doctor",
            "is_active": True,
            "eligible_for_new_booking": True,
            "existing_daily_queue_ids": [],
        }
    ]
    assert doctor_row["precreate_by_tag"][0]["can_precreate"] is False
    assert doctor_row["precreate_by_tag"][0]["reason_codes"] == [
        "no_explicit_service_owner"
    ]
    assert resource_row["resolved_mode"] == "booking"
    assert resource_row["booking_targets"][0]["owner_type"] == "resource"
    assert resource_row["booking_targets"][0]["owner_id"] == 1
    assert resource_row["precreate_by_tag"][0]["can_precreate"] is True
    assert resource_row["precreate_by_tag"][0]["owner_type"] == "resource"
    assert resource_row["precreate_by_tag"][0]["owner_id"] == 1
    assert "patient" not in str(payload).lower()


def test_queue_admin_directions_uses_profile_names_with_bounded_profile_reads(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    profile = QueueProfile(
        key="aqs-t18-doctor-labels",
        title="Dermatology",
        title_ru="Дерматология",
        queue_tags=["dermatology"],
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    named_doctors = [
        (
            "aqs_t18_profile_doctor_one",
            "t18-profile-doctor-one@example.test",
            None,
            "Synthetic Dermatology Doctor One",
        ),
        (
            "aqs_t18_profile_doctor_two",
            "t18-profile-doctor-two@example.test",
            None,
            "Synthetic Dermatology Doctor Two",
        ),
        (
            "aqs_t18_legacy_doctor",
            "t18-legacy-doctor@example.test",
            "Synthetic Legacy Doctor Name",
            None,
        ),
        (
            "aqs_t18_unnamed_doctor",
            "t18-unnamed-doctor@example.test",
            None,
            None,
        ),
    ]
    users: list[User] = []
    doctors: list[Doctor] = []
    user_profiles: list[UserProfile] = []
    for username, email, legacy_name, _profile_name in named_doctors:
        user = User(
            username=username,
            email=email,
            full_name=legacy_name,
            hashed_password="not-used",
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )
        users.append(user)
    db_session.add_all([profile, *users])
    db_session.flush()

    for (_username, _email, _legacy_name, profile_name), user in zip(
        named_doctors, users, strict=True
    ):
        doctor = Doctor(user_id=user.id, specialty="dermatology", active=True)
        doctors.append(doctor)
        if profile_name is not None:
            user_profiles.append(UserProfile(user_id=user.id, full_name=profile_name))
    db_session.add_all([*doctors, *user_profiles])
    db_session.commit()
    db_session.expire_all()

    headers = _admin_headers(admin_user)
    profile_selects: list[str] = []

    def record_profile_selects(
        _connection, _cursor, statement, _parameters, _context, _many
    ) -> None:
        normalized = statement.lower()
        if (
            normalized.lstrip().startswith(("select", "with"))
            and "user_profiles" in normalized
        ):
            profile_selects.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record_profile_selects)
    try:
        response = client.get(
            "/api/v1/queue/admin/directions?day=2026-10-17",
            headers=headers,
        )
    finally:
        event.remove(engine, "before_cursor_execute", record_profile_selects)

    assert response.status_code == 200, response.text
    direction = next(
        row
        for row in response.json()["directions"]
        if row["profile"]["key"] == "aqs-t18-doctor-labels"
    )
    targets = direction["booking_targets"]
    doctor_targets = {
        target["owner_id"]: target
        for target in targets
        if target["owner_type"] == "doctor"
    }
    assert len(doctor_targets) == 4
    assert [target["label"] for target in doctor_targets.values()] == [
        "Synthetic Dermatology Doctor One",
        "Synthetic Dermatology Doctor Two",
        "Synthetic Legacy Doctor Name",
        "dermatology",
    ]
    assert all(
        target["queue_tag"] == "dermatology" for target in doctor_targets.values()
    )
    assert all(target["is_active"] is True for target in doctor_targets.values())
    assert all(
        target["eligible_for_new_booking"] is True for target in doctor_targets.values()
    )
    assert len(profile_selects) == 1, (
        "doctor profile names must be loaded in one bounded query, not once per doctor; "
        f"observed {len(profile_selects)} profile reads"
    )


def test_inactive_resource_with_current_queue_remains_a_typed_target(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    monkeypatch,
) -> None:
    from app.services import queue_admin_directions_read_service

    clinic_day = date(2026, 10, 17)
    monkeypatch.setattr(
        queue_admin_directions_read_service,
        "clinic_today",
        lambda _db: clinic_day,
    )
    resource = QueueResource(
        id=1,
        code="aqs-inactive-resource",
        queue_tag="lab",
        display_name="Synthetic existing lab resource",
        active=False,
    )
    profile = QueueProfile(
        key="aqs-existing-lab",
        title="Existing lab",
        title_ru="Лаборатория",
        queue_tags=["lab"],
        is_active=True,
        show_on_qr_page=True,
        display_order=1,
    )
    db_session.add_all([resource, profile])
    db_session.flush()
    queue = DailyQueue(
        day=date(2026, 10, 17),
        queue_tag="lab",
        queue_resource_id=resource.id,
        specialist_id=None,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    direction = response.json()["directions"][0]
    assert direction["booking_targets"] == [
        {
            "owner_type": "resource",
            "owner_id": 1,
            "queue_tag": "lab",
            "label": "Synthetic existing lab resource",
            "is_active": False,
            "eligible_for_new_booking": True,
            "existing_daily_queue_ids": [queue.id],
        }
    ]
    assert direction["current_day_queues"] == [
        {
            "daily_queue_id": queue.id,
            "queue_tag": "lab",
            "owner_type": "resource",
            "owner_id": 1,
        }
    ]
    assert direction["public_availability"] is True


def test_publication_readiness_uses_clinic_today_not_selected_queue_day(
    client: TestClient,
    db_session: Session,
    admin_user: User,
    monkeypatch,
) -> None:
    from app.api.v1.endpoints.registrar_integration import _queue_profiles
    from app.services import queue_admin_directions_read_service

    clinic_day = date(2026, 10, 18)
    selected_day = date(2026, 10, 17)
    monkeypatch.setattr(
        queue_admin_directions_read_service,
        "clinic_today",
        lambda _db: clinic_day,
    )
    monkeypatch.setattr(_queue_profiles, "clinic_today", lambda _db: clinic_day)

    resource = QueueResource(
        code="aqs-t13-historical-resource",
        queue_tag="aqs-t13-historical-resource-tag",
        display_name="Synthetic historical resource",
        active=False,
    )
    profile = QueueProfile(
        key="aqs-t13-historical-resource-profile",
        title="Historical resource direction",
        title_ru="Историческое ресурсное направление",
        queue_tags=[resource.queue_tag],
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    db_session.add_all([resource, profile])
    db_session.flush()
    historical_queue = DailyQueue(
        day=selected_day,
        queue_tag=resource.queue_tag,
        queue_resource_id=resource.id,
        specialist_id=None,
        active=True,
    )
    db_session.add(historical_queue)
    db_session.commit()

    response = client.get(
        f"/api/v1/queue/admin/directions?day={selected_day.isoformat()}",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    direction = response.json()["directions"][0]
    assert response.json()["as_of_day"] == selected_day.isoformat()
    assert direction["current_day_queues"] == [
        {
            "daily_queue_id": historical_queue.id,
            "queue_tag": resource.queue_tag,
            "owner_type": "resource",
            "owner_id": resource.id,
        }
    ]
    assert direction["resolved_mode"] == "unresolved"
    assert all(
        action["kind"] != "publish_profile"
        for action in direction["allowed_next_actions"]
    )
    assert "no_bookable_owner" in {
        reason["code"] for reason in direction["configuration_reasons"]
    }

    publish_response = client.put(
        f"/api/v1/queues/profiles/{profile.key}",
        json={"show_on_qr_page": True},
        headers=_admin_headers(admin_user),
    )
    assert publish_response.status_code == 409
    assert publish_response.json()["detail"]["reason"] == "profile_publication_blocked"
    assert publish_response.json()["detail"]["code"] == "no_bookable_owner"


def test_hidden_profile_keeps_address_existence_separate_from_public_access(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    resource = QueueResource(
        code="aqs-hidden-ecg",
        queue_tag="ecg",
        display_name="Synthetic ECG resource",
        active=True,
    )
    profile = QueueProfile(
        key="aqs-hidden-ecg-profile",
        title="Hidden ECG",
        title_ru="Скрытая ЭКГ",
        queue_tags=["ecg"],
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    db_session.add_all([resource, profile])
    db_session.flush()
    address = QueueDirectionPublicAddress(
        queue_profile_id=profile.id,
        public_code="abcdefgh2345",
    )
    db_session.add(address)
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    direction = response.json()["directions"][0]
    assert direction["public_availability"] is False
    assert direction["permanent_address_exists"] is True
    assert direction["configuration_state"] == "incomplete"
    assert direction["allowed_next_actions"] == [
        {
            "kind": "publish_profile",
            "entity_type": "queue_profile",
            "entity_id": profile.id,
            "entity_key": profile.key,
        }
    ]
    assert "public_code" not in direction
    assert "abcdefgh2345" not in response.text


def test_hidden_profile_does_not_offer_publish_for_ambiguous_public_target(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    doctor_user = User(
        username="aqs_direction_conflict_doctor",
        email="aqs-direction-conflict@example.test",
        full_name="Synthetic Conflict Doctor",
        hashed_password="not-used",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(doctor_user)
    db_session.flush()
    db_session.add_all(
        [
            Doctor(
                id=1,
                user_id=doctor_user.id,
                specialty="cardiology",
                active=True,
            ),
            QueueResource(
                id=1,
                code="aqs-conflict-lab",
                queue_tag="lab",
                display_name="Synthetic lab resource",
                active=True,
            ),
            QueueProfile(
                key="aqs-published-overview",
                title="Published mixed overview",
                title_ru="Опубликованный общий обзор",
                queue_tags=["lab", "cardiology"],
                is_active=True,
                show_on_qr_page=True,
                display_order=1,
            ),
            QueueProfile(
                key="aqs-hidden-resource-target",
                title="Hidden lab direction",
                title_ru="Скрытая лаборатория",
                queue_tags=["lab"],
                is_active=True,
                show_on_qr_page=False,
                display_order=2,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    direction = next(
        row
        for row in response.json()["directions"]
        if row["profile"]["key"] == "aqs-hidden-resource-target"
    )
    assert direction["resolved_mode"] == "booking"
    assert direction["public_availability"] is False
    assert "publish_target_not_selectable" in {
        reason["code"] for reason in direction["configuration_reasons"]
    }
    assert direction["configuration_state"] == "conflict"
    assert direction["allowed_next_actions"] == [
        {
            "kind": "review_configuration",
            "entity_type": "queue_profile",
            "entity_id": direction["profile"]["id"],
            "entity_key": "aqs-hidden-resource-target",
        }
    ]


def test_hidden_profile_with_inactive_parent_reports_unavailable_not_conflict(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    parent = Department(
        key="aqs-t13-inactive-department",
        name_ru="Неактивное тестовое отделение",
        name_uz="Faol bo'lmagan sinov bo'limi",
        active=False,
    )
    resource = QueueResource(
        code="aqs-t13-inactive-parent-resource",
        queue_tag="lab",
        display_name="Synthetic lab resource",
        active=True,
    )
    profile = QueueProfile(
        key="aqs-t13-inactive-parent-profile",
        title="Hidden lab",
        title_ru="Скрытая лаборатория",
        queue_tags=["lab"],
        department_key=parent.key,
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    db_session.add_all([parent, resource, profile])
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    direction = response.json()["directions"][0]
    assert direction["configuration_state"] == "unavailable"
    assert "publish_target_not_selectable" not in {
        reason["code"] for reason in direction["configuration_reasons"]
    }
    assert direction["allowed_next_actions"] == [
        {
            "kind": "review_configuration",
            "entity_type": "department",
            "entity_id": None,
            "entity_key": parent.key,
        }
    ]


def test_parent_conflict_next_action_targets_queue_profile_editor(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    own_parent = Department(
        key="aqs-t13-conflict-profile-parent",
        name_ru="Собственное тестовое отделение",
        name_uz="O'z test bo'limi",
        active=True,
    )
    explicit_parent = Department(
        key="aqs-t13-conflict-explicit-parent",
        name_ru="Явное тестовое отделение",
        name_uz="Aniq sinov bo'limi",
        active=True,
    )
    profile = QueueProfile(
        key=own_parent.key,
        title="Conflicting parent direction",
        title_ru="Направление с конфликтом родителей",
        queue_tags=["lab"],
        department_key=explicit_parent.key,
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    db_session.add_all([own_parent, explicit_parent, profile])
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200, response.text
    direction = next(
        row
        for row in response.json()["directions"]
        if row["profile"]["key"] == profile.key
    )
    assert direction["configuration_state"] == "conflict"
    assert direction["effective_availability_reasons"] == ["parent_conflict"]
    assert direction["allowed_next_actions"] == [
        {
            "kind": "review_configuration",
            "entity_type": "queue_profile",
            "entity_id": profile.id,
            "entity_key": profile.key,
        }
    ]


def test_hidden_profiles_with_same_doctor_specialty_are_independently_publishable(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    doctor_user = User(
        username="aqs_t13_publish_doctor",
        email="aqs-t13-publish-doctor@example.test",
        full_name="Synthetic Publication Doctor",
        hashed_password="not-used",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(doctor_user)
    db_session.flush()
    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        active=True,
    )
    first_profile = QueueProfile(
        key="aqs-t13-hidden-cardio-a",
        title="Cardiology A",
        title_ru="Кардиология A",
        queue_tags=["cardiology"],
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    second_profile = QueueProfile(
        key="aqs-t13-hidden-cardio-b",
        title="Cardiology B",
        title_ru="Кардиология B",
        queue_tags=["cardiology"],
        is_active=True,
        show_on_qr_page=False,
        display_order=2,
    )
    service = Service(
        name="Synthetic cardiology consultation",
        active=True,
        queue_tag="cardiology",
        doctor_id=None,
        requires_doctor=False,
    )
    db_session.add_all([doctor, first_profile, second_profile, service])
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    by_key = {row["profile"]["key"]: row for row in response.json()["directions"]}
    for key in (first_profile.key, second_profile.key):
        direction = by_key[key]
        assert direction["public_availability"] is False
        assert "publish_target_not_selectable" not in {
            reason["code"] for reason in direction["configuration_reasons"]
        }
        assert direction["allowed_next_actions"] == [
            {
                "kind": "publish_profile",
                "entity_type": "queue_profile",
                "entity_id": direction["profile"]["id"],
                "entity_key": key,
            }
        ]


def test_precreate_matches_existing_queue_by_selected_typed_owner(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    doctor_users = [
        User(
            username=f"aqs_t13_precreate_doctor_{suffix}",
            email=f"aqs-t13-precreate-{suffix}@example.test",
            full_name=f"Synthetic Precreate Doctor {suffix}",
            hashed_password="not-used",
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )
        for suffix in ("a", "b")
    ]
    db_session.add_all(doctor_users)
    db_session.flush()
    doctors = [
        Doctor(
            user_id=doctor_user.id,
            specialty="cardiology",
            active=True,
        )
        for doctor_user in doctor_users
    ]
    profile = QueueProfile(
        key="aqs-t13-precreate-cardiology",
        title="Cardiology precreate",
        title_ru="Кардиология для precreate",
        queue_tags=["cardiology"],
        is_active=True,
        show_on_qr_page=False,
        display_order=1,
    )
    service = Service(
        name="Synthetic doctor-owned cardiology service",
        active=True,
        queue_tag="cardiology",
        doctor_id=None,
        requires_doctor=False,
    )
    db_session.add_all([*doctors, profile, service])
    db_session.flush()
    service.doctor_id = doctors[0].id
    unrelated_queue = DailyQueue(
        day=date(2026, 10, 17),
        queue_tag="cardiology",
        queue_resource_id=None,
        specialist_id=doctors[1].id,
        active=True,
    )
    db_session.add(unrelated_queue)
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    direction = response.json()["directions"][0]
    precreate = direction["precreate_by_tag"][0]
    assert precreate["owner_type"] == "doctor"
    assert precreate["owner_id"] == doctors[0].id
    assert precreate["state"] == "eligible"
    assert precreate["can_precreate"] is True
    assert precreate["existing_daily_queue_ids"] == []
    assert precreate["reason_codes"] == ["single_active_service_owner"]
    assert direction["current_day_queues"] == [
        {
            "daily_queue_id": unrelated_queue.id,
            "queue_tag": "cardiology",
            "owner_type": "doctor",
            "owner_id": doctors[1].id,
        }
    ]

    selected_owner_queue = DailyQueue(
        day=date(2026, 10, 17),
        queue_tag="cardiology",
        queue_resource_id=None,
        specialist_id=doctors[0].id,
        active=True,
    )
    db_session.add(selected_owner_queue)
    db_session.commit()

    response = client.get(
        "/api/v1/queue/admin/directions?day=2026-10-17",
        headers=_admin_headers(admin_user),
    )

    assert response.status_code == 200
    precreate = response.json()["directions"][0]["precreate_by_tag"][0]
    assert precreate["owner_type"] == "doctor"
    assert precreate["owner_id"] == doctors[0].id
    assert precreate["state"] == "already_exists"
    assert precreate["can_precreate"] is True
    assert precreate["existing_daily_queue_ids"] == [selected_owner_queue.id]
    assert precreate["reason_codes"] == [
        "single_active_service_owner",
        "active_queue_exists",
    ]
