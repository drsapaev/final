#!/usr/bin/env python3
"""
Detect hardcoded Russian text in JSX/JS files.
Counts Cyrillic string literals that should be migrated to i18n.
"""
import os
import re
import sys
import argparse

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src')
CYRILLIC_PATTERN = re.compile(r"['\"`][^'\"`]*[А-Яа-яЁё][^'\"`]*['\"`]")

EXCLUDE_DIRS = {'__tests__', 'node_modules', 'dist', 'locales', '.git'}
EXCLUDE_FILES = {'labTranslations.js', 'registrarTranslations.js', 'useTranslation.jsx'}

def scan_file(filepath):
    violations = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f, 1):
            # Skip comments and imports
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('import') or stripped.startswith('*'):
                continue
            matches = CYRILLIC_PATTERN.findall(line)
            for match in matches:
                # Skip if it's a key name (short, no spaces)
                text = match.strip('\'"`')
                if len(text) < 3 or ' ' not in text:
                    continue
                violations.append((i, text[:60]))
    return violations

def main():
    parser = argparse.ArgumentParser(description='Detect hardcoded Russian text')
    parser.add_argument('--max-violations', type=int, default=2300, help='Maximum allowed violations')
    parser.add_argument('--verbose', action='store_true', help='Print all violations')
    args = parser.parse_args()

    total_violations = 0
    files_with_violations = 0

    for root, dirs, files in os.walk(SRC_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for filename in files:
            if filename in EXCLUDE_FILES:
                continue
            if not filename.endswith(('.jsx', '.js')):
                continue
            filepath = os.path.join(root, filename)
            violations = scan_file(filepath)
            if violations:
                files_with_violations += 1
                total_violations += len(violations)
                if args.verbose:
                    rel_path = os.path.relpath(filepath, SRC_DIR)
                    for line_num, text in violations[:3]:
                        print(f"  {rel_path}:{line_num}: {text}")

    print(f"\nTotal hardcoded Russian strings: {total_violations}")
    print(f"Files with violations: {files_with_violations}")
    print(f"Threshold: {args.max_violations}")

    if total_violations > args.max_violations:
        print(f"❌ Exceeds threshold ({total_violations} > {args.max_violations})")
        sys.exit(1)
    else:
        print(f"✅ Within threshold ({total_violations} <= {args.max_violations})")
        sys.exit(0)

if __name__ == '__main__':
    main()
