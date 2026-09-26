"""PR #3468 audit regression: local-only admin DSN guard + scratch teardown.

P1: libpq treats the connection ``host`` (netloc or ``?host=`` query
parameter) as a comma-separated FAILOVER list and ``?hostaddr=`` bypasses
DNS. A local-only guard that inspects only the first element (or the string
prefix) admits DSNs such as ``?host=/missing-local-socket,db.internal`` —
the local socket is merely the first failover target, and libpq falls
through to the remote endpoint, so a fixture could CREATE/DROP its scratch
database on a server it must never touch.

These tests exercise the REAL ``_candidate_admin_urls`` (and, for the
two-source fixtures, ``_preprovisioned_local_url``) of every fixture module
changed by PR #3468 — wiring level, all 16 files — plus the shared
validator matrix (``tests._pg_admin_guard``). No PostgreSQL server is
required: this is pure DSN-admission logic.

Follow-up sibling PR: the two lock-proof fixtures that stayed on main
(``test_schedule_create_lock_pg``, ``test_portal_department_booking_lock_pg``)
carried the same P1 class — their DATABASE_URL branch admitted ANY ``?host=``
value (no prefix check, no list parsing) and any loopback netloc with a
non-local ``?hostaddr=``. They are wired into the same matrix below.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
for _p in (BACKEND_DIR, BACKEND_DIR / "tests" / "integration",
           BACKEND_DIR / "tests" / "characterization"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# The 11 socket-aware fixture modules changed by PR #3468 (raw socket-DSN
# admission path) and the 5 whose DATABASE_URL candidate used to be appended
# without any local-only check at all (docstring claimed "LOCAL servers
# only" while the code appended unconditionally).
SOCKET_AWARE_MODULES = [
    "test_admin_department_create_atomicity",
    "test_doctor_panel_queue_tag_visibility",
    "test_effective_queue_settings_report",
    "test_qr_family_phone_identity",
    "test_qr_join_owner_eligibility",
    "test_qr_selection_join_visibility",
    "test_qr_token_path_owner_eligibility",
    "test_queue_profile_lifecycle",
    "test_registrar_services_requires_doctor",
    "test_rq09b_specialist_type_resolution",
    "test_rq14a_numbering_integrity_pg",
]
UNGUARDED_MODULES = [
    "test_rq13b_daily_queue_snapshot_pg",
    "test_rq16b_direction_entry_methods",
    "test_rq16c_direction_public_address_pg",
    "test_rq16d_public_direction_runtime",
]
# Sibling follow-up PR: the two lock-proof fixtures on main with the same
# P1 class (any-``?host=`` admission + hostaddr bypass on loopback netloc).
SIBLING_MODULES = [
    "test_schedule_create_lock_pg",
    "test_portal_department_booking_lock_pg",
]
ALL_FIXTURE_MODULES = (
    SOCKET_AWARE_MODULES + UNGUARDED_MODULES + SIBLING_MODULES + [
        "test_rq14_qr_desk_owner_consistency_pg",  # characterization, unguarded
    ]
)
TWO_SOURCE_MODULES = [  # fallback path via _preprovisioned_local_url
    "test_doctor_panel_queue_tag_visibility",
    "test_qr_selection_join_visibility",
]

# The exact audit vector: local socket first, remote failover tail.
AUDIT_MULTI_HOST = "postgresql:///clinicdb?host=/missing-local-socket,db.internal"
REMOTE_DSN = "postgresql://probe:s3cret@db.internal:5432/postgres"
HOSTADDR_BYPASS = "postgresql://probe:s3cret@localhost:5432/postgres?hostaddr=10.9.8.7"
PURE_SOCKET = "postgresql:///clinicdb?host=/var/run/scratch-sockets"
LOOPBACK_TCP = "postgresql://probe:s3cret@localhost:5432/postgres"


def _isolate_dsn_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every env var that could inject extra admin candidates."""
    for name in list(os.environ):
        if name == "LOCAL_PG_SUPERUSER_PASSWORD" or name.endswith("_PG_ADMIN_URL"):
            monkeypatch.delenv(name, raising=False)


def _load(modname: str):
    return importlib.import_module(modname)


@pytest.mark.parametrize("modname", ALL_FIXTURE_MODULES)
def test_multi_host_socket_dsn_is_never_accepted(monkeypatch, modname):
    """P1 audit vector: a remote failover tail must poison the whole DSN."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", AUDIT_MULTI_HOST)
    urls = mod._candidate_admin_urls()
    assert urls == [], (
        f"{modname} accepted a multi-host DSN whose failover list reaches "
        f"db.internal: {urls}"
    )


@pytest.mark.parametrize("modname", ALL_FIXTURE_MODULES)
def test_remote_dsn_is_never_accepted(monkeypatch, modname):
    """Plain remote DATABASE_URL must never reach scratch provisioning."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", REMOTE_DSN)
    urls = mod._candidate_admin_urls()
    assert urls == [], f"{modname} accepted a remote admin DSN: {urls}"


