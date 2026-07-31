#!/usr/bin/env python3
"""
D3: Add `import type { HttpApiError } from '...types/errors'` to files that
use HttpApiError but don't import it. Determines the correct relative path
based on file depth from frontend/src/.
"""
import os
import re
from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"

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
    return last_import_end + 1 if last_import_end >= 0 else 0

def process_file(filepath: Path) -> bool:
    content = filepath.read_text()
    if "HttpApiError" not in content:
        return False
    if "import" in content and "HttpApiError" in content.split("\n")[0:50].__str__():
        # Check if already imported
        for line in content.split("\n"):
            if line.startswith("import") and "HttpApiError" in line:
                return False

    lines = content.split("\n")
    depth = len(filepath.relative_to(FRONTEND_SRC).parts) - 1
    import_path = "../" * depth + "types/errors"

    insert_at = find_import_insertion_point(lines)
    lines.insert(insert_at, f"import type {{ HttpApiError }} from '{import_path}';")
    filepath.write_text("\n".join(lines))
    return True

def main():
    changed = 0
    for root, dirs, files in os.walk(FRONTEND_SRC):
        if "__tests__" in root:
            continue
        for fname in files:
            if not (fname.endswith(".ts") or fname.endswith(".tsx")):
                continue
            fpath = Path(root) / fname
            if process_file(fpath):
                changed += 1
                print(f"  {fpath.relative_to(FRONTEND_SRC)}")
    print(f"\nFiles updated: {changed}")

if __name__ == "__main__":
    main()
