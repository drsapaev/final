#!/usr/bin/env python3
"""
SW-07 codemod: Replace hardcoded blue hex values with CSS variable references.

Maps:
  #007aff  → var(--mac-accent-blue, #007aff)   (Apple system blue)
  #3b82f6  → var(--mac-accent-blue, #3b82f6)   (Tailwind blue-500)
  #2563eb  → var(--mac-accent-blue, #2563eb)   (Tailwind blue-600)
  #0066cc  → var(--mac-accent-blue, #0066cc)   (custom)
  #2196f3  → var(--mac-accent-blue, #2196f3)   (Material blue)
  #0ea5e9  → var(--mac-accent-info, #0ea5e9)   (Tailwind sky-500, keep separate as info color)

Only touches inline style strings in .jsx files — does NOT modify:
  - CSS files (they already use CSS vars where appropriate)
  - design-system/ (dead code, will be deleted in SW-01)
  - scripts/ (codemods, migration scripts)
  - test files
  - Comments
"""
import re
import os
import sys

REPLACEMENTS = {
    '#007aff': 'var(--mac-accent-blue, #007aff)',
    '#3b82f6': 'var(--mac-accent-blue, #3b82f6)',
    '#2563eb': 'var(--mac-accent-blue, #2563eb)',
    '#0066cc': 'var(--mac-accent-blue, #0066cc)',
    '#2196f3': 'var(--mac-accent-blue, #2196f3)',
}

SKIP_DIRS = {'node_modules', 'dist', '__tests__', 'design-system', 'scripts', 'codemods', 'test'}
SKIP_EXTENSIONS = {'.css', '.test.jsx', '.test.js', '.stories.jsx'}

def should_skip(filepath):
    for skip_dir in SKIP_DIRS:
        if f'/{skip_dir}/' in filepath:
            return True
    for ext in SKIP_EXTENSIONS:
        if filepath.endswith(ext):
            return True
    return False

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    changes = 0

    for old_hex, new_val in REPLACEMENTS.items():
        # Only replace in string contexts (style values, not in comments)
        # Match: '#007aff' or "#007aff" in strings
        # Pattern: quote + hex + quote → quote + var(...) + quote
        pattern = r"(['\"])" + re.escape(old_hex) + r"\1"
        replacement = r"\1" + new_val + r"\1"
        new_content, count = re.subn(pattern, replacement, content)
        if count > 0:
            content = new_content
            changes += count

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return changes
    return 0

def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else 'src'
    total_changes = 0
    files_changed = 0

    for root, dirs, files in os.walk(src_dir):
        # Skip directories in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            if not (fname.endswith('.jsx') or fname.endswith('.js')):
                continue
            filepath = os.path.join(root, fname)
            if should_skip(filepath):
                continue

            changes = process_file(filepath)
            if changes > 0:
                files_changed += 1
                total_changes += changes
                print(f"  {filepath}: {changes} replacements")

    print(f"\nTotal: {total_changes} replacements in {files_changed} files")

if __name__ == '__main__':
    main()
