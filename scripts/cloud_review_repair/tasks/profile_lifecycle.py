from pathlib import Path
import sys

TEST = r'''"""Review #3274/#3269: real profile/department routes on isolated fixtures."""
from datetime import date
import uuid

import pytest

from app.models.clinic import Doctor
from app.models.department import Department
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.queue_profile import QueueProfile
from tests.conftest import mint_access_token


def _headers(user):
    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _profile(db, *, key=None, tags=None, visible=True, department=None):
    key = key or "review_" + uuid.uuid4().hex[:10]
    row = QueueProfile(key=key, title="Synthetic review profile", queue_tags=tags or [key],
                       department_key=department, is_active=True, show_on_qr_page=visible)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.parametrize("action", ["toggle", "bulk"])
@pytest.mark.parametrize("public", [False, True])
def test_last_department_deactivation_stays_empty(client, db_session, admin_user, action, public):
    db_session.query(QueueProfile).delete(synchronize_session=False)
    key = "review_" + uuid.uuid4().hex[:10]
    dept = Department(key=key, name_ru="Synthetic department", active=True)
    db_session.add(dept)
    db_session.commit()
    profile = _profile(db_session, key=key, department=key)
    profile_id = profile.id
    headers = _headers(admin_user)
    if action == "toggle":
        response = client.post(f"/api/v1/admin/departments/{dept.id}/toggle", headers=headers)
    else:
        response = client.patch("/api/v1/admin/departments/bulk-activate",
                                json={"ids": [dept.id], "active": False}, headers=headers)
    assert response.status_code == 200, response.text
    path = "/api/v1/queues/profiles" + ("/public" if public else "")
    result = client.get(path, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["specialists" if public else "profiles"] == [], result.text
    assert result.json()["source"] == "database"
    db_session.expire_all()
    assert db_session.get(QueueProfile, profile_id).is_active is False
    all_profiles = client.get("/api/v1/queues/profiles?active_only=false", headers=headers)
    assert key in {p["key"] for p in all_profiles.json()["profiles"]}


def test_all_qr_hidden_is_not_an_unconfigured_table(client, db_session):
    db_session.query(QueueProfile).delete(synchronize_session=False)
    _profile(db_session, visible=False)
    result = client.get("/api/v1/queues/profiles/public")
    assert result.status_code == 200, result.text
    assert result.json()["specialists"] == [], result.text
    assert result.json()["source"] == "database"


def test_truly_unconfigured_profile_table_keeps_bootstrap_fallback(client, db_session, admin_user):
    db_session.query(QueueProfile).delete(synchronize_session=False)
    db_session.commit()
    for suffix, key in [("", "profiles"), ("/public", "specialists")]:
        result = client.get("/api/v1/queues/profiles" + suffix, headers=_headers(admin_user))
        assert result.status_code == 200, result.text
        assert result.json()["source"] == "fallback"
        assert result.json()[key]


@pytest.mark.parametrize("operation", ["preview", "delete"])
def test_profile_key_queue_counts_as_usage_even_outside_explicit_tags(
    client, db_session, admin_user, operation,
):
    key = "review_" + uuid.uuid4().hex[:10]
    explicit_tag = key + "_other"
    profile = _profile(db_session, key=key, tags=[explicit_tag])
    profile_id = profile.id
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add(doctor)
    db_session.flush()
    queue = DailyQueue(day=date.today(), specialist_id=doctor.id, queue_tag=key, active=True)
    db_session.add(queue)
    db_session.flush()
    entry = OnlineQueueEntry(queue_id=queue.id, number=1, status="waiting", source="online")
    db_session.add(entry)
    db_session.commit()
    queue_id, entry_id = queue.id, entry.id
    endpoint = f"/api/v1/queues/profiles/{key}"
    if operation == "preview":
        response = client.get(endpoint + "/impact-preview", headers=_headers(admin_user))
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["can_hard_delete"] is False, data
        assert data["links"]["daily_queues"] == 1
        assert data["links"]["entries_waiting"] == 1
    else:
        response = client.delete(endpoint, headers=_headers(admin_user))
        assert response.status_code == 409, response.text
    db_session.expire_all()
    assert db_session.get(QueueProfile, profile_id).queue_tags == [explicit_tag]
    assert db_session.get(DailyQueue, queue_id) is not None
    assert db_session.get(OnlineQueueEntry, entry_id).status == "waiting"


def test_unused_profile_with_distinct_key_and_tags_can_still_be_deleted(client, db_session, admin_user):
    key = "review_" + uuid.uuid4().hex[:10]
    profile = _profile(db_session, key=key, tags=[key + "_other"])
    profile_id = profile.id
    response = client.delete(f"/api/v1/queues/profiles/{key}", headers=_headers(admin_user))
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(QueueProfile, profile_id) is None
'''

if sys.argv[1] == 'tests':
    p = Path('backend/tests/test_review_profile_lifecycle.py')
    assert not p.exists()
    p.write_text(TEST)
elif sys.argv[1] == 'fix':
    p = Path('backend/app/api/v1/endpoints/registrar_integration/_queue_profiles.py')
    s = p.read_text()
    for anchor in [
        '        # Если таблица не существует или пуста - возвращаем fallback\n        if not profiles:',
        '        if not profiles:\n            # Fallback: возвращаем все из INITIAL_QUEUE_PROFILES (кроме general и ecg)',
    ]:
        assert s.count(anchor) == 1
        replacement = anchor.replace('if not profiles:', 'if not profiles and db.query(QueueProfile.id).first() is None:')
        s = s.replace(anchor, replacement)
    old = '    tags = [t for t in (profile.queue_tags or []) if t]'
    assert s.count(old) == 1
    s = s.replace(old, '''    # QR entry points route on the profile key even when an explicit tag
    # list omits it. Count that real usage without rewriting the operator's
    # configured tags or merging queues (reviews #3269 and #3274).
    tags = list(dict.fromkeys(
        t for t in [*(profile.queue_tags or []), profile.key] if t
    ))''')
    p.write_text(s)
else:
    raise ValueError('Unknown phase')
