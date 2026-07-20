#!/usr/bin/env python3
"""Check a file for module-scope Russian strings (before first component declaration).

Usage:
  python3 check_module_scope.py <file.jsx> [<file2.jsx> ...]
"""
import os
import re
import sys

REPO = '/home/z/my-project/final-audit/frontend/src'


def check(filepath):
    if filepath.startswith(REPO):
        full = filepath
        rel = filepath.replace(REPO + '/', '')
    else:
        rel = filepath
        full = os.path.join(REPO, filepath)
    if not os.path.exists(full):
        print(f"  ✗ {rel}: not found")
        return
    src = open(full, encoding='utf-8').read()
    lines = src.split('\n')
    # Find first component declaration
    first_comp = -1
    for i, ln in enumerate(lines):
        if re.match(r'\s*(export\s+)?(default\s+)?(function\s+[A-Z]\w*|const\s+[A-Z]\w*\s*=\s*\()', ln):
            first_comp = i + 1
            break
    if first_comp < 0:
        # No component declaration — assume all module scope
        first_comp = len(lines)
    # Find Russian strings before first_comp
    found = []
    for i, ln in enumerate(lines[:first_comp], 1):
        stripped = ln.lstrip()
        if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
            continue
        if re.search(r'(console|logger)\.(log|error|warn|debug|info)\s*\(', ln):
            continue
        # Strip inline // comments
        in_str = None
        cut = len(ln)
        j = 0
        while j < len(ln):
            c = ln[j]
            if in_str:
                if c == '\\':
                    j += 2
                    continue
                if c == in_str:
                    in_str = None
                j += 1
                continue
            if c in '"\'`':
                in_str = c
                j += 1
                continue
            if c == '/' and j + 1 < len(ln) and ln[j + 1] == '/':
                cut = j
                break
            j += 1
        code = ln[:cut]
        # Skip lines that are just function declarations (we'll process their bodies)
        # We want to flag Russian strings at module scope OR inside helper functions at module scope
        if re.search(r'[А-Яа-яЁё]{3,}', code):
            # Check if it's inside a function definition - if so, this helper function
            # is at module scope and would need t as parameter
            found.append((i, ln.rstrip()[:160]))
    if found:
        print(f"  ⚠ {rel}: {len(found)} module-scope lines with Russian:")
        for ln_no, txt in found[:8]:
            print(f"      L{ln_no}: {txt}")
        if len(found) > 8:
            print(f"      ... and {len(found) - 8} more")
    else:
        print(f"  ✓ {rel}: no module-scope Russian")


def main():
    for fp in sys.argv[1:]:
        check(fp)


if __name__ == '__main__':
    main()
