#!/usr/bin/env python3
"""Fix broken JSX attribute replacements: title=t('...') -> title={t('...')}.

Walks all .jsx files (excluding tests/stories) and fixes patterns where a t()
call is used as a JSX attribute value without curly braces.

Specifically: `attr=t('misc.X')` → `attr={t('misc.X')}`
Also handles `attr=t('misc.X', {...})`.
"""
import os
import re
import sys

REPO = '/home/z/my-project/final-audit/frontend/src'

# Match: word= followed by t('misc....') possibly with params and a closing )
# The expression ends with ) — possibly followed by more characters on the line.
# We want to wrap t(...) in { }.

# Strategy: find pattern like `[\w-]+=t\('misc\.[a-z0-9_]+'(?:,\s*\{[^}]*\})?\)`
# Replace with `\1={\2}` where \1 is the attr name and \2 is the t() call.

ATTR_RE = re.compile(
    r"(?P<attr>[\w.:-]+)=t\((?P<inner>'misc\.[a-z0-9_]+'(?:,\s*\{[^}]*\})?)\)"
)


def fix_file(filepath):
    with open(filepath, encoding='utf-8') as f:
        src = f.read()
    new_src = ATTR_RE.sub(r"\g<attr>={t(\g<inner>)}", src)
    if new_src != src:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_src)
        # Count replacements
        n = len(ATTR_RE.findall(src))
        return n
    return 0


def main():
    files = []
    for root, dirs, fnames in os.walk(REPO):
        if '__tests__' in root or 'node_modules' in root:
            continue
        for fn in fnames:
            if not fn.endswith('.jsx') or fn.endswith('.stories.jsx'):
                continue
            files.append(os.path.join(root, fn))
    total = 0
    affected = 0
    for fp in files:
        n = fix_file(fp)
        if n > 0:
            affected += 1
            total += n
            print(f"  ✓ {fp.replace(REPO + '/', '')}: {n} fixes")
    print(f"\nTotal: {total} fixes across {affected} files")


if __name__ == '__main__':
    main()
