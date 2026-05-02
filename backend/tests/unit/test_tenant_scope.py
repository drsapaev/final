from __future__ import annotations

import pytest

from app.core.tenant_scope import (
    TenantScope,
    parse_branch_id,
    require_branch_scope,
    resolve_tenant_scope,
)


def test_parse_branch_id_returns_none_for_missing_or_blank_values() -> None:
    assert parse_branch_id(None) is None
    assert parse_branch_id("") is None
    assert parse_branch_id("   ") is None


def test_parse_branch_id_raises_for_non_numeric_values() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        parse_branch_id("abc")


def test_resolve_tenant_scope_prefers_header_then_query_then_user() -> None:
    assert resolve_tenant_scope("11", 7, 3) == TenantScope(branch_id=11, source="header")
    assert resolve_tenant_scope(None, 7, 3) == TenantScope(branch_id=7, source="query")
    assert resolve_tenant_scope(None, None, 3) == TenantScope(branch_id=3, source="user")
    assert resolve_tenant_scope(None, None, None) == TenantScope(branch_id=None, source="unset")


def test_resolve_tenant_scope_validates_positive_values() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        resolve_tenant_scope(None, 0, None)

    with pytest.raises(ValueError, match="positive integer"):
        resolve_tenant_scope(None, None, -5)


def test_require_branch_scope_raises_if_branch_missing() -> None:
    with pytest.raises(ValueError, match="required"):
        require_branch_scope(TenantScope(branch_id=None, source="unset"))

    assert require_branch_scope(TenantScope(branch_id=9, source="query")) == 9
