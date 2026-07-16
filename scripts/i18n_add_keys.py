#!/usr/bin/env python3
"""Add a list of (key, value) pairs to misc section of all 5 locale files.

Usage:
  python3 i18n_add_keys.py <comment> <key1> <value1> [<key2> <value2> ...]
"""

import os
import re
import sys

LOCALE_DIR = '/home/z/my-project/final-audit/frontend/src/i18n/locales'
LOCALES = ['ru', 'uz-Latn', 'en', 'kk', 'uz-Cyrl']


def escape_js_string(s):
    """Escape a string for use in a JS single-quoted string literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def append_to_locale(locale, pairs, comment):
    path = os.path.join(LOCALE_DIR, f'{locale}.js')
    with open(path, encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    misc_start = -1
    for i, ln in enumerate(lines):
        if re.match(r'\s*misc:\s*\{', ln):
            misc_start = i
            break
    if misc_start < 0:
        raise RuntimeError(f"misc section not found in {path}")
    misc_end = -1
    for i in range(misc_start + 1, len(lines)):
        if re.match(r'\s*\},?\s*$', lines[i]) and '}' in lines[i] and '{' not in lines[i]:
            misc_end = i
            break
    if misc_end < 0:
        raise RuntimeError(f"misc section end not found in {path}")

    insert_lines = [f'    // {comment}']
    for key, val in pairs:
        insert_lines.append(f"    {key}: '{escape_js_string(val)}',")
    lines[misc_end:misc_end] = insert_lines
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    if len(sys.argv) < 4 or (len(sys.argv) - 2) % 2 != 0:
        print(__doc__)
        sys.exit(1)
    comment = sys.argv[1]
    args = sys.argv[2:]
    pairs = [(args[i], args[i + 1]) for i in range(0, len(args), 2)]
    for loc in LOCALES:
        append_to_locale(loc, pairs, comment)
    print(f"Added {len(pairs)} keys to all 5 locale files (comment: {comment})")
    for k, v in pairs:
        print(f"  {k}: {v[:60]}")


if __name__ == '__main__':
    main()
