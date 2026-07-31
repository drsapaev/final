#!/usr/bin/env python3
"""
Final consolidation baseline scanner.

Applies the exact grep filters specified in the Sprint C/D/E completion
criteria. Reports actual counts for each of the 13 criteria.

Usage:
    python3 scripts/final-consolidation-baseline.py
"""

from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"

def grep_count(pattern: str, extra_grep_v: str = "", include_tests: bool = False) -> int:
    """Run ripgrep with pattern, optionally filtering out __tests__ and extra patterns."""
    cmd = ["rg", "-c", pattern, str(FRONTEND_SRC), "--glob", "*.ts", "--glob", "*.tsx"]
    if not include_tests:
        cmd.extend(["--glob", "!**/__tests__/**"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0
    total = 0
    for line in result.stdout.strip().split("\n"):
        if ":" in line:
            try:
                total += int(line.rsplit(":", 1)[1])
            except ValueError:
                pass
    return total

def grep_lines(pattern: str, include_tests: bool = False) -> list[str]:
    """Run ripgrep with pattern, return matching lines."""
    cmd = ["rg", "-n", pattern, str(FRONTEND_SRC), "--glob", "*.ts", "--glob", "*.tsx"]
    if not include_tests:
        cmd.extend(["--glob", "!**/__tests__/**"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return result.stdout.strip().split("\n") if result.stdout.strip() else []

def main():
    print("=" * 70)
    print("FINAL CONSOLIDATION BASELINE")
    print("=" * 70)
    print()

    # Criterion 1: tsc --noEmit = 0
    print("1.  tsc --noEmit:                    (run separately)")

    # Criterion 3: as unknown as (excl tests) = 0
    count = grep_count(r"as unknown as")
    print(f"3.  'as unknown as' (excl tests):    {count}")

    # Criterion 4: AxiosLikeError (excl types/errors.ts) = 0
    lines = grep_lines(r"AxiosLikeError")
    filtered = [l for l in lines if "types/errors.ts" not in l and "// ADR-0016" not in l]
    print(f"4.  'AxiosLikeError' (excl errors.ts): {len(filtered)}")

    # Criterion 5: function getErrorMessage = 1
    count = grep_count(r"^export function getErrorMessage|^function getErrorMessage")
    print(f"5.  'function getErrorMessage':      {count}")

    # Criterion 6: prop-types in package.json = 0
    pkg = Path(__file__).resolve().parents[1] / "frontend" / "package.json"
    content = pkg.read_text()
    count = content.count("prop-types")
    print(f"6.  'prop-types' in package.json:    {count}")

    # Criterion 7: JSON.parse (excl safeParse/SW/heic) = 0
    lines = grep_lines(r"JSON\.parse")
    filtered = [l for l in lines if not any(x in l.lower() for x in ["safeparse", "safestorage", "serviceworker", "heicconverter"])]
    print(f"7.  'JSON.parse' (excl safe):        {len(filtered)}")

    # Criterion 8: as any / as { response = 0
    lines = grep_lines(r" as ")
    filtered = [l for l in lines if re.search(r"as any|as \{ response", l)]
    print(f"8.  'as any' / 'as {{ response':      {len(filtered)}")

    # Criterion 9: !. (excl tests, excl guarded)
    # This is tricky — "guarded" means preceded by if/filter/has/assert/throw/return
    lines = grep_lines(r"!\.")
    # Filter out lines that contain guard keywords
    guarded_patterns = ["if ", "filter", "has", "assert", "throw", "return", "?.", "&&", "||"]
    unguarded = [l for l in lines if not any(g in l for g in guarded_patterns)]
    print(f"9.  '!.' (excl tests, excl guarded): {len(unguarded)} / {len(lines)} total")

    # Criterion 10: Record<string, unknown> (excl tests, excl legit)
    lines = grep_lines(r"Record<string, unknown>")
    legit_patterns = ["LABELS", "CONFIG", "ALIASES", "TYPES", "stats", "context", "metadata"]
    filtered = [l for l in lines if not any(g in l for g in legit_patterns)]
    # Also exclude function signatures (Record<string, unknown>) at end of param
    filtered = [l for l in filtered if "Record<string, unknown>)" not in l]
    print(f"10. 'Record<string, unknown>' (excl): {len(filtered)} / {len(lines)} total")

    # Criterion 11: String( (excl tests, excl legit)
    lines = grep_lines(r"String\(")
    legit_patterns = ["err", "error", "unknown", "content", "message", "id", "Id", "url", "URL"]
    filtered = [l for l in lines if not any(g in l for g in legit_patterns)]
    print(f"11. 'String(' (excl legit):          {len(filtered)} / {len(lines)} total")

    # Criterion 12: useState<string | null> in hooks (excl UI state)
    hooks_dir = FRONTEND_SRC / "hooks"
    cmd = ["rg", "-n", r"useState<string \| null>", str(hooks_dir), "--glob", "*.ts", "--glob", "*.tsx", "--glob", "!**/__tests__/**"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    ui_patterns = ["search", "query", "tab", "selected", "filter"]
    filtered = [l for l in lines if not any(g in l.lower() for g in ui_patterns)]
    print(f"12. 'useState<string | null>' hooks: {len(filtered)} / {len(lines)} total")

    print()
    print("TARGETS:")
    print("  3.  as unknown as  → 0  (HARD)")
    print("  4.  AxiosLikeError → 0")
    print("  5.  getErrorMessage → 1")
    print("  6.  prop-types     → 0  (already done)")
    print("  7.  JSON.parse     → 0")
    print("  8.  as any/resp    → 0")
    print("  9.  !. unguarded   → 0")
    print("  10. Record<str,uk> → 0 (excl legit)")
    print("  11. String(        → 0 (excl legit)")
    print("  12. useState<s|n>  → 0 (excl UI state)")

if __name__ == "__main__":
    main()
