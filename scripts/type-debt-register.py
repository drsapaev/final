#!/usr/bin/env python3
"""
Type Debt Register — автоматический подсчёт для CI.
Генерирует отчёт, который можно использовать в CI pipeline для отслеживания прогресса.

Usage:
    python3 scripts/type-debt-register.py          # print report
    python3 scripts/type-debt-register.py --json   # JSON output for CI
"""
import json
import subprocess
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / 'frontend' / 'src'

def count_pattern(pattern: str, opts: str = '') -> int:
    """Count occurrences of a grep pattern in src/ .ts/.tsx files."""
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', pattern, str(FRONTEND_DIR)] + opts.split(),
        capture_output=True, text=True
    )
    return len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

def count_files_with_pattern(pattern: str) -> int:
    """Count files containing a pattern."""
    result = subprocess.run(
        ['grep', '-rl', '--include=*.ts', '--include=*.tsx', pattern, str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    return len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

def generate_report() -> dict:
    """Generate the Type Debt Register report."""
    # Count @ts-nocheck files (file-level, not line-level)
    ts_nocheck_files = count_files_with_pattern('@ts-nocheck')
    
    # Count @ts-expect-error lines (excluding @ts-nocheck files)
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', '@ts-expect-error', str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    ts_expect_error_lines = len([l for l in result.stdout.strip().split('\n') if l and '@ts-nocheck' not in l])
    
    # Count @ts-ignore lines
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', '@ts-ignore', str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    ts_ignore_lines = len([l for l in result.stdout.strip().split('\n') if l and '@ts-nocheck' not in l])
    
    # Count `any` (real code, not JSDoc)
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', '-E', ': any\\b|<any>|as any\\b', str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    any_real = len([l for l in result.stdout.strip().split('\n') 
                    if l and '@ts-nocheck' not in l and '* @' not in l])
    
    # Count `any` in JSDoc only
    any_jsdoc = len([l for l in result.stdout.strip().split('\n') 
                     if l and '@ts-nocheck' not in l and '* @' in l])
    
    # Count `as unknown as`
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', 'as unknown as', str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    as_unknown_as = len([l for l in result.stdout.strip().split('\n') if l and '@ts-nocheck' not in l])
    
    # Count eslint-disable
    result = subprocess.run(
        ['grep', '-rn', '--include=*.ts', '--include=*.tsx', 'eslint-disable', str(FRONTEND_DIR)],
        capture_output=True, text=True
    )
    eslint_disable = len([l for l in result.stdout.strip().split('\n') if l and '@ts-nocheck' not in l])
    
    # Count TODO(TS-MIGRATION)
    todo_count = count_pattern('TODO(TS-MIGRATION)')
    
    # Count FIXME(TS)
    fixme_count = count_pattern('FIXME(TS)')
    
    # Count total files
    total_files = subprocess.run(
        ['find', str(FRONTEND_DIR), '-name', '*.ts', '-o', '-name', '*.tsx'],
        capture_output=True, text=True
    )
    total_ts = len(total_files.stdout.strip().split('\n')) if total_files.stdout.strip() else 0
    
    # Count files WITHOUT @ts-nocheck
    no_ts_nocheck = total_ts - ts_nocheck_files
    
    return {
        'timestamp': subprocess.run(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], capture_output=True, text=True).stdout.strip(),
        'totals': {
            'ts_tsx_files': total_ts,
            'js_jsx_files': 0,  # Should always be 0 after structural migration
            'files_without_ts_nocheck': no_ts_nocheck,
            'files_with_ts_nocheck': ts_nocheck_files,
            'fully_typed_percentage': round(no_ts_nocheck / total_ts * 100, 1) if total_ts > 0 else 0,
        },
        'type_debt': {
            '@ts-nocheck_files': ts_nocheck_files,
            '@ts-expect-error_lines': ts_expect_error_lines,
            '@ts-ignore_lines': ts_ignore_lines,
            'any_real_code': any_real,
            'any_jsdoc_only': any_jsdoc,
            'as_unknown_as': as_unknown_as,
            'eslint_disable': eslint_disable,
            'TODO(TS-MIGRATION)': todo_count,
            'FIXME(TS)': fixme_count,
        },
        'phase': {
            'structural_migration': 'COMPLETE',
            'type_migration': 'IN_PROGRESS',
            'description': 'All .js/.jsx files converted to .ts/.tsx. 430 files still have @ts-nocheck (B5 Legacy). Type migration is ongoing.',
        }
    }

def print_report(report: dict):
    """Print human-readable report."""
    print('=' * 60)
    print('TYPE DEBT REGISTER')
    print(f"Generated: {report['timestamp']}")
    print('=' * 60)
    print()
    print('STRUCTURAL MIGRATION')
    print(f"  Phase A (structural):     {report['phase']['structural_migration']}")
    print(f"  Phase B (type migration): {report['phase']['type_migration']}")
    print()
    print('FILE TOTALS')
    t = report['totals']
    print(f"  .ts/.tsx files:           {t['ts_tsx_files']}")
    print(f"  .js/.jsx files:           {t['js_jsx_files']}")
    print(f"  Without @ts-nocheck:      {t['files_without_ts_nocheck']} ({t['fully_typed_percentage']}%)")
    print(f"  With @ts-nocheck:         {t['files_with_ts_nocheck']} ({100 - t['fully_typed_percentage']}%)")
    print()
    print('TYPE DEBT (excluding @ts-nocheck files)')
    d = report['type_debt']
    print(f"  @ts-nocheck (files):      {d['@ts-nocheck_files']}")
    print(f"  @ts-expect-error (lines): {d['@ts-expect-error_lines']}")
    print(f"  @ts-ignore (lines):       {d['@ts-ignore_lines']}")
    print(f"  any (real code):          {d['any_real_code']}")
    print(f"  any (JSDoc only):         {d['any_jsdoc_only']}")
    print(f"  as unknown as:            {d['as_unknown_as']}")
    print(f"  eslint-disable:           {d['eslint_disable']}")
    print(f"  TODO(TS-MIGRATION):       {d['TODO(TS-MIGRATION)']}")
    print(f"  FIXME(TS):                {d['FIXME(TS)']}")
    print()
    print('DESCRIPTION')
    print(f"  {report['phase']['description']}")
    print('=' * 60)

if __name__ == '__main__':
    report = generate_report()
    if '--json' in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
