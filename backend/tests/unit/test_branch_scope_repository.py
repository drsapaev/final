from __future__ import annotations

import pytest

from app.repositories.branch_scope_repository import (
    BranchScopeRequiredError,
    BranchScopeViolationError,
    ensure_entity_within_branch_scope,
    require_branch_scope_id,
    resolve_scoped_branch_id,
)


def test_require_branch_scope_id_validates_presence_and_range() -> None:
    assert require_branch_scope_id(7, source="test") == 7

    with pytest.raises(BranchScopeRequiredError):
        require_branch_scope_id(None, source="test")

    with pytest.raises(BranchScopeRequiredError):
        require_branch_scope_id(0, source="test")


def test_resolve_scoped_branch_id_prefers_explicit_and_detects_mismatch() -> None:
    assert resolve_scoped_branch_id(request_branch_id=11, explicit_branch_id=None) == 11
    assert resolve_scoped_branch_id(request_branch_id=11, explicit_branch_id=11) == 11
    assert resolve_scoped_branch_id(request_branch_id=None, explicit_branch_id=5) == 5

    with pytest.raises(BranchScopeViolationError):
        resolve_scoped_branch_id(request_branch_id=11, explicit_branch_id=7)


def test_resolve_scoped_branch_id_requires_scope_when_flag_enabled() -> None:
    with pytest.raises(BranchScopeRequiredError):
        resolve_scoped_branch_id(request_branch_id=None, explicit_branch_id=None, require_scope=True)

    assert (
        resolve_scoped_branch_id(request_branch_id=9, explicit_branch_id=None, require_scope=True)
        == 9
    )


def test_ensure_entity_within_branch_scope_checks_membership() -> None:
    ensure_entity_within_branch_scope(
        entity_branch_id=3,
        scoped_branch_id=3,
        entity_name="Equipment",
        entity_id=100,
    )

    with pytest.raises(BranchScopeViolationError):
        ensure_entity_within_branch_scope(
            entity_branch_id=4,
            scoped_branch_id=3,
            entity_name="Equipment",
            entity_id=100,
        )
