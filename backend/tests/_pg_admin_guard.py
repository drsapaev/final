"""Local-only admission check for scratch-database admin DSNs (PR #3468).

The scratch-provisioning fixtures CREATE and DROP a disposable PostgreSQL
database. That must only ever happen on a machine-local server, never on a
remote/production one (a Supabase-style DATABASE_URL points there).

Audit P1 (PR #3468): libpq treats the connection ``host`` — both the netloc
host and the ``?host=`` query parameter — as a comma-separated FAILOVER
list, and ``?hostaddr=`` bypasses DNS entirely. A guard that inspects only
the first element (or the string prefix) admits DSNs such as

    postgresql:///db?host=/missing/socket,db.internal

where the local socket is merely the FIRST failover target; if it is
unavailable libpq silently falls through to the remote endpoint, and the
fixture would provision its scratch database there. The only safe rule is
therefore: EVERY possible endpoint of the DSN must be local.

Local endpoints: the loopback literals ``localhost`` / ``127.0.0.1`` /
``::1`` and unix-socket directories (libpq semantics: a host element
starting with ``/``). Everything else — remote hostnames, network IPs,
cloud DB endpoints, relative ``./`` paths (libpq treats those as DNS
hostnames, not sockets) — fails closed.

Unification with the RQ-29 harness guard (PR #3474 follow-up): that
harness carried its own stricter private guard, and the shared validator
missed exactly the vectors below. They are now part of THIS shared
contract, so every consumer gets the RQ29-grade rule set:

* **Case-insensitive conninfo keys** — libpq matches parameter names
  case-insensitively while SQLAlchemy preserves query-key case, so
  ``?HOSTADDR=10.9.8.7`` was dialled by libpq but not read by the old
  validator: a remote dial through an uppercase spelling. Query keys are
  now normalized case-insensitively.
* **Repeated keys** — SQLAlchemy folds repeated query keys into
  sequences; the old validator crashed (AttributeError) on them instead
  of returning a verdict. Every value of every key is now judged; a
  remote tail in ANY duplicate poisons the whole DSN.
* **``?service=`` rejection** — a service file is resolved at connect
  time and may inject any unspelled parameter (``hostaddr`` included)
  from a file this guard cannot inspect; fail closed.
* **Environment re-dial** — with ``PGHOSTADDR`` or ``PGSERVICE`` set in
  the environment, libpq re-dials EVERY candidate through that
  address/service regardless of its spelling; fail closed.
* **postgresql-only drivername** — a non-postgresql URL is never a PG
  admin candidate, even when it carries a syntactically local ``?host=``.

Deliberately preserved from the audited PR #3468 contract: a DSN that
mentions no endpoint at all (e.g. ``postgresql:///db``) is still rejected,
because libpq would fall back to environment-provided defaults this guard
cannot inspect; and a loopback ``?hostaddr=`` element is still admitted
element-wise (dialling 127.0.0.1 is local by construction).
"""

from __future__ import annotations

import os

from sqlalchemy.engine import make_url

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _endpoint_list(raw: str) -> list[str]:
    """Split a libpq comma-separated host/hostaddr list, dropping blanks."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _env_can_re_dial() -> bool:
    """True when the environment can re-dial a DSN's address.

    libpq fills omitted connection fields from the environment; with both
    ``host`` and ``hostaddr`` present libpq dials ``hostaddr``, and a
    service name may inject any unspelled parameter. Any non-empty value
    of either rejects (fail-closed).
    """
    return bool(os.getenv("PGHOSTADDR", "").strip()) or bool(
        os.getenv("PGSERVICE", "").strip()
    )


def _query_values(u: make_url) -> dict[str, list[str]]:
    """Case-insensitive, duplication-safe view of the DSN query string.

    libpq matches conninfo parameter names case-insensitively and accepts
    repeated keys; SQLAlchemy preserves query-key case and folds repeated
    keys into sequences. The guard must normalize both — otherwise a case
    or duplication spelling becomes a bypass.
    """
    qvals: dict[str, list[str]] = {}
    for k, v in (u.query or {}).items():
        vals = v if isinstance(v, (list, tuple)) else [v]
        qvals.setdefault(str(k).lower(), []).extend(str(x) for x in vals)
    return qvals


def is_local_admin_dsn(dsn: str) -> bool:
    """True iff EVERY endpoint this DSN can reach is machine-local.

    Endpoints considered (libpq failover semantics):
    * the netloc host (SQLAlchemy keeps a comma-separated netloc list
      intact — verified against SQLAlchemy 2.0.x),
    * every ``?host=`` query value under ANY case spelling (comma-separated
      host/socket list; percent-encoded values are decoded by make_url),
    * every ``?hostaddr=`` query value under ANY case spelling (comma-
      separated IP list used verbatim, bypassing DNS).

    Fail-closed rules beyond the endpoint check: a DSN that mentions no
    endpoint at all (e.g. ``postgresql:///db``) is rejected, because libpq
    would then fall back to environment-provided defaults this guard
    cannot inspect; a ``?service=`` reference is rejected (a service file
    may inject any unspelled parameter); the whole DSN is rejected while
    ``PGHOSTADDR``/``PGSERVICE`` can re-dial it from the environment; and
    a non-postgresql URL is never a PG admin candidate.
    """
    if not dsn or not dsn.strip():
        return False
    try:
        u = make_url(dsn)
    except Exception:
        return False
    if not u.drivername.startswith("postgresql"):
        return False  # a sqlite/other URL is never a PG admin candidate

    qvals = _query_values(u)
    if qvals.get("service"):
        return False  # service contract unresolved — fail-closed
    if _env_can_re_dial():
        return False  # the environment can re-dial the address — fail-closed

    endpoints: list[str] = []
    if u.host:
        endpoints.extend(_endpoint_list(u.host))
    for value in qvals.get("host") or []:
        endpoints.extend(_endpoint_list(value))
    for value in qvals.get("hostaddr") or []:
        endpoints.extend(_endpoint_list(value))
    if not endpoints:
        return False

    for endpoint in endpoints:
        if endpoint.startswith("/"):
            # Unix-socket directory (libpq: leading slash) — local by
            # construction; the socket file lives on this machine.
            continue
        if endpoint.lower() in LOCAL_HOSTS:
            continue
        return False
    return True
