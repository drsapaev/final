from __future__ import annotations

import re
from pathlib import Path


ACTIVE_TEXT_EXTENSIONS = {".py", ".ps1", ".bat", ".md"}
LEGACY_PORT = "".join(["8", "000"])
LEGACY_PORT_RX = re.escape(LEGACY_PORT)
EXCLUDED_PARTS = {
    ".ai-factory/patches",
    ".ai-factory/evolutions",
    ".venv",
    "node_modules",
    "output",
    "storage",
    "test-results",
    "docs/archives",
}
EXCLUDED_FILES = {
    "Fixing New Service Queue Time.md",
    "seed_services.py",
    "test_no_legacy_ports_in_active_text.py",
}

LEGACY_PORT_PATTERNS = [
    re.compile(rf"http://(?:127\.0\.0\.1|localhost):{LEGACY_PORT_RX}\b"),
    re.compile(rf"ws://(?:127\.0\.0\.1|localhost):{LEGACY_PORT_RX}\b"),
    re.compile(rf"\b127\.0\.0\.1:{LEGACY_PORT_RX}\b"),
    re.compile(rf"\blocalhost:{LEGACY_PORT_RX}\b"),
    re.compile(rf"\b0\.0\.0\.0:{LEGACY_PORT_RX}\b"),
    re.compile(rf"\bport={LEGACY_PORT_RX}\b"),
    re.compile(rf"\b--port {LEGACY_PORT_RX}\b"),
    re.compile(rf"\b[Р В РЎСџР В РЎвЂ”]Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™ {LEGACY_PORT_RX}\b"),
    re.compile(rf"\b-LocalPort {LEGACY_PORT_RX}\b"),
    re.compile(rf":{LEGACY_PORT_RX}.*LISTENING"),
]

SQLITE_FIRST_DOC_PATTERNS = [
    re.compile(r"sqlite3\s+backend/clinic\.db\b", re.IGNORECASE),
    re.compile(r"SQLite\s+\(clinic\.db\)\s+", re.IGNORECASE),
    re.compile(r"clinic\.db\s+Р РЋР вЂљР В Р’В°Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В Р’В°Р В Р’ВµР РЋРІР‚С™", re.IGNORECASE),
]

RETIRED_DOC_COMMAND_PATTERNS = [
    re.compile(r"\bpython\s+quick_check\.py\b", re.IGNORECASE),
    re.compile(r"\bpython\s+check_system_integrity\.py\b", re.IGNORECASE),
    re.compile(r"\bpython\s+create_user_management_tables\.py\b", re.IGNORECASE),
]

SQLITE_SCHEMA_PATCH_MARKERS = [
    "ALTER TABLE",
    "CREATE TABLE",
    "CREATE INDEX",
]

SQLITE_DATA_FIX_MARKERS = [
    "UPDATE ",
    "INSERT ",
    "DELETE ",
]

INTENTIONAL_SQLITE_RECOVERY_TOOLS = {
    "backend/app/scripts/migrate_sqlite_to_postgres.py",
    "backend/app/scripts/migrate_users_to_postgres.py",
    "backend/check_db.py",
    "backend/scripts/inspect_today_visits.py",
    "backend/scripts/pass15_restore_compat_audit.py",
}


def _is_excluded(path: Path) -> bool:
    path_text = path.as_posix()
    if path.name in EXCLUDED_FILES:
        return True
    return any(part in path_text for part in EXCLUDED_PARTS)


def _iter_scan_paths(root: Path):
    try:
        children = list(root.iterdir())
    except OSError:
        return

    for path in children:
        if _is_excluded(path):
            continue
        yield path
        try:
            is_dir = path.is_dir()
        except OSError:
            continue
        if is_dir:
            yield from _iter_scan_paths(path)


def _collect_active_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in _iter_scan_paths(root):
        if _is_excluded(path):
            continue
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        if path.suffix.lower() not in ACTIVE_TEXT_EXTENSIONS:
            continue
        files.append(path)
    return files


