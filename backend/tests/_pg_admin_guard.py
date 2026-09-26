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
"""

from __future__ import annotations

from sqlalchemy.engine import make_url

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _endpoint_list(raw: str) -> list[str]:
    """Split a libpq comma-separated host/hostaddr list, dropping blanks."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def is_local_admin_dsn(dsn: str) -> bool:
    """True iff EVERY endpoint this DSN can reach is machine-local.

    Endpoints considered (libpq failover semantics):
    * the netloc host (SQLAlchemy keeps a comma-separated netloc list
      intact — verified against SQLAlchemy 2.0.x),
    * the ``?host=`` query parameter (comma-separated host/socket list;
      percent-encoded values are decoded by make_url),
    * the ``?hostaddr=`` query parameter (comma-separated IP list used
      verbatim, bypassing DNS).

    Fail-closed: a DSN that mentions no endpoint at all (e.g.
    ``postgresql:///db``) is rejected, because libpq would then fall back
    to environment-provided defaults this guard cannot inspect.
    """
    if not dsn or not dsn.strip():
        return False
    try:
        u = make_url(dsn)
    except Exception:
        return False

    endpoints: list[str] = []
    if u.host:
        endpoints.extend(_endpoint_list(u.host))
    endpoints.extend(_endpoint_list(u.query.get("host") or ""))
    endpoints.extend(_endpoint_list(u.query.get("hostaddr") or ""))
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
