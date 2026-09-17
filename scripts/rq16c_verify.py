"""Self-contained RQ-16.c verification runner (lessons 48/49).

One process provisions a FRESH disposable PostgreSQL (pgserver, new
pgdata dir per run — lesson 49), proxies its unix socket onto a free
127.0.0.1 TCP port (app.db.session parses a plain TCP SQLAlchemy URL —
``?host=`` socket DSNs break make_url), and runs pytest in-process.
Background processes spawned by earlier Bash commands do not survive
between commands in this environment (lesson 48) — hence everything in
ONE process.
"""

from __future__ import annotations

import os
import shutil
import socket
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

import pgserver

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"


class _UnixToTCPHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            up.connect(self.server.upstream_sock)
        except OSError:
            return

        def pump(src, dst) -> None:
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
            except OSError:
                pass

        t = threading.Thread(target=pump, args=(self.request, up), daemon=True)
        t.start()
        pump(up, self.request)
        t.join(timeout=5)
        return


class _ThreadedTCPProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print("usage: rq16c_verify.py <pytest args...>", file=sys.stderr)
        return 2

    pgdata = tempfile.mkdtemp(prefix="rq16c_pgdata_")
    server = pgserver.get_server(pgdata)
    sock_dir = server.get_uri().split("host=")[-1].split("&")[0]
    upstream_sock = os.path.join(sock_dir, ".s.PGSQL.5432")
    port = _free_port()
    proxy = _ThreadedTCPProxy(("127.0.0.1", port), _UnixToTCPHandler)
    proxy.upstream_sock = upstream_sock
    threading.Thread(target=proxy.serve_forever, daemon=True).start()

    admin_url = f"postgresql://postgres@127.0.0.1:{port}/postgres"
    sa_url = f"postgresql+psycopg://postgres@127.0.0.1:{port}/postgres"
    os.environ.update(
        RQ16C_PG_ADMIN_URL=admin_url,
        # Neighbor PG modules reuse the SAME fresh server (their candidate
        # lists probe their own env names): rq16b entry-methods, rq14
        # desk/owner consistency — keeps the regression battery non-skipped.
        RQ16B_PG_ADMIN_URL=admin_url,
        RQ14_PG_ADMIN_URL=admin_url,
        DATABASE_URL=sa_url,
        TESTING="1",
        ENV="dev",
    )
    os.chdir(BACKEND_DIR)
    import pytest

    rc = 1
    try:
        rc = pytest.main(argv)
    finally:
        proxy.shutdown()
        try:
            server.stop()
        except Exception:
            pass
        shutil.rmtree(pgdata, ignore_errors=True)
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