def test_no_legacy_port_refs_in_active_text():
    repo_root = Path(__file__).resolve().parents[3]
    matches: list[str] = []

    scan_roots = [
        repo_root / "backend",
        repo_root / "docs",
        repo_root / ".ai-factory",
    ]

    seen: set[Path] = set()
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in _collect_active_text_files(scan_root):
            if path in seen:
                continue
            seen.add(path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for pattern in LEGACY_PORT_PATTERNS:
                for match in pattern.finditer(content):
                    line_number = content.count("\n", 0, match.start()) + 1
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line_end = content.find("\n", match.start())
                    if line_end == -1:
                        line_end = len(content)
                    line = content[line_start:line_end].strip()
                    matches.append(f"{path.relative_to(repo_root)}:{line_number}:{line}")

    for path in repo_root.glob("*.md"):
        if _is_excluded(path):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for pattern in LEGACY_PORT_PATTERNS:
            for match in pattern.finditer(content):
                line_number = content.count("\n", 0, match.start()) + 1
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.start())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end].strip()
                matches.append(f"{path.relative_to(repo_root)}:{line_number}:{line}")

    assert not matches, "Legacy port references still exist:\n" + "\n".join(matches[:50])


def _read_repo_text(repo_root: Path, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8", errors="ignore")


def test_runtime_env_docs_use_explicit_prod_cors_guidance():
    repo_root = Path(__file__).resolve().parents[3]
    docs_env = _read_repo_text(repo_root, "docs/README_env.md")
    docker_compose = _read_repo_text(repo_root, "ops/docker-compose.yml")
    staging_compose = _read_repo_text(repo_root, "ops/compose.staging.yml")

    assert "CORS_ALLOW_ALL" in docs_env
    assert "local diagnostics only" in docs_env
    assert "stage|prod" in docs_env
    assert "CORS_ALLOW_ALL: ${CORS_ALLOW_ALL:-0}" in docker_compose
    assert (
        "BACKEND_CORS_ORIGINS: ${BACKEND_CORS_ORIGINS:-http://localhost:5173,http://127.0.0.1:5173}"
        in docker_compose
    )
    assert "AUTH_SECRET: ${AUTH_SECRET:-}" in staging_compose


def test_runtime_env_samples_keep_auth_secret_as_optional_alias():
    repo_root = Path(__file__).resolve().parents[3]
    ops_env = _read_repo_text(repo_root, "ops/.env.example")
    staging_env = _read_repo_text(repo_root, "ops/staging.env.sample")
    docker_compose = _read_repo_text(repo_root, "ops/docker-compose.yml")

    assert "# Optional legacy alias. Leave empty to use SECRET_KEY." in ops_env
    assert "# Optional legacy alias. Leave empty to use SECRET_KEY." in staging_env
    assert "PORT=18000" in ops_env
    assert "BACKEND_PORT=18000" in ops_env
    assert "AUTH_SECRET: ${AUTH_SECRET:-}" in docker_compose


def test_runtime_database_guards_and_diagnostic_opt_ins_are_explicit():
    repo_root = Path(__file__).resolve().parents[3]
    session_py = _read_repo_text(repo_root, "backend/app/db/session.py")
    init_db_py = _read_repo_text(repo_root, "backend/init_database.py")
    inspect_users_py = _read_repo_text(repo_root, "backend/inspect_users.py")
    load_test_py = _read_repo_text(repo_root, "backend/load_test.py")

    assert "ALLOW_SQLITE_DATABASE_URL" in session_py
    assert "SQLite DATABASE_URL is disabled for runtime." in session_py
    assert "_safe_database_url_for_log" in session_py
    assert "CONFIRM_INIT_DATABASE" in init_db_py
    assert "CONFIRM_INSPECT_USERS" in inspect_users_py
    assert "CONFIRM_LOAD_TEST" in load_test_py


def test_windows_clinic_host_redacts_restore_urls_and_guards_forceful_ops():
    repo_root = Path(__file__).resolve().parents[3]
    clinic_host = _read_repo_text(repo_root, "ops/windows/clinic_host.ps1")

    assert "CONFIRM_CLINIC_HOST_STOP_PORT_OWNERS" in clinic_host
    assert "Redact-DatabaseUrl" in clinic_host
    assert "RESTORE_DATABASE_URL=$(Redact-DatabaseUrl -DatabaseUrl $restoreDatabaseUrl)" in clinic_host
    assert "CONFIRM_FORCE_RELEASE_CHECKOUT" in clinic_host
