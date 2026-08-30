"""pg_dump/pg_restore must resolve even when not on PATH (#2772 DR finding).

Production Windows box keeps PostgreSQL clients outside PATH; the backup
service previously invoked bare "pg_dump" and every nightly run died with
FileNotFoundError leaving backend/backups/ empty since forever.
"""
from __future__ import annotations

import os

from app.services.backup_service import _resolve_pg_tool


def test_prefers_shutil_which_hit(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda t: "/usr/bin/" + t)
    assert _resolve_pg_tool("pg_dump") == "/usr/bin/pg_dump"


def test_falls_back_to_known_windows_install(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda t: None)
    monkeypatch.setattr(os.path, "isfile", lambda p: "postgresql/17/bin/" in p.replace("\\", "/").lower())
    got = _resolve_pg_tool("pg_dump")
    assert "PostgreSQL/17" in got.replace("\\", "/"), got


def test_last_resort_returns_bare_name(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda t: None)
    monkeypatch.setattr(os.path, "isfile", lambda p: False)
    assert _resolve_pg_tool("pg_dump") == "pg_dump"
