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
    re.compile(rf"\b[Пп]орт {LEGACY_PORT_RX}\b"),
    re.compile(rf"\b-LocalPort {LEGACY_PORT_RX}\b"),
    re.compile(rf":{LEGACY_PORT_RX}.*LISTENING"),
]


def _is_excluded(path: Path) -> bool:
    path_text = path.as_posix()
    if path.name in EXCLUDED_FILES:
        return True
    return any(part in path_text for part in EXCLUDED_PARTS)


def _collect_active_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ACTIVE_TEXT_EXTENSIONS:
            continue
        if _is_excluded(path):
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
