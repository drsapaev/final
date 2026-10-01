"""Queue-profile read behavior when the configured catalog is empty or unavailable."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.registrar_integration._queue_profiles import (
    get_queue_profiles,
    get_queue_profiles_public,
)


class EmptyProfileQuery:
    def filter(self, *_conditions):
        return self

    def order_by(self, *_expressions):
        return self

    def all(self) -> list[object]:
        return []


class EmptyProfileSession:
    def query(self, *_entities) -> EmptyProfileQuery:
        return EmptyProfileQuery()


class FailingProfileSession:
    def query(self, *_entities):
        raise RuntimeError("synthetic profile database failure")


def _read_admin_profiles(db):
    return get_queue_profiles(active_only=True, db=db, current_user=None)


def _read_public_profiles(db):
    return get_queue_profiles_public(db=db)


@pytest.mark.parametrize(
    ("reader", "list_field"),
    [
        (_read_admin_profiles, "profiles"),
        (_read_public_profiles, "specialists"),
    ],
)
def test_empty_profile_catalog_returns_a_genuine_empty_list(reader, list_field):
    result = reader(EmptyProfileSession())

    assert result["success"] is True
    assert result["source"] == "database"
    assert result[list_field] == []


@pytest.mark.parametrize("reader", [_read_admin_profiles, _read_public_profiles])
def test_profile_read_failure_raises_safe_server_error(reader):
    with pytest.raises(HTTPException) as error:
        reader(FailingProfileSession())

    assert error.value.status_code == 500
    assert error.value.detail == "Internal server error"
    assert "synthetic profile database failure" not in str(error.value.detail)
