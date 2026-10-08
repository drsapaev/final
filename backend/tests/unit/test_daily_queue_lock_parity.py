"""Lock-parity pins for the doctor day-queue creation advisory scope.

Follow-up to the #3511 review (owner verdict round + merge-gate
round): the canonical
``queue_service.get_or_create_daily_queue`` serializes its
check-then-insert on ``pg_advisory_xact_lock('daily_queue:{day}:{doctor}')``,
while FIVE legacy creation paths ran the same query-then-insert outside
that scope:

- GraphQL ``joinQueue`` (untagged) took a DIFFERENT key spelling
  (``daily_queue:{doctor}:{day}:`` — doctor-first with a trailing colon),
  so it serialized only against itself, never against the canonical
  writer (registrar cart, morning assignment);
- ``crud/online_queue.get_or_create_daily_queue`` (the queue_batch
  path), ``visit_confirmation_repository.get_or_create_daily_queue``,
  ``queue_limits_repository.get_or_create_daily_queue`` and
  ``QueueApiService.get_or_create_daily_queue`` (the deprecated but
  mounted ``POST /queue/open`` for Admin/Registrar queue management)
  took no lock at all.

Two concurrent writers could both observe "no queue" and insert — the
``uq_daily_queues_active_doctor_day_tag`` partial unique then failed the
loser with an unhandled IntegrityError instead of a clean reuse.

The fix centralizes the key in
``queue_resource_routing.daily_queue_creation_lock_key`` and routes every
path through ``lock_daily_queue_creation``. These pins hold:

- the key spelling (byte-identical to the historical canonical
  interpolation — the lock IDENTITY must not drift, or the parity is
  silently lost again);
- the helper's PostgreSQL-only parity (execute on PG, no-op on SQLite
  and on bind-less test doubles);
- the call-site wiring: all five legacy paths call the helper, and the
  legacy inline spelling is gone (scanner pins — the same family the
  repo uses for source-level contracts).

The behavioral PostgreSQL proof (real concurrent writers, one queue row)
lives in ``tests/integration/test_daily_queue_lock_parity_pg.py``.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.crud.queue_resource_routing import (
    daily_queue_creation_lock_key,
    lock_daily_queue_creation,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _fake_session(dialect_name: str | None):
    """A duck-typed session recording every ``execute`` call."""

    executed: list[tuple[object, dict]] = []

    if dialect_name is None:
        bind = None
    else:
        bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))

    session = SimpleNamespace(bind=bind, executed=executed)

    def _execute(statement, params=None):
        executed.append((statement, dict(params or {})))

    session.execute = _execute
    return session


# ── Key spelling: the lock IDENTITY ────────────────────────────────────────


def test_lock_key_spelling_is_canonical() -> None:
    """``daily_queue:{iso-day}:{doctor}`` — day first, doctor last."""

    key = daily_queue_creation_lock_key(date(2026, 9, 29), 123)
    assert key == "daily_queue:2026-09-29:123"


def test_lock_key_is_byte_identical_to_historical_canonical_interpolation() -> None:
    """The canonical service's historical f-string and the SSOT helper
    produce the SAME string — otherwise every deployment upgrade would
    silently split the serialization scope in two."""

    day = date(2026, 9, 29)
    specialist_id = 456
    historical = f"daily_queue:{day}:{specialist_id}"
    assert daily_queue_creation_lock_key(day, specialist_id) == historical


def test_lock_key_rejects_nothing_but_stays_stable_across_days() -> None:
    """Distinct (day, doctor) pairs map to distinct scopes; the same pair
    is stable (pure function, no hidden state)."""

    assert daily_queue_creation_lock_key(date(2026, 9, 29), 1) != (
        daily_queue_creation_lock_key(date(2026, 9, 30), 1)
    )
    assert daily_queue_creation_lock_key(date(2026, 9, 29), 1) != (
        daily_queue_creation_lock_key(date(2026, 9, 29), 2)
    )
    assert daily_queue_creation_lock_key(date(2026, 9, 29), 1) == (
        daily_queue_creation_lock_key(date(2026, 9, 29), 1)
    )


# ── Helper parity: PostgreSQL executes, everything else no-ops ─────────────


def test_helper_executes_pg_advisory_xact_lock_on_postgresql() -> None:
    session = _fake_session("postgresql")

    lock_daily_queue_creation(session, date(2026, 9, 29), 123)

    assert len(session.executed) == 1
    statement, params = session.executed[0]
    assert "pg_advisory_xact_lock" in str(statement)
    assert "hashtext" in str(statement)
    assert params == {"k": "daily_queue:2026-09-29:123"}


def test_helper_is_noop_on_sqlite() -> None:
    session = _fake_session("sqlite")

    lock_daily_queue_creation(session, date(2026, 9, 29), 123)

    assert session.executed == []


def test_helper_is_noop_without_bind() -> None:
    """Unit test doubles may carry no bind at all — never raise."""

    session = _fake_session(None)

    lock_daily_queue_creation(session, date(2026, 9, 29), 123)

    assert session.executed == []


# ── Scanner pins: the wiring cannot silently drift ─────────────────────────


def test_canonical_service_uses_the_shared_helper() -> None:
    """queue_service routes through the SSOT helper — the historical
    inline f-string spelling must not reappear."""

    source = (
        BACKEND_ROOT / "app" / "services" / "queue_svc" / "_operations.py"
    ).read_text(encoding="utf-8")
    assert re.search(
        r"lock_daily_queue_creation\(\s*db,\s*day,\s*actual_specialist_id,"
        r"\s*queue_tag=queue_tag\s*\)",
        source,
    )
    # the historical inline spelling is gone
    assert 'f"daily_queue:{day}:{actual_specialist_id}"' not in source


def test_gql_untagged_join_uses_the_shared_helper() -> None:
    """The GraphQL untagged branch calls the helper; the legacy mismatched
    inline key (doctor-before-day + trailing colon) is gone — that
    spelling serialized the GQL path only against itself."""

    source = (BACKEND_ROOT / "app" / "graphql" / "mutations.py").read_text(
        encoding="utf-8"
    )
    assert "lock_daily_queue_creation(db, today, input.doctor_id)" in source
    assert "daily_queue:{input.doctor_id}" not in source


def test_legacy_creation_paths_call_the_helper_before_their_lookup() -> None:
    """crud/online_queue (queue_batch), the visit-confirmation
    repository, the queue-limits repository and the queue-api legacy
    service (the deprecated but mounted POST /queue/open) acquire the
    canonical scope BEFORE their existing-queue lookup — an advisory
    taken after the lookup would not close the check-then-insert
    window."""

    sites = {
        "app/crud/online_queue.py": (
            "queue_resource_routing.lock_daily_queue_creation(",
            "query_filters = [",
        ),
        "app/repositories/visit_confirmation_repository.py": (
            "lock_daily_queue_creation(",
            "query = self.db.query(DailyQueue).filter(",
        ),
        "app/repositories/queue_limits_repository.py": (
            "lock_daily_queue_creation(self.db, day, specialist_id)",
            "queue = self.get_daily_queue(day=day, specialist_id=specialist_id)",
        ),
        "app/services/queue_api_service.py": (
            "queue_resource_routing.lock_daily_queue_creation(",
            "daily_queue = self.repository.get_daily_queue(",
        ),
    }
    for relpath, (lock_call, lookup_marker) in sites.items():
        source = (BACKEND_ROOT / relpath).read_text(encoding="utf-8")
        assert lock_call in source, f"{relpath}: helper call missing"
        lock_pos = source.index(lock_call)
        lookup_pos = source.index(lookup_marker)
        assert (
            lock_pos < lookup_pos
        ), f"{relpath}: the advisory must precede the existing-queue lookup"


def test_no_second_advisory_key_spelling_for_doctor_day_queues() -> None:
    """Exactly ONE key spelling family for the doctor day-queue creation
    scope across the backend: the tag-scope locks
    (``daily_queue:tag:...``) are a different, legitimate family; the
    GQL legacy ``daily_queue:{doctor}:{day}:`` variant must not
    reappear anywhere."""

    app_root = BACKEND_ROOT / "app"
    offenders: list[str] = []
    for path in sorted(app_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        # legacy GQL spelling: doctor id interpolated BEFORE the day,
        # trailing colon after the day
        if re.search(r"daily_queue:\{[^}]*doctor[^}]*\}", text):
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []
