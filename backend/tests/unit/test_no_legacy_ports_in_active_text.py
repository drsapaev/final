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
    "docs/archive",
    "docs/archives",
    "scripts/legacy_scripts",
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
    re.compile(rf"\b[Пп]орт {LEGACY_PORT_RX}\b"),
    re.compile(rf"\b-LocalPort {LEGACY_PORT_RX}\b"),
    re.compile(rf":{LEGACY_PORT_RX}.*LISTENING"),
]

SQLITE_FIRST_DOC_PATTERNS = [
    re.compile(r"sqlite3\s+backend/clinic\.db\b", re.IGNORECASE),
    re.compile(r"SQLite\s+\(clinic\.db\)\s+", re.IGNORECASE),
    re.compile(r"clinic\.db\s+работает", re.IGNORECASE),
]

DEFAULT_DB_CREDENTIAL_DOC_PATTERNS = [
    re.compile(r"postgresql\+psycopg://clinic:clinicpwd@", re.IGNORECASE),
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


def test_no_sqlite_first_claims_in_active_docs():
    repo_root = Path(__file__).resolve().parents[3]
    matches: list[str] = []

    scan_roots = [
        repo_root / "backend",
        repo_root / "docs",
    ]

    seen: set[Path] = set()
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in _collect_active_text_files(scan_root):
            if path in seen or path.suffix.lower() != ".md":
                continue
            seen.add(path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for pattern in SQLITE_FIRST_DOC_PATTERNS:
                for match in pattern.finditer(content):
                    line_number = content.count("\n", 0, match.start()) + 1
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line_end = content.find("\n", match.start())
                    if line_end == -1:
                        line_end = len(content)
                    line = content[line_start:line_end].strip()
                    matches.append(f"{path.relative_to(repo_root)}:{line_number}:{line}")

    assert not matches, "SQLite-first doc claims still exist:\n" + "\n".join(matches[:50])


def test_no_default_database_passwords_in_active_docs():
    repo_root = Path(__file__).resolve().parents[3]
    matches: list[str] = []

    scan_roots = [
        repo_root / "backend",
        repo_root / "docs",
    ]

    seen: set[Path] = set()
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in _collect_active_text_files(scan_root):
            if path in seen or path.suffix.lower() != ".md":
                continue
            seen.add(path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for pattern in DEFAULT_DB_CREDENTIAL_DOC_PATTERNS:
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

        for pattern in DEFAULT_DB_CREDENTIAL_DOC_PATTERNS:
            for match in pattern.finditer(content):
                line_number = content.count("\n", 0, match.start()) + 1
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.start())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end].strip()
                matches.append(f"{path.relative_to(repo_root)}:{line_number}:{line}")

    assert not matches, (
        "Default database passwords still exist in active docs:\n"
        + "\n".join(matches[:50])
    )


def test_no_default_database_passwords_in_active_workflows():
    repo_root = Path(__file__).resolve().parents[3]
    workflow_root = repo_root / ".github" / "workflows"
    matches: list[str] = []

    workflow_files = sorted(
        list(workflow_root.glob("*.yml")) + list(workflow_root.glob("*.yaml"))
    )
    for path in workflow_files:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for pattern in DEFAULT_DB_CREDENTIAL_DOC_PATTERNS:
            for match in pattern.finditer(content):
                line_number = content.count("\n", 0, match.start()) + 1
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.start())
                if line_end == -1:
                    line_end = len(content)
                line = content[line_start:line_end].strip()
                matches.append(f"{path.relative_to(repo_root)}:{line_number}:{line}")

    assert not matches, (
        "Default database passwords still exist in active workflows:\n"
        + "\n".join(matches[:50])
    )


def test_no_retired_backend_helper_commands_in_active_docs():
    repo_root = Path(__file__).resolve().parents[3]
    matches: list[str] = []

    scan_roots = [
        repo_root / "backend",
        repo_root / "docs",
    ]

    seen: set[Path] = set()
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in _collect_active_text_files(scan_root):
            if path in seen or path.suffix.lower() != ".md":
                continue
            seen.add(path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for pattern in RETIRED_DOC_COMMAND_PATTERNS:
                for match in pattern.finditer(content):
                    line_number = content.count("\n", 0, match.start()) + 1
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    line_end = content.find("\n", match.start())
                    if line_end == -1:
                        line_end = len(content)
                    line = content[line_start:line_end].strip()
                    matches.append(f"{path.relative_to(repo_root)}:{line_number}:{line}")

    assert not matches, (
        "Retired backend helper commands still exist in active docs:\n"
        + "\n".join(matches[:50])
    )


def test_backend_sqlite_schema_patches_require_standard_opt_in():
    repo_root = Path(__file__).resolve().parents[3]
    backend_root = repo_root / "backend"
    matches: list[str] = []

    scan_paths = [
        path
        for path in _collect_active_text_files(backend_root)
        if path.suffix.lower() == ".py"
    ]
    scan_paths.extend(repo_root.glob("*.py"))
    for path in scan_paths:
        relative_path = path.relative_to(repo_root).as_posix()
        if relative_path in INTENTIONAL_SQLITE_RECOVERY_TOOLS:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if "sqlite3.connect" not in content or "clinic.db" not in content:
            continue
        if not any(marker in content for marker in SQLITE_SCHEMA_PATCH_MARKERS):
            continue
        if "ALLOW_LEGACY_SQLITE_SCHEMA_PATCH" in content:
            continue

        matches.append(relative_path)

    assert not matches, (
        "Legacy SQLite schema patch scripts must require "
        "ALLOW_LEGACY_SQLITE_SCHEMA_PATCH=1:\n" + "\n".join(matches)
    )


def test_backend_sqlite_data_fixes_require_standard_opt_in():
    repo_root = Path(__file__).resolve().parents[3]
    backend_root = repo_root / "backend"
    matches: list[str] = []

    scan_paths = [
        path
        for path in _collect_active_text_files(backend_root)
        if path.suffix.lower() == ".py"
    ]
    scan_paths.extend(repo_root.glob("*.py"))
    for path in scan_paths:
        relative_path = path.relative_to(repo_root).as_posix()
        if relative_path in INTENTIONAL_SQLITE_RECOVERY_TOOLS:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if "sqlite3.connect" not in content or "clinic.db" not in content:
            continue
        if not any(marker in content for marker in SQLITE_DATA_FIX_MARKERS):
            continue
        if "ALLOW_LEGACY_SQLITE_DATA_FIX" in content:
            continue
        if "ALLOW_LEGACY_SQLITE_SCHEMA_PATCH" in content:
            continue

        matches.append(relative_path)

    assert not matches, (
        "Legacy SQLite data-fix scripts must require "
        "ALLOW_LEGACY_SQLITE_DATA_FIX=1:\n" + "\n".join(matches)
    )


def test_legacy_sqlite_reset_scripts_are_deprecated_fail_fast():
    repo_root = Path(__file__).resolve().parents[3]
    backend_root = repo_root / "backend"

    auto_reset = (backend_root / "reset_database_auto.ps1").read_text(
        encoding="utf-8", errors="ignore"
    )
    interactive_reset = (backend_root / "reset_database.ps1").read_text(
        encoding="utf-8", errors="ignore"
    )
    fk_summary = (backend_root / "FK_POLICIES_SUMMARY.md").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "CONFIRM_LEGACY_SQLITE_RESET is intentionally ignored" in auto_reset
    assert "AUTO MODE: No confirmation required" not in auto_reset
    assert "Automatic SQLite file deletion is disabled" in auto_reset
    assert "PostgreSQL + Alembic are the database source of truth" in auto_reset
    assert "Remove-Item" not in auto_reset
    assert "exit 2" in auto_reset

    assert "DEPRECATED DATABASE RESET SCRIPT" in interactive_reset
    assert "This legacy helper no longer deletes local SQLite files" in interactive_reset
    assert "PostgreSQL + Alembic are the database source of truth" in interactive_reset
    assert "Remove-Item" not in interactive_reset
    assert "exit 2" in interactive_reset

    assert "PostgreSQL runtime databases should apply schema changes with Alembic" in fk_summary
    assert "legacy SQLite-only recovery helper" in fk_summary


def test_allowlisted_sqlite_recovery_helpers_remain_explicit_opt_in():
    repo_root = Path(__file__).resolve().parents[3]

    required_markers = {
        "backend/app/scripts/migrate_sqlite_to_postgres.py": [
            "CONFIRM_SQLITE_TO_POSTGRES_MIGRATION",
            "--dry-run",
        ],
        "backend/app/scripts/migrate_users_to_postgres.py": [
            "CONFIRM_USERS_SQLITE_TO_POSTGRES_MIGRATION",
            "--dry-run",
        ],
        "backend/scripts/inspect_today_visits.py": [
            "ALLOW_LEGACY_SQLITE_DIAGNOSTIC_READ",
            "explicit local legacy SQLite diagnostic run",
        ],
        "backend/scripts/pass15_restore_compat_audit.py": [
            "ALLOW_PASS15_RESTORE_COMPAT_AUDIT",
            "CONFIRM_PASS15_RESTORE_COMPAT_APPLY",
        ],
    }

    missing: list[str] = []
    for relative_path, markers in required_markers.items():
        file_path = repo_root / relative_path
        if not file_path.exists():
            # File has been moved to scripts/legacy_scripts/ — skip active-backend check.
            continue
        content = file_path.read_text(
            encoding="utf-8", errors="ignore"
        )
        for marker in markers:
            if marker not in content:
                missing.append(f"{relative_path}: missing {marker}")

    assert not missing, "SQLite recovery helper opt-in markers missing:\n" + "\n".join(missing)


def test_diagnose_ci_uses_only_isolated_temporary_sqlite():
    repo_root = Path(__file__).resolve().parents[3]
    diagnose_ci_path = repo_root / "backend" / "diagnose_ci.py"
    if not diagnose_ci_path.exists():
        # backend/diagnose_ci.py was retired and moved to scripts/legacy_scripts/.
        # No active file to enforce isolation rules on.
        return
    content = diagnose_ci_path.read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "tempfile.TemporaryDirectory" in content
    assert "diagnose_ci.db" in content
    assert "ALLOW_SQLITE_DATABASE_URL" in content
    assert "CONFIRM_DIAGNOSE_CI_TEMP_SQLITE" in content
    assert "clinic.db" not in content


def test_orphan_cleanup_requires_postgres_without_sqlite_fallback():
    repo_root = Path(__file__).resolve().parents[3]
    orphan_cleanup_path = repo_root / "backend" / "cleanup_orphaned_records.py"
    if not orphan_cleanup_path.exists():
        # backend/cleanup_orphaned_records.py was retired and moved to
        # scripts/legacy_scripts/. No active file to enforce Postgres-only rules on.
        return
    content = orphan_cleanup_path.read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "DATABASE_URL must be configured before orphan cleanup." in content
    assert "SQLite DATABASE_URL is disabled for orphan cleanup." in content
    assert "sqlite:///./clinic.db" not in content
    assert "clinic.db" not in content
    assert "PRAGMA foreign_keys=ON" not in content
