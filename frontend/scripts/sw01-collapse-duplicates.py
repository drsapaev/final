#!/usr/bin/env python3
"""
SW-01 Phase 2: Collapse duplicate MacOS* / non-prefixed component pairs.

For each pair, determines the winner by import count, then:
1. If Plain wins: deletes MacOS* file, removes MacOS* from index.js
2. If MacOS* wins: copies MacOS* content to Plain file, deletes MacOS* file
3. Replaces all MacOS<Component> references with <Component> across all source files
4. Updates index.js to remove MacOS* exports
"""
import os
import re
import shutil

MACOS_DIR = 'src/components/ui/macos'

# Pairs: (plain_name, macos_name, winner)
# Winner determined by import count analysis
PAIRS = [
    ('Alert', 'MacOSAlert', 'plain'),        # 29 vs 14
    ('Badge', 'MacOSBadge', 'plain'),         # 59 vs 40
    ('Button', 'MacOSButton', 'plain'),       # 105 vs 69
    ('Checkbox', 'MacOSCheckbox', 'macos'),   # 5 vs 26
    ('Input', 'MacOSInput', 'macos'),         # 29 vs 59
    ('List', 'MacOSList', 'plain'),           # 8 vs 0
    ('Modal', 'MacOSModal', 'plain'),         # 20 vs 12
    ('Radio', 'MacOSRadio', 'plain'),         # 1 vs 0
    ('Select', 'MacOSSelect', 'plain'),       # 73 vs 14
    ('Table', 'MacOSTable', 'macos'),         # 8 vs 11
    ('Textarea', 'MacOSTextarea', 'macos'),   # 14 vs 25
    ('Skeleton', 'MacOSLoadingSkeleton', 'macos'),  # 9 vs 27
]

# Special case: MacOSLoadingSkeleton → Skeleton (name mismatch)
# The macos file is MacOSLoadingSkeleton.jsx, plain is Skeleton.jsx
# When macos wins, copy MacOSLoadingSkeleton.jsx content → Skeleton.jsx

SKIP_DIRS = {'node_modules', 'dist', '__tests__', '.git'}
SKIP_EXT = {'.test.jsx', '.test.js', '.stories.jsx'}

def should_skip(filepath):
    for d in SKIP_DIRS:
        if f'/{d}/' in filepath:
            return True
    for ext in SKIP_EXT:
        if filepath.endswith(ext):
            return True
    return False

def process_files(src_dir, replacements):
    """Replace MacOSComponent with Component in all source files."""
    total = 0
    files_changed = 0
    
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            if not (fname.endswith('.jsx') or fname.endswith('.js')):
                continue
            filepath = os.path.join(root, fname)
            if should_skip(filepath):
                continue
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            for old_name, new_name in replacements.items():
                # Replace whole word matches only
                # Handles: imports, JSX tags, prop references, PropTypes
                content = re.sub(r'\b' + re.escape(old_name) + r'\b', new_name, content)
            
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                files_changed += 1
                total += 1
                print(f'  Updated: {filepath}')
    
    return files_changed

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
    
    # Build replacement map: MacOSComponent → Component
    replacements = {}
    for plain, macos, winner in PAIRS:
        replacements[macos] = plain
    
    print('=== Phase 1: Copy MacOS* winners to Plain name ===')
    for plain, macos, winner in PAIRS:
        macos_path = os.path.join(MACOS_DIR, f'{macos}.jsx')
        plain_path = os.path.join(MACOS_DIR, f'{plain}.jsx')
        
        if winner == 'macos':
            if os.path.exists(macos_path) and os.path.exists(plain_path):
                # Copy MacOS* content to Plain file
                shutil.copy2(macos_path, plain_path)
                print(f'  {macos}.jsx → {plain}.jsx (content copied)')
            elif os.path.exists(macos_path):
                # Rename MacOS* to Plain
                shutil.move(macos_path, plain_path)
                print(f'  {macos}.jsx → {plain}.jsx (renamed)')
    
    print('\n=== Phase 2: Delete MacOS* files ===')
    for plain, macos, winner in PAIRS:
        macos_path = os.path.join(MACOS_DIR, f'{macos}.jsx')
        if os.path.exists(macos_path):
            os.remove(macos_path)
            print(f'  Deleted: {macos}.jsx')
    
    print('\n=== Phase 3: Replace MacOS* references in source files ===')
    files_changed = process_files('src', replacements)
    print(f'\n  Total: {files_changed} files updated')
    
    print('\n=== Phase 4: Update index.js ===')
    index_path = os.path.join(MACOS_DIR, 'index.js')
    with open(index_path, 'r', encoding='utf-8') as f:
        index_content = f.read()
    
    # Remove MacOS* export lines
    for plain, macos, winner in PAIRS:
        # Remove lines like: export { default as MacOSButton } from './MacOSButton';
        pattern = rf"export {{[^}}]*\b{macos}\b[^}}]*}}[^;]*;\n"
        index_content = re.sub(pattern, '', index_content)
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)
    print(f'  Updated index.js (removed {len(PAIRS)} MacOS* exports)')
    
    print('\n=== Done! ===')

if __name__ == '__main__':
    main()