@pytest.mark.parametrize("modname", ALL_FIXTURE_MODULES)
def test_hostaddr_bypass_is_never_accepted(monkeypatch, modname):
    """?hostaddr= overrides DNS — a non-local hostaddr is remote, period."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", HOSTADDR_BYPASS)
    urls = mod._candidate_admin_urls()
    assert urls == [], (
        f"{modname} accepted a DSN whose hostaddr points off-machine: {urls}"
    )


@pytest.mark.parametrize("modname", ALL_FIXTURE_MODULES)
def test_loopback_tcp_dsn_still_accepted(monkeypatch, modname):
    """Positive pin: loopback TCP stays usable for scratch provisioning."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", LOOPBACK_TCP)
    urls = mod._candidate_admin_urls()
    assert any(
        u.startswith("postgresql://probe:s3cret@localhost:5432/postgres")
        for u in urls
    ), f"{modname} lost the loopback TCP candidate: {urls}"


@pytest.mark.parametrize("modname", SOCKET_AWARE_MODULES + SIBLING_MODULES)
def test_pure_local_socket_dsn_still_accepted(monkeypatch, modname):
    """Positive pin: the userspace pgserver socket DSN stays usable."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", PURE_SOCKET)
    urls = mod._candidate_admin_urls()
    assert PURE_SOCKET in urls, (
        f"{modname} lost the local unix-socket candidate: {urls}"
    )


@pytest.mark.parametrize("modname", TWO_SOURCE_MODULES)
def test_preprovisioned_fallback_rejects_multi_host(monkeypatch, modname):
    """P1 family: the source-2 fallback must apply the same strict rule."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", AUDIT_MULTI_HOST)
    assert mod._preprovisioned_local_url() is None, (
        f"{modname}._preprovisioned_local_url accepted a multi-host DSN"
    )


@pytest.mark.parametrize("modname", TWO_SOURCE_MODULES)
def test_preprovisioned_fallback_keeps_password(monkeypatch, modname):
    """Sibling of the 648a3a6 fix: str(URL) masks the password as ***."""
    mod = _load(modname)
    _isolate_dsn_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", LOOPBACK_TCP)
    url = mod._preprovisioned_local_url()
    assert url is not None
    assert "s3cret" in url, (
        f"{modname}._preprovisioned_local_url masked the password: {url!r}"
    )


def test_validator_matrix() -> None:
    """Exhaustive accept/reject matrix for the shared validator."""
    validator = pytest.importorskip("tests._pg_admin_guard")
    is_local = validator.is_local_admin_dsn

    accepted = [
        "postgresql://u:p@localhost:5432/postgres",
        "postgresql://u:p@127.0.0.1:5432/postgres",
        "postgresql://u:p@[::1]:5432/postgres",
        "postgresql://u:p@LOCALHOST:5432/postgres",
        "postgresql:///db?host=/var/run/scratch-sockets",
        "postgresql:///db?host=/sock1,/sock2",
        "postgresql:///db?host=/sock1,localhost",
        "postgresql:///db?host=localhost,127.0.0.1,::1",
        "postgresql:///db?host=%2Fsock1%2C%2Fsock2",
        "postgresql:///db?host=/var/run/scratch-sockets&hostaddr=",
    ]
    rejected = [
        # The audit vector itself.
        "postgresql:///db?host=/missing-local-socket,db.internal",
        "postgresql:///db?host=/missing-local-socket,10.1.2.3",
        # Mixed local-first lists still carry a remote tail.
        "postgresql:///db?host=localhost,db.internal",
        # Percent-encoded remote tail.
        "postgresql:///db?host=%2Fsock%2Cdb.internal",
        # Whitespace around elements must not hide the remote endpoint.
        "postgresql:///db?host=/sock1 , db.internal",
        # hostaddr overrides DNS entirely.
        "postgresql://u:p@localhost:5432/db?hostaddr=10.9.8.7",
        "postgresql://u:p@localhost:5432/db?hostaddr=10.9.8.7,::1",
        # Plain remote forms.
        "postgresql://u:p@db.internal:5432/db",
        "postgresql://u:p@10.1.2.3:5432/db",
        "postgresql://u:p@db.internal:5432/db?hostaddr=",
        # Netloc failover list with a remote element.
        "postgresql://u:p@localhost,db.internal:5432/db",
        # Relative socket paths: libpq treats "./x" as a DNS hostname.
        "postgresql:///db?host=./relative-socket",
        # No endpoint at all — fail closed (libpq would use env defaults).
        "postgresql:///db",
        "postgresql://",
        "",
        # Garbage fails closed.
        "not-a-dsn at all",
    ]
    for dsn in accepted:
        assert is_local(dsn), f"must ACCEPT local DSN: {dsn!r}"
    for dsn in rejected:
        assert not is_local(dsn), f"must REJECT non-local DSN: {dsn!r}"
