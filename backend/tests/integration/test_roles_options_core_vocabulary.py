"""NURSE-V2 N2-2 — /roles/options guarantees the canonical creation vocabulary.

Codex round-3 P2 (PR 3333): the roles catalog is a deployment artifact —
this slice neither seeds nor requires a 'Nurse' row in public.roles — but
the admin UI sources its user-creation options from GET /roles/options.
Without a guarantee, a catalog without a Nurse row made the newly
admitted role uncreatable through the normal workflow (UserModal /
useRoles fall back to lists that omitted it too).

The endpoint now MERGES the canonical user-creation vocabulary into the
catalog-derived list (case-insensitive de-dup: catalog rows keep their
deployment display names). Pins:

- an EMPTY catalog still yields every core selectable (incl. Nurse);
- a catalog Nurse row is not duplicated and its display name wins;
- retired (Manager) and internal-only (Resource) catalog rows stay
  filtered — the merge never resurrects them;
- include_all keeps the leading 'Все роли' filter option.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.role_permission import Role
from app.models.user import User

_OPTIONS_PATH = "/api/v1/roles/options"

_CORE_VALUES = {"admin", "doctor", "registrar", "cashier", "lab", "nurse", "patient"}


def _admin(db_session: Session, username: str) -> User:
    user = db_session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password="x",
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _clear_catalog(db_session: Session) -> None:
    """Drop every catalog row (and any role<->permission links first, so
    the delete cannot trip an FK). This suite runs after the sentinel /
    manager / lab catalog suites in collection order and only asserts on
    its own seeded state."""
    from app.models.role_permission import role_permissions_table

    db_session.execute(role_permissions_table.delete())
    db_session.query(Role).delete()
    db_session.commit()


def _seed_role(
    db_session: Session, name: str, display_name: str, *, level: int = 1
) -> Role:
    role = Role(name=name, display_name=display_name, level=level, is_active=True)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


def _values(payload: dict) -> list[str]:
    return [str(option["value"]) for option in payload["options"]]


@pytest.mark.integration
def test_empty_catalog_still_offers_every_core_selectable(
    client: TestClient, db_session: Session
) -> None:
    """The codex scenario: no Nurse catalog row (no catalog at all)."""
    from tests.conftest import mint_access_token

    _clear_catalog(db_session)
    headers = {
        "Authorization": f"Bearer {mint_access_token(_admin(db_session, 'n2v2_roles_core_admin'))}"
    }

    response = client.get(_OPTIONS_PATH, headers=headers)
    assert response.status_code == 200, response.text
    values = {v.lower() for v in _values(response.json())}
    assert _CORE_VALUES <= values

    by_value = {
        str(option["value"]).lower(): option for option in response.json()["options"]
    }
    assert by_value["nurse"]["value"] == "Nurse"
    assert by_value["nurse"]["label"] == "Медсестра"


@pytest.mark.integration
def test_catalog_nurse_row_is_not_duplicated_and_display_name_wins(
    client: TestClient, db_session: Session
) -> None:
    """A deployment that DID provision a catalog row keeps exactly one
    Nurse option, with its own display name."""
    from tests.conftest import mint_access_token

    _clear_catalog(db_session)
    _seed_role(db_session, "Nurse", "Старшая медсестра", level=5)
    _seed_role(db_session, "Admin", "Главный администратор", level=10)
    headers = {
        "Authorization": f"Bearer {mint_access_token(_admin(db_session, 'n2v2_roles_dup_admin'))}"
    }

    response = client.get(_OPTIONS_PATH, headers=headers)
    assert response.status_code == 200, response.text
    options = response.json()["options"]

    nurse_options = [o for o in options if str(o["value"]).lower() == "nurse"]
    assert len(nurse_options) == 1
    assert nurse_options[0]["label"] == "Старшая медсестра"

    admin_options = [o for o in options if str(o["value"]).lower() == "admin"]
    assert len(admin_options) == 1
    assert admin_options[0]["label"] == "Главный администратор"

    # the rest of the core vocabulary is still guaranteed
    values = {str(o["value"]).lower() for o in options}
    assert _CORE_VALUES <= values


@pytest.mark.integration
def test_retired_and_internal_spellings_stay_filtered(
    client: TestClient, db_session: Session
) -> None:
    """The merge never resurrects Manager/Receptionist (retired) or
    Resource (internal-only sentinel) — those catalog rows stay filtered
    by the pre-existing trust boundary."""
    from tests.conftest import mint_access_token

    _clear_catalog(db_session)
    _seed_role(db_session, "Manager", "Менеджер", level=8)
    _seed_role(db_session, "Resource", "Ресурс", level=1)
    _seed_role(db_session, "Nurse", "Медсестра процедурного кабинета", level=4)
    headers = {
        "Authorization": f"Bearer {mint_access_token(_admin(db_session, 'n2v2_roles_filter_admin'))}"
    }

    response = client.get(_OPTIONS_PATH, headers=headers)
    assert response.status_code == 200, response.text
    values = {str(o["value"]).lower() for o in response.json()["options"]}

    assert "manager" not in values
    assert "resource" not in values
    assert _CORE_VALUES <= values


@pytest.mark.integration
def test_include_all_keeps_leading_filter_option(
    client: TestClient, db_session: Session
) -> None:
    """include_all=True still starts with the 'Все роли' filter entry and
    then carries the guaranteed vocabulary."""
    from tests.conftest import mint_access_token

    _clear_catalog(db_session)
    headers = {
        "Authorization": f"Bearer {mint_access_token(_admin(db_session, 'n2v2_roles_all_admin'))}"
    }

    response = client.get(f"{_OPTIONS_PATH}?include_all=true", headers=headers)
    assert response.status_code == 200, response.text
    options = response.json()["options"]
    assert options[0]["value"] == ""
    assert options[0]["label"] == "Все роли"
    values = {str(o["value"]).lower() for o in options[1:]}
    assert _CORE_VALUES <= values
