#!/usr/bin/env python3
"""
C3: Replace bare JSON.parse with safeJsonParse — fixed import insertion.
Finds the last complete import statement (line ending with ;) and inserts after it.
"""

import re, os
from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"
EXEMPT_FILES = {"safeJsonParse.ts", "ws-schemas.ts"}
EXEMPT_PATTERNS = ["safeParse", "safeStorage", "serviceWorker", "heicConverter"]

def find_import_insertion_point(lines: list[str]) -> int:
    """Find the line index after the last complete import statement."""
    last_import_end = -1
    in_import = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import "):
            in_import = True
        if in_import:
            if stripped.endswith(";"):
                last_import_end = i
                in_import = False
    # If no imports found, insert at top
    return last_import_end + 1 if last_import_end >= 0 else 0

def process_file(filepath: Path) -> tuple[bool, int]:
    content = filepath.read_text()
    if "JSON.parse" not in content:
        return False, 0

    lines = content.split("\n")
    changes = 0
    modified = False
    has_import = "safeJsonParse" in content

    for i, line in enumerate(lines):
        if "JSON.parse" not in line:
            continue
        if any(p in line for p in EXEMPT_PATTERNS):
            continue
        if "safeJsonParse" in line:
            continue
        # Skip comment lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue

        new_line = line.replace("JSON.parse(", "safeJsonParse(")
        if new_line != line:
            lines[i] = new_line
            modified = True
            changes += 1

    if modified and not has_import:
        depth = len(filepath.relative_to(FRONTEND_SRC).parts) - 1
        import_path = "../" * depth + "utils/safeJsonParse"
        insert_at = find_import_insertion_point(lines)
        lines.insert(insert_at, f"import {{ safeJsonParse }} from '{import_path}';")

    if modified:
        filepath.write_text("\n".join(lines))

    return modified, changes

def main():
    changed_files = 0
    total_changes = 0
    for root, dirs, files in os.walk(FRONTEND_SRC):
        if "__tests__" in root:
            continue
        for fname in files:
            if fname in EXEMPT_FILES:
                continue
            if not (fname.endswith(".ts") or fname.endswith(".tsx")):
                continue
            fpath = Path(root) / fname
            changed, changes = process_file(fpath)
            if changed:
                changed_files += 1
                total_changes += changes
                print(f"  {fpath.relative_to(FRONTEND_SRC)}: {changes} replacements")
    print(f"\nFiles: {changed_files}, Changes: {total_changes}")

if __name__ == "__main__":
    main()
