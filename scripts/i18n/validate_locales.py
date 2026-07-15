#!/usr/bin/env python3
"""
Validate locale key parity across all locale files.
Ensures ru ↔ uz-Latn ↔ uz-Cyrl ↔ en ↔ kk have the same keys.
"""
import json
import os
import sys
import argparse

LOCALES_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'src', 'i18n', 'locales')
LOCALES = ['ru', 'uz-Latn', 'uz-Cyrl', 'en', 'kk']

def load_locale(name):
    path = os.path.join(LOCALES_DIR, f'{name}.js')
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        content = f.read()
    # Simple extraction: find all top-level keys
    keys = set()
    for line in content.split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('//') and not line.startswith('import'):
            key = line.split(':')[0].strip().strip('"\'')
            if key and not key.startswith('//'):
                keys.add(key)
    return keys

def get_nested_keys(obj, prefix=''):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(get_nested_keys(v, full_key))
            else:
                keys.add(full_key)
    return keys

def main():
    parser = argparse.ArgumentParser(description='Validate locale key parity')
    parser.add_argument('--strict', action='store_true', help='Exit with error on any mismatch')
    args = parser.parse_args()

    locale_keys = {}
    for locale in LOCALES:
        keys = load_locale(locale)
        if keys is None:
            print(f"WARNING: Locale file {locale}.js not found, skipping")
            continue
        locale_keys[locale] = keys
        print(f"{locale}: {len(keys)} keys")

    if len(locale_keys) < 2:
        print("ERROR: Need at least 2 locale files to compare")
        sys.exit(1)

    # Compare with ru (base locale)
    base = 'ru'
    if base not in locale_keys:
        base = list(locale_keys.keys())[0]

    base_keys = locale_keys[base]
    all_good = True

    for locale, keys in locale_keys.items():
        if locale == base:
            continue
        missing = base_keys - keys
        extra = keys - base_keys
        if missing:
            print(f"ERROR: {locale} is missing {len(missing)} keys present in {base}")
            for k in sorted(missing)[:10]:
                print(f"  - {k}")
            all_good = False
        if extra:
            print(f"WARNING: {locale} has {len(extra)} extra keys not in {base}")
            for k in sorted(extra)[:5]:
                print(f"  + {k}")

    if all_good:
        print("✅ All locales have matching keys")
        sys.exit(0)
    elif args.strict:
        print("❌ Locale key parity check failed")
        sys.exit(1)
    else:
        print("⚠️  Locale key parity issues found (non-strict mode)")
        sys.exit(0)

if __name__ == '__main__':
    main()
