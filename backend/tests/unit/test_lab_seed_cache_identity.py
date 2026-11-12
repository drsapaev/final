"""Regression: the lab self-heal seed cache must key on bind identity, not id(bind).

CI 2026-11-11: tests/unit/test_lab_reporting_service.py
::test_real_catalog_codes_l23_l24_l54_resolve_to_exact_templates failed with
``resolution_mode == "unmapped"`` on a freshly seeded test database. Root
cause: the process-level cache records ``id(bind)`` of the previous test
database's connection; once that connection is garbage-collected, CPython may
reuse the id for the new connection, and the cache then reports the
brand-new (empty) database as already seeded — every catalog code resolves
unmapped.

#4011 fixed the runtime cache with a weakref identity (do not revert). Its
own regression test, however, gated its premise on the CPython allocator
actually recycling the dead bind's numeric id within 16 probe allocations
("allocator did not recycle the dead bind id — premise not exercised").
Python guarantees no such reuse, so that test could fail while production
was correct (Codex review on merged #4011: isolated CPython 3.14.4
reproductions — 2 failures in 1,000 runs; ledger #4000 comment 20).

The premise is replaced with a DETERMINISTIC family: the legacy numeric-id
scheme's collision is demonstrated with an INJECTED identity provider in a
test-only replica, and the production weakref contract is pinned without any
allocator-reuse requirement. A bounded repeat-run churn stress stays as
supplemental evidence only — never as a proof of deterministic correctness.
"""

from __future__ import annotations

import gc
import weakref

from app.services.lab_reporting._base import (
    _mark_seed_ensured,
    _seed_cache_fresh,
    reset_lab_seed_cache,
)


class _FakeBind:
    """Smallest weakref-able stand-in for a Session bind (Engine/Connection)."""


class _LegacyNumericSeedCache:
    """Test-only replica of the PRE-#4011 buggy cache: keyed by ``id(bind)``.

    The identity provider is INJECTABLE so the harness can make the deadly
    collision DETERMINISTIC — a live object can never actually share ``id()``
    with another live object, and whether a freed object's id is recycled is
    the allocator's choice. This replica exists to demonstrate WHY numeric
    keying was the bug; it never gates on allocator behavior.
    """

    def __init__(self) -> None:
        self._bind_identity: int | None = None
        self._flags: dict[str, bool] = {}

    def mark_ensured(
        self, bind: object, part: str, *, identity: int | None = None
    ) -> None:
        self._bind_identity = id(bind) if identity is None else identity
        self._flags[part] = True

    def is_fresh(self, bind: object, part: str, *, identity: int | None = None) -> bool:
        observed = id(bind) if identity is None else identity
        if self._bind_identity != observed:
            # A DIFFERENT bind resets every part — the legacy scheme's
            # intent, broken only by numeric-id recycling.
            self._flags = {}
        return not self._flags.get(part, False)


def test_seed_cache_does_not_inherit_across_distinct_binds_even_when_numeric_keying_would_collide():
    """(a)+(b) Deterministic core: two DISTINCT live binds never share seed
    state in the weakref cache — while the same interleaving under an
    injected numeric identity collides by construction, documenting exactly
    the failure mode the weakref fix removed (a fresh database inheriting a
    previous database's already-ensured state)."""
    reset_lab_seed_cache()
    try:
        bind_x = _FakeBind()
        bind_y = _FakeBind()  # a fresh, distinct bind — a different empty database
        assert bind_x is not bind_y

        assert _seed_cache_fresh(bind_x, "bindings") is True
        _mark_seed_ensured(bind_x, "bindings")
        assert _seed_cache_fresh(bind_x, "bindings") is False

        # The weakref cache keys on OBJECT IDENTITY: bind_y never inherits
        # bind_x's already-ensured state.
        assert _seed_cache_fresh(bind_y, "bindings") is True

        # The legacy numeric-id scheme under the SAME interleaving WOULD
        # collide if the two binds shared a numeric identity — exactly what
        # a recycled dead id produced in CI 2026-11-11. The collision is
        # deterministic via the injected provider; no allocator reliance.
        legacy = _LegacyNumericSeedCache()
        legacy.mark_ensured(bind_x, "bindings", identity=0xBAD)
        assert legacy.is_fresh(bind_y, "bindings", identity=0xBAD) is False
    finally:
        reset_lab_seed_cache()


def test_seed_cache_treats_a_dead_binds_replacement_as_stale_without_allocator_preconditions():
    """(b) The original CI scenario, deterministically: a dead bind's
    replacement is stale REGARDLESS of whether CPython recycles the numeric
    id. There is no premise assert — the test cannot fail on a well-behaved
    (or differently-behaved) allocator while production is correct."""
    reset_lab_seed_cache()
    try:
        bind_one = _FakeBind()
        assert _seed_cache_fresh(bind_one, "bindings") is True
        _mark_seed_ensured(bind_one, "bindings")
        assert _seed_cache_fresh(bind_one, "bindings") is False

        dead_bind_id = id(bind_one)
        del bind_one  # refcount-freed immediately: no cycles in this stand-in
        gc.collect()  # force the cyclic collector too — the object is gone

        # Documentary, non-gated: the numeric replica inherits whenever the
        # allocator DID recycle the id — showing the bug firing under the
        # legacy scheme. Whether that happens here is not part of the
        # contract and never fails the test.
        legacy = _LegacyNumericSeedCache()
        legacy.mark_ensured(None, "bindings", identity=dead_bind_id)
        bind_two = _FakeBind()
        if id(bind_two) == dead_bind_id:
            assert legacy.is_fresh(bind_two, "bindings") is False

        # The weakref cache MUST treat the replacement as stale in every
        # case — recycled id or not: the dead bind's weakref is dead, so the
        # new database re-runs its seeders.
        assert _seed_cache_fresh(bind_two, "bindings") is True
        _mark_seed_ensured(bind_two, "bindings")
        assert _seed_cache_fresh(bind_two, "bindings") is False
    finally:
        reset_lab_seed_cache()


def test_seed_cache_identity_survives_repeated_bind_churn_stress():
    """(c) Supplemental repeat-run stress: bounded churn across many bind
    generations keeps the identity semantics (fresh for every new bind,
    sticky while that bind is the current one, no inheritance from a dead
    generation). Supplemental evidence only — never a proof."""
    reset_lab_seed_cache()
    try:
        for _ in range(25):
            churn = _FakeBind()
            # Every fresh generation is fresh...
            assert _seed_cache_fresh(churn, "catalog") is True
            _mark_seed_ensured(churn, "catalog")
            # ...and stays ensured while IT is the current bind.
            assert _seed_cache_fresh(churn, "catalog") is False
            del churn
            gc.collect()
            # The next generation must not inherit this one's state (the
            # next iteration's `is True` re-proves it).
        # One final generation after the churn loop ends.
        final = _FakeBind()
        assert _seed_cache_fresh(final, "catalog") is True
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
