"""Regression: the lab self-heal seed cache must key on bind identity, not id(bind).

CI 2026-11-11: tests/unit/test_lab_reporting_service.py
::test_real_catalog_codes_l23_l24_l54_resolve_to_exact_templates failed with
``resolution_mode == "unmapped"`` on a freshly seeded test database. Root
cause: the process-level cache records ``id(bind)`` of the previous test
database's connection; once that connection is garbage-collected, CPython may
reuse the id for the new connection, and the cache then reports the
brand-new (empty) database as already seeded — every catalog code resolves
unmapped.
"""

from __future__ import annotations

import weakref

from app.services.lab_reporting._base import (
    _mark_seed_ensured,
    _seed_cache_fresh,
    reset_lab_seed_cache,
)


class _FakeBind:
    """Smallest weakref-able stand-in for a Session bind (Engine/Connection)."""


def test_seed_cache_treats_a_new_bind_as_stale_even_when_the_dead_bind_id_was_reused():
    reset_lab_seed_cache()
    try:
        bind_one = _FakeBind()
        assert _seed_cache_fresh(bind_one, "bindings") is True
        _mark_seed_ensured(bind_one, "bindings")
        assert _seed_cache_fresh(bind_one, "bindings") is False

        dead_bind_id = id(bind_one)
        del bind_one  # refcount-freed immediately: no cycles in this stand-in

        # CPython reuses the freed slot for the next same-size allocation. The
        # probe loop only pins the premise down explicitly so the test can
        # never silently degrade into a vacuous pass.
        bind_two = None
        for _ in range(16):
            candidate = _FakeBind()
            if id(candidate) == dead_bind_id:
                bind_two = candidate
                break
            del candidate
        assert (
            bind_two is not None
        ), "allocator did not recycle the dead bind id — premise not exercised"

        # The new bind owns a different (empty) database. The cache must treat
        # it as stale so the seeders run, instead of inheriting the dead
        # bind's already-ensured state through the recycled id.
        assert _seed_cache_fresh(bind_two, "bindings") is True
    finally:
        reset_lab_seed_cache()


def test_seed_cache_keeps_hitting_for_the_same_live_bind():
    """Guard: identity-based caching must keep the once-per-process win for a
    long-lived production engine (catalog/templates/bindings per part)."""
    reset_lab_seed_cache()
    try:
        bind = _FakeBind()
        assert _seed_cache_fresh(bind, "catalog") is True
        _mark_seed_ensured(bind, "catalog")
        assert _seed_cache_fresh(bind, "catalog") is False

        assert _seed_cache_fresh(bind, "bindings") is True
        _mark_seed_ensured(bind, "bindings")
        assert _seed_cache_fresh(bind, "bindings") is False
    finally:
        reset_lab_seed_cache()


def test_seed_cache_rearms_after_reset():
    """Guard: reset_lab_seed_cache re-arms every part for the same bind
    (self-heal paths in list_templates/get_template rely on this)."""
    reset_lab_seed_cache()
    try:
        bind = _FakeBind()
        _mark_seed_ensured(bind, "templates")
        assert _seed_cache_fresh(bind, "templates") is False
        reset_lab_seed_cache()
        assert _seed_cache_fresh(bind, "templates") is True
    finally:
        reset_lab_seed_cache()


def test_seed_cache_does_not_hold_the_bind_alive():
    """Guard: the cache may keep only a weakref to the bind — seeding state
    must never pin the previous engine (and its pooled connections) in
    memory."""
    reset_lab_seed_cache()
    try:
        bind = _FakeBind()
        _mark_seed_ensured(bind, "catalog")
        probe = weakref.ref(bind)
        del bind
        assert probe() is None
    finally:
        reset_lab_seed_cache()
